"""
Sitemap Reconciliation & Cross-Signal Conflict Triangulation Engine (Milestone M6.5).
Triangulates sitemap declarations against empirical crawl evidence, indexability gates,
canonical chains, and internal link topology.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Union

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    CrawlabilityStatus,
    IndexabilityStatus,
    CanonicalizationSignal,
    CanonicalChainStatus,
    NodeOrphanStatus,
    SitemapDocumentRecord,
    SitemapUrlRecord,
    CrossSignalConflictType,
    CrossSignalConflictSeverity,
    EvidenceNature,
    CrossSignalConflictRecord,
    SitemapReconciliationSummary,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.analyzers.record_lookup import RecordLookupIndex


class SitemapReconciler:
    """
    Production cross-signal conflict triangulator for XML sitemaps.
    Directly consumes M6.2 SearchEligibility, M6.3 Chains, and M6.4 Link Graph models.
    """

    @classmethod
    def reconcile(
        cls,
        site_crawl: SiteCrawlResult,
        sitemap_documents: Optional[List[SitemapDocumentRecord]] = None,
        sitemap_urls: Optional[Union[Dict[str, SitemapUrlRecord], List[SitemapUrlRecord]]] = None,
        robots_parser: Optional[Any] = None,
        user_agent: str = "RankIntel/2.0 (+https://github.com/ZeroTrace7/RankIntel)",
    ) -> SitemapReconciliationSummary:
        """
        Reconcile sitemap declarations with crawl, indexability, canonical, and link graph evidence.
        Updates site_crawl.search_eligibility in-place and sets site_crawl.sitemap_reconciliation.
        """
        s_docs: List[SitemapDocumentRecord] = sitemap_documents or []

        # Normalize sitemap_urls into dict keyed by identity_url
        s_url_map: Dict[str, SitemapUrlRecord] = {}
        if isinstance(sitemap_urls, dict):
            s_url_map = dict(sitemap_urls)
        elif isinstance(sitemap_urls, list):
            for item in sitemap_urls:
                ident = item.identity_url or UrlNormalizer.get_url_identity(item.loc)
                s_url_map[ident] = item

        # Build index for crawl records
        lookup_index = RecordLookupIndex(site_crawl.crawl_records)

        # Map sitemap URLs by raw and normalized identities for lookup
        sitemap_by_raw: Dict[str, SitemapUrlRecord] = {rec.loc.strip(): rec for rec in s_url_map.values()}
        sitemap_by_ident: Dict[str, SitemapUrlRecord] = {rec.identity_url: rec for rec in s_url_map.values()}

        # 1. Update site_crawl.search_eligibility records with in_sitemap presence
        for url_key, elig_rec in site_crawl.search_eligibility.items():
            ident = UrlNormalizer.get_url_identity(url_key)
            if url_key in sitemap_by_raw or ident in sitemap_by_ident:
                elig_rec.in_sitemap = True

        conflicts: List[CrossSignalConflictRecord] = []
        uncrawled_urls: List[str] = []
        missing_internal_urls: List[str] = []

        crawled_count = 0

        # -------------------------------------------------------------------
        # Evaluate Sitemap URLs: Conflicts A, B, C, D, E, H, I
        # -------------------------------------------------------------------
        for ident, s_rec in s_url_map.items():
            target_url = s_rec.loc
            crawl_rec = lookup_index.lookup(target_url)
            elig_rec = site_crawl.search_eligibility.get(target_url)
            if not elig_rec and crawl_rec:
                elig_rec = site_crawl.search_eligibility.get(crawl_rec.url)

            # Conflict A: Sitemap + Robots Blocked
            is_robots_blocked = False
            if crawl_rec and crawl_rec.crawl_status == CrawlStatus.BLOCKED:
                is_robots_blocked = True
            elif elig_rec and elig_rec.crawlability == CrawlabilityStatus.BLOCKED:
                is_robots_blocked = True
            elif robots_parser is not None:
                try:
                    if not robots_parser.can_fetch(user_agent, target_url):
                        is_robots_blocked = True
                except Exception:
                    pass

            if is_robots_blocked:
                conflicts.append(
                    CrossSignalConflictRecord(
                        url=target_url,
                        conflict_type=CrossSignalConflictType.SITEMAP_ROBOTS_BLOCKED,
                        severity=CrossSignalConflictSeverity.HIGH,
                        signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                        signal_a_state="included_in_sitemap",
                        signal_b_source="robots.txt",
                        signal_b_state="BLOCKED",
                        evidence_nature=EvidenceNature.OBSERVED,
                        summary=f"Sitemap URL '{target_url}' is blocked by robots.txt disallow rules.",
                        recommended_reconciliation="Remove URL from sitemap, or unblock path in robots.txt if indexation is intended.",
                    )
                )

            # Check if URL was crawled
            if crawl_rec:
                crawled_count += 1

                # Conflict B: Sitemap + Noindex Conflict
                is_noindex = False
                if elig_rec and elig_rec.indexability == IndexabilityStatus.NOINDEX:
                    is_noindex = True
                elif crawl_rec.raw_html and "noindex" in crawl_rec.raw_html.lower():
                    # Double check meta robots
                    from rankintel.analyzers.indexability_engine import IndexabilityEngine
                    meta_dirs = IndexabilityEngine.parse_meta_robots(crawl_rec.raw_html)
                    x_dirs = IndexabilityEngine.parse_x_robots_tag(crawl_rec.response_headers)
                    if any(d in IndexabilityEngine.NOINDEX_DIRECTIVES for d in (meta_dirs + x_dirs)):
                        is_noindex = True

                if is_noindex:
                    conflicts.append(
                        CrossSignalConflictRecord(
                            url=target_url,
                            conflict_type=CrossSignalConflictType.SITEMAP_NOINDEX_CONFLICT,
                            severity=CrossSignalConflictSeverity.HIGH,
                            signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                            signal_a_state="included_in_sitemap",
                            signal_b_source="meta_robots / X-Robots-Tag",
                            signal_b_state="noindex",
                            evidence_nature=EvidenceNature.OBSERVED,
                            summary=f"Sitemap URL '{target_url}' specifies a 'noindex' directive.",
                            recommended_reconciliation="Remove 'noindex' directive if page should rank, or remove URL from XML sitemap.",
                        )
                    )

                # Conflict C: Sitemap + Redirect Conflict
                if (300 <= crawl_rec.status_code <= 399) or crawl_rec.crawl_status == CrawlStatus.REDIRECTED:
                    target_dest = crawl_rec.redirect_url or "redirect_target"
                    conflicts.append(
                        CrossSignalConflictRecord(
                            url=target_url,
                            conflict_type=CrossSignalConflictType.SITEMAP_REDIRECT_CONFLICT,
                            severity=CrossSignalConflictSeverity.MEDIUM,
                            signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                            signal_a_state="included_in_sitemap",
                            signal_b_source="http_status",
                            signal_b_state=f"HTTP {crawl_rec.status_code} -> {target_dest}",
                            evidence_nature=EvidenceNature.OBSERVED,
                            summary=f"Sitemap URL '{target_url}' returns HTTP {crawl_rec.status_code} redirect.",
                            recommended_reconciliation="Replace redirecting URL in sitemap with the final destination target URL.",
                        )
                    )

                # Conflict D: Sitemap + Error Conflict
                if (crawl_rec.status_code >= 400) or (crawl_rec.crawl_status == CrawlStatus.FAILED and not is_robots_blocked):
                    status_lbl = f"HTTP {crawl_rec.status_code}" if crawl_rec.status_code else "FAILED"
                    conflicts.append(
                        CrossSignalConflictRecord(
                            url=target_url,
                            conflict_type=CrossSignalConflictType.SITEMAP_ERROR_CONFLICT,
                            severity=CrossSignalConflictSeverity.HIGH,
                            signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                            signal_a_state="included_in_sitemap",
                            signal_b_source="http_status",
                            signal_b_state=status_lbl,
                            evidence_nature=EvidenceNature.OBSERVED,
                            summary=f"Sitemap URL '{target_url}' returned HTTP error ({status_lbl}).",
                            recommended_reconciliation="Restore broken page or remove dead URL from XML sitemap.",
                        )
                    )

                # Conflict E: Sitemap + Canonical Elsewhere
                if elig_rec and elig_rec.canonicalization in (
                    CanonicalizationSignal.CANONICALIZED_ELSEWHERE,
                    CanonicalizationSignal.CROSS_DOMAIN,
                ):
                    c_target = elig_rec.canonical_target or "unknown"
                    conflicts.append(
                        CrossSignalConflictRecord(
                            url=target_url,
                            conflict_type=CrossSignalConflictType.SITEMAP_CANONICAL_ELSEWHERE,
                            severity=CrossSignalConflictSeverity.MEDIUM,
                            signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                            signal_a_state="included_in_sitemap",
                            signal_b_source="canonical_tag",
                            signal_b_state=f"canonical_target={c_target}",
                            evidence_nature=EvidenceNature.OBSERVED,
                            summary=f"Sitemap URL '{target_url}' declares canonical pointing elsewhere ({c_target}).",
                            recommended_reconciliation="Replace non-canonical URL in sitemap with the declared canonical URL.",
                        )
                    )

                # Conflict H: Sitemap + Orphan Candidate (Directly consumes M6.4 link_graph)
                if site_crawl.link_graph and site_crawl.link_graph.nodes:
                    node = (
                        site_crawl.link_graph.nodes.get(target_url)
                        or site_crawl.link_graph.nodes.get(ident)
                    )
                    if node and node.orphan_status == NodeOrphanStatus.POTENTIAL_ORPHAN:
                        conflicts.append(
                            CrossSignalConflictRecord(
                                url=target_url,
                                conflict_type=CrossSignalConflictType.SITEMAP_ORPHAN_CANDIDATE,
                                severity=CrossSignalConflictSeverity.LOW,
                                signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                                signal_a_state="included_in_sitemap",
                                signal_b_source="internal_link_graph",
                                signal_b_state="zero_observed_inbound_internal_links",
                                evidence_nature=EvidenceNature.OBSERVED,
                                summary=f"Sitemap URL '{target_url}' has zero observed inbound internal links in crawl graph.",
                                recommended_reconciliation="Add contextual internal links from relevant parent pages to support this page.",
                            )
                        )
            else:
                # Conflict I: Sitemap URL Not Crawled (Discovery evidence only)
                uncrawled_urls.append(target_url)
                conflicts.append(
                    CrossSignalConflictRecord(
                        url=target_url,
                        conflict_type=CrossSignalConflictType.SITEMAP_URL_UNCRAWLED,
                        severity=CrossSignalConflictSeverity.INFO,
                        signal_a_source=f"sitemap:{s_rec.source_sitemap}",
                        signal_a_state="discovered_in_sitemap",
                        signal_b_source="crawl_record",
                        signal_b_state="UNAVAILABLE",
                        evidence_nature=EvidenceNature.UNAVAILABLE,
                        summary=f"Sitemap URL '{target_url}' was discovered via sitemap but not crawled within crawl budget.",
                        recommended_reconciliation="Discovery evidence only; crawlability and indexability remain UNKNOWN until audited.",
                    )
                )

        # -------------------------------------------------------------------
        # Conflicts F & G: Directly consume M6.3 CanonicalChainRecords
        # -------------------------------------------------------------------
        if site_crawl.canonical_chains:
            for chain in site_crawl.canonical_chains.values():
                # Conflict F: Canonical Target Redirect
                if chain.points_to_redirect or chain.status == CanonicalChainStatus.POINTS_TO_REDIRECT:
                    conflicts.append(
                        CrossSignalConflictRecord(
                            url=chain.source_url,
                            conflict_type=CrossSignalConflictType.CANONICAL_TARGET_REDIRECT,
                            severity=CrossSignalConflictSeverity.HIGH,
                            signal_a_source="canonical_tag",
                            signal_a_state=f"declared_canonical={chain.declared_canonical}",
                            signal_b_source="redirect_resolver",
                            signal_b_state="target_is_redirect",
                            evidence_nature=EvidenceNature.OBSERVED,
                            summary=f"Declared canonical target '{chain.declared_canonical}' for '{chain.source_url}' returns a redirect.",
                            recommended_reconciliation="Update canonical tag to point directly to the final 200 OK destination URL.",
                        )
                    )

                # Conflict G: Canonical Target Dead
                if chain.points_to_dead_url or chain.status == CanonicalChainStatus.POINTS_TO_DEAD_URL:
                    conflicts.append(
                        CrossSignalConflictRecord(
                            url=chain.source_url,
                            conflict_type=CrossSignalConflictType.CANONICAL_TARGET_DEAD,
                            severity=CrossSignalConflictSeverity.HIGH,
                            signal_a_source="canonical_tag",
                            signal_a_state=f"declared_canonical={chain.declared_canonical}",
                            signal_b_source="http_status",
                            signal_b_state="target_returned_error",
                            evidence_nature=EvidenceNature.OBSERVED,
                            summary=f"Declared canonical target '{chain.declared_canonical}' for '{chain.source_url}' returns 4xx/5xx or failed.",
                            recommended_reconciliation="Fix broken canonical destination or update canonical tag to a valid page.",
                        )
                    )

        # -------------------------------------------------------------------
        # Conflict J: Internal URL Discovered but Absent from Sitemap
        # Classified as a coverage discrepancy, NOT a penalty
        # -------------------------------------------------------------------
        for rec in site_crawl.crawl_records:
            if rec.status_code == 200:
                elig = site_crawl.search_eligibility.get(rec.url)
                is_indexable = (
                    elig is not None
                    and elig.indexability == IndexabilityStatus.INDEXABLE
                    and elig.canonicalization == CanonicalizationSignal.SELF_REFERENCING
                )
                if is_indexable:
                    rec_ident = rec.identity_url or UrlNormalizer.get_url_identity(rec.url)
                    if (rec.url not in sitemap_by_raw) and (rec_ident not in sitemap_by_ident):
                        missing_internal_urls.append(rec.url)
                        conflicts.append(
                            CrossSignalConflictRecord(
                                url=rec.url,
                                conflict_type=CrossSignalConflictType.INTERNAL_URL_NOT_IN_SITEMAP,
                                severity=CrossSignalConflictSeverity.LOW,
                                signal_a_source="internal_link_graph",
                                signal_a_state="crawled_indexable_200",
                                signal_b_source="sitemap",
                                signal_b_state="missing_from_sitemap",
                                evidence_nature=EvidenceNature.OBSERVED,
                                summary=f"Internal indexable URL '{rec.url}' is omitted from sitemaps (coverage discrepancy).",
                                recommended_reconciliation="Factual coverage discrepancy. Add valuable indexable internal URL to sitemap.",
                            )
                        )

        # Compute summary counts
        type_counts: Dict[str, int] = {}
        sev_counts: Dict[str, int] = {}
        for c in conflicts:
            t_key = c.conflict_type.value
            s_key = c.severity.value
            type_counts[t_key] = type_counts.get(t_key, 0) + 1
            sev_counts[s_key] = sev_counts.get(s_key, 0) + 1

        summary = SitemapReconciliationSummary(
            total_sitemaps_discovered=len(s_docs),
            total_sitemaps_parsed=len([d for d in s_docs if d.status == "SUCCESS"]),
            total_sitemap_urls_discovered=sum(d.urls_found_count for d in s_docs),
            total_unique_sitemap_urls=len(s_url_map),
            crawled_sitemap_urls_count=crawled_count,
            uncrawled_sitemap_urls_count=len(uncrawled_urls),
            internal_urls_missing_from_sitemap_count=len(missing_internal_urls),
            conflicts_count_by_type=type_counts,
            conflicts_count_by_severity=sev_counts,
            sitemap_documents=s_docs,
            sitemap_urls=s_url_map,
            conflicts=conflicts,
            uncrawled_sitemap_urls=uncrawled_urls,
            internal_urls_missing_from_sitemap=missing_internal_urls,
        )

        site_crawl.sitemap_reconciliation = summary

        # Append high-level issues to site_crawl.site_wide_issues if conflicts exist
        if type_counts.get(CrossSignalConflictType.SITEMAP_ROBOTS_BLOCKED.value, 0) > 0:
            msg = f"{type_counts[CrossSignalConflictType.SITEMAP_ROBOTS_BLOCKED.value]} sitemap URL(s) blocked by robots.txt"
            if msg not in site_crawl.site_wide_issues:
                site_crawl.site_wide_issues.append(msg)

        if type_counts.get(CrossSignalConflictType.SITEMAP_NOINDEX_CONFLICT.value, 0) > 0:
            msg = f"{type_counts[CrossSignalConflictType.SITEMAP_NOINDEX_CONFLICT.value]} sitemap URL(s) specify 'noindex' directives"
            if msg not in site_crawl.site_wide_issues:
                site_crawl.site_wide_issues.append(msg)

        if type_counts.get(CrossSignalConflictType.SITEMAP_ERROR_CONFLICT.value, 0) > 0:
            msg = f"{type_counts[CrossSignalConflictType.SITEMAP_ERROR_CONFLICT.value]} sitemap URL(s) returned 4xx/5xx errors"
            if msg not in site_crawl.site_wide_issues:
                site_crawl.site_wide_issues.append(msg)

        return summary
