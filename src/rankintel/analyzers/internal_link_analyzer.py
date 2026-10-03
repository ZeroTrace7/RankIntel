"""
Site Internal Link Analyzer — Cross-page multi-page crawl internal link intelligence (Phase 8.3).
Analyzes internal link graph topology, anchor text distributions, structural connectivity conditions,
and link concentration without redundant network fetches or arbitrary scoring.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from urllib.parse import urlsplit

from rankintel.models.schema import (
    SiteCrawlResult,
    CrawlRecord,
    CrawlStatus,
    LinkClassification,
    DiscoveredLinkItem,
    GenericAnchorOccurrence,
    AnchorAmbiguityFinding,
    BrokenInternalLinkItem,
    LinkStructuralFindingType,
    LinkStructuralFinding,
    LinkConcentrationTelemetry,
    SiteAnchorIntelligence,
    InternalLinkEvidence,
    OutlinkDiscoveryStatus,
    PageLinkAnalysisRecord,
    SiteInternalLinkIntelligence,
    EvidenceNature,
)
from rankintel.engines.internal_link_engine import InternalLinkEngine
from rankintel.analyzers.link_graph_engine import InternalLinkGraphEngine
from rankintel.analyzers.record_lookup import RecordLookupIndex


class SiteInternalLinkAnalyzer:
    """
    Analyzes site-wide internal link topology, anchor text patterns,
    and connectivity conditions from CrawlRecord evidence.
    Reuses existing InternalLinkGraphEngine without duplicate graph abstractions.
    """

    @classmethod
    def analyze_site(
        cls,
        site_crawl: SiteCrawlResult,
        root_url: Optional[str] = None,
        allow_subdomains: bool = False,
    ) -> SiteInternalLinkIntelligence:
        """
        Analyze all internal links across crawled pages in site_crawl.
        Populates and attaches site_crawl.internal_link_intelligence.
        """
        if not site_crawl:
            empty_intel = SiteInternalLinkIntelligence()
            return empty_intel

        # Ensure any records with raw_html but empty discovered_links have their links extracted for graph building
        for rec in site_crawl.crawl_records:
            if not rec.discovered_links and rec.raw_html:
                extracted = InternalLinkEngine.extract_links_from_html(
                    raw_html=rec.raw_html,
                    base_url=rec.url,
                    allow_subdomains=allow_subdomains,
                )
                rec.discovered_links = [l.target_url for l in extracted]

        # Reuse existing InternalLinkGraphEngine to build/retrieve the graph
        G, resolved_root, graph_summary = InternalLinkGraphEngine.build_graph(
            records=site_crawl,
            root_url=root_url,
            allow_subdomains=allow_subdomains,
        )
        # Ensure site_crawl.link_graph is synchronized
        site_crawl.link_graph = graph_summary
        site_crawl.orphan_pages = list(graph_summary.potential_orphans)

        lookup = RecordLookupIndex(site_crawl.crawl_records)

        # Lookup map for crawled target statuses (to detect broken internal links)
        # identity_url -> CrawlRecord
        crawled_record_map: Dict[str, CrawlRecord] = {}
        for rec in site_crawl.crawl_records:
            ident = rec.identity_url or InternalLinkGraphEngine.normalize_node_url(rec.url, lookup_index=lookup)
            crawled_record_map[ident] = rec
            if rec.url:
                crawled_record_map[rec.url] = rec

        page_evidence: Dict[str, InternalLinkEvidence] = {}
        all_internal_links: List[DiscoveredLinkItem] = []

        # Anchor tracking:
        # anchor_norm -> { target_identity_url -> list of source_urls }
        anchor_to_destinations: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        # raw anchor text -> total count
        raw_anchor_counts: Dict[str, int] = defaultdict(int)
        empty_anchor_sources: Set[str] = set()
        generic_counts: Dict[Tuple[str, str], int] = defaultdict(int)

        # Overlapping observable link analysis tracking (for benchmarking & comparison)
        total_inlinks_by_target: Dict[str, int] = defaultdict(int)
        total_outlinks_by_source: Dict[str, int] = defaultdict(int)
        inlink_anchors_by_target: Dict[str, List[str]] = defaultdict(list)

        broken_links_list: List[BrokenInternalLinkItem] = []
        broken_link_keys: Set[Tuple[str, str]] = set()

        # Step 1: Extract links and anchor semantics per page
        for rec in site_crawl.crawl_records:
            if not rec.url:
                continue

            source_id = InternalLinkGraphEngine.normalize_node_url(
                rec.url,
                base_url=resolved_root,
                lookup_index=lookup,
            )

            # Extract links from raw_html if present, else fallback to rec.discovered_links
            if rec.raw_html:
                page_links = InternalLinkEngine.extract_links_from_html(
                    raw_html=rec.raw_html,
                    base_url=rec.url,
                    allow_subdomains=allow_subdomains,
                    lookup_index=lookup,
                )
            elif rec.discovered_links:
                page_links = []
                for dl in rec.discovered_links:
                    cls_link = InternalLinkGraphEngine.classify_link(
                        dl, base_url=rec.url, allow_subdomains=allow_subdomains
                    )
                    norm_dl = InternalLinkGraphEngine.normalize_node_url(
                        dl, base_url=rec.url, lookup_index=lookup
                    )
                    page_links.append(DiscoveredLinkItem(
                        source_url=rec.url,
                        target_url=dl,
                        target_identity_url=norm_dl or dl,
                        anchor_text="",
                        is_empty_anchor=True,
                        link_classification=cls_link,
                    ))
            else:
                page_links = []

            # Single-page evaluation
            node_inbound = graph_summary.nodes.get(source_id).inbound_internal_count if source_id in graph_summary.nodes else None
            node_depth = graph_summary.nodes.get(source_id).click_depth if source_id in graph_summary.nodes else rec.depth

            page_ev = InternalLinkEngine.evaluate(
                raw_html=rec.raw_html,
                url=rec.url,
                allow_subdomains=allow_subdomains,
                crawl_depth=node_depth,
                inbound_internal_count=node_inbound,
            )
            page_evidence[rec.url] = page_ev

            # Aggregate internal links and track anchors
            for item in page_links:
                if item.link_classification == LinkClassification.INTERNAL:
                    all_internal_links.append(item)
                    target_id = item.target_identity_url
                    total_inlinks_by_target[target_id] += 1
                    total_outlinks_by_source[source_id] += 1
                    if item.anchor_text and not item.is_empty_anchor:
                        inlink_anchors_by_target[target_id].append(item.anchor_text.strip())

                    # Check for broken internal link targets
                    matched_rec = crawled_record_map.get(target_id) or crawled_record_map.get(item.target_url)
                    if matched_rec:
                        is_broken = (
                            (matched_rec.status_code and matched_rec.status_code >= 400)
                            or matched_rec.crawl_status == CrawlStatus.FAILED
                        )
                        if is_broken:
                            b_key = (rec.url, item.target_url)
                            if b_key not in broken_link_keys:
                                broken_link_keys.add(b_key)
                                broken_links_list.append(BrokenInternalLinkItem(
                                    source_url=rec.url,
                                    target_url=item.target_url,
                                    anchor_text=item.anchor_text,
                                    status_code=matched_rec.status_code if matched_rec.status_code > 0 else None,
                                    failure_reason=matched_rec.failure_reason or (f"HTTP {matched_rec.status_code}" if matched_rec.status_code else "Fetch failed"),
                                ))

                    # Anchor tracking
                    if item.is_empty_anchor:
                        empty_anchor_sources.add(rec.url)
                    else:
                        norm_anchor = InternalLinkEngine.normalize_anchor_text(item.anchor_text)
                        if norm_anchor:
                            anchor_to_destinations[norm_anchor][target_id].append(rec.url)
                            raw_anchor_counts[item.anchor_text] += 1

                            if InternalLinkEngine.is_generic_anchor(item.anchor_text):
                                generic_counts[(item.anchor_text, target_id)] += 1

        # Step 2: Build Anchor Intelligence
        generic_occurrences: List[GenericAnchorOccurrence] = [
            GenericAnchorOccurrence(anchor_text=k[0], target_url=k[1], count=c)
            for k, c in sorted(generic_counts.items(), key=lambda item: item[1], reverse=True)
        ]

        # Detect conflicting / ambiguous anchor destinations
        ambiguous_anchors: List[AnchorAmbiguityFinding] = []
        for norm_anc, dests in anchor_to_destinations.items():
            # If the same normalized anchor text points to 2 or more distinct destination URLs
            if len(dests) > 1:
                dest_list = sorted(list(dests.keys()))
                all_sources = sorted(list({src for src_list in dests.values() for src in src_list}))
                tot_occurrences = sum(len(src_list) for src_list in dests.values())
                ambiguous_anchors.append(AnchorAmbiguityFinding(
                    anchor_text=norm_anc,
                    target_urls=dest_list,
                    source_pages=all_sources[:5],
                    total_occurrences=tot_occurrences,
                    observation=f"Anchor phrase '{norm_anc}' points to {len(dest_list)} distinct destination URLs across the site.",
                ))
        ambiguous_anchors.sort(key=lambda a: a.total_occurrences, reverse=True)

        sorted_top_anchors = sorted(raw_anchor_counts.items(), key=lambda item: item[1], reverse=True)[:15]

        anchor_intel = SiteAnchorIntelligence(
            total_anchors_observed=len(all_internal_links),
            unique_anchor_texts_count=len(raw_anchor_counts),
            empty_anchors_count=sum(1 for l in all_internal_links if l.is_empty_anchor),
            empty_anchor_sources=sorted(list(empty_anchor_sources)),
            generic_anchors_count=sum(c for c in generic_counts.values()),
            generic_anchor_occurrences=generic_occurrences[:15],
            conflicting_anchors_count=len(ambiguous_anchors),
            conflicting_anchors=ambiguous_anchors[:10],
            top_anchor_texts=sorted_top_anchors,
        )

        # Step 3: Extract graph adjacency and topology metrics from existing G
        inlink_sources: Dict[str, List[str]] = {}
        outlink_targets: Dict[str, List[str]] = {}
        inlink_counts: Dict[str, int] = {}
        outlink_counts: Dict[str, int] = {}
        crawl_depth_map: Dict[str, Optional[int]] = {}

        for node_id in G.nodes():
            preds = [p for p in G.predecessors(node_id) if p != node_id]
            succs = [s for s in G.successors(node_id) if s != node_id]
            inlink_sources[node_id] = sorted(preds)
            outlink_targets[node_id] = sorted(succs)
            inlink_counts[node_id] = len(preds)
            outlink_counts[node_id] = len(succs)
            node_model = graph_summary.nodes.get(node_id)
            crawl_depth_map[node_id] = node_model.click_depth if node_model else None

        # Step 4: Identify structural conditions with strict partial-crawl semantics
        pages_zero_inlinks: List[str] = []
        pages_weak_inlinks: List[str] = []
        dead_ends: List[str] = []
        deep_pages: List[str] = []
        findings: List[LinkStructuralFinding] = []

        total_pages_in_crawl = len(site_crawl.crawl_records)

        for node_id, node_model in graph_summary.nodes.items():
            is_root = bool(resolved_root and node_id == resolved_root)

            # Condition 1: Zero discovered internal incoming links (within analyzed crawl)
            if not is_root and node_model.inbound_internal_count == 0 and node_model.crawl_state.value == "CRAWLED":
                pages_zero_inlinks.append(node_id)
                findings.append(LinkStructuralFinding(
                    finding_type=LinkStructuralFindingType.NO_DISCOVERED_INCOMING_LINKS,
                    affected_url=node_id,
                    evidence=f"0 discovered internal incoming links in analyzed crawl of {total_pages_in_crawl} pages",
                    observation="No internal incoming links to this crawled page were observed in the analyzed crawl graph.",
                    recommendation="If this page is intended to be discoverable by search crawlers, consider adding contextual internal links from parent or related pages.",
                ))

            # Condition 2: Limited incoming connectivity (1 discovered internal source)
            elif not is_root and node_model.inbound_internal_count == 1 and node_model.crawl_state.value == "CRAWLED":
                pages_weak_inlinks.append(node_id)
                src_page = inlink_sources.get(node_id, ["unknown"])[0] if inlink_sources.get(node_id) else "unknown"
                findings.append(LinkStructuralFinding(
                    finding_type=LinkStructuralFindingType.LIMITED_CONNECTIVITY,
                    affected_url=node_id,
                    evidence=f"1 discovered internal source ({src_page})",
                    observation="Limited internal connectivity observed within the analyzed crawl (linked from only 1 discovered page).",
                    recommendation="Review whether additional cross-linking from related content or category navigation would aid discovery.",
                ))

            # Condition 3: Dead ends (0 outbound internal links)
            if node_model.outbound_internal_count == 0 and node_model.crawl_state.value == "CRAWLED":
                dead_ends.append(node_id)
                findings.append(LinkStructuralFinding(
                    finding_type=LinkStructuralFindingType.ZERO_OUTLINKS,
                    affected_url=node_id,
                    evidence="0 outbound internal links to other pages",
                    observation="Page acts as a terminal node in the observed crawl graph with zero links pointing to other internal pages.",
                    recommendation="Consider providing relevant navigation, related links, or a primary CTA to guide visitors and crawlers forward.",
                ))

            # Condition 4: Deep click depth (> 3 clicks from root) — neutral topology telemetry
            if node_model.click_depth is not None and node_model.click_depth > 3:
                deep_pages.append(node_id)
                findings.append(LinkStructuralFinding(
                    finding_type=LinkStructuralFindingType.DEEP_CLICK_DEPTH,
                    affected_url=node_id,
                    evidence=f"Observed at crawl depth {node_model.click_depth}",
                    observation=f"Page is reached at crawl depth {node_model.click_depth} (>3 clicks from seed) via observed crawl paths.",
                    recommendation="Verify whether this page is intended to be hierarchically deep or if key navigation links could improve discovery path length.",
                ))

        # Condition 5: Broken internal link targets
        for broken in broken_links_list:
            findings.append(LinkStructuralFinding(
                finding_type=LinkStructuralFindingType.BROKEN_TARGET,
                affected_url=broken.target_url,
                evidence=f"Linked from `{broken.source_url}` (returned {broken.failure_reason})",
                observation=f"Internal link with anchor '{broken.anchor_text}' targets a page verified as failing/erroring in crawl evidence.",
                recommendation="Update or remove the hyperlink target to point to a valid, live internal URL.",
            ))

        # Condition 6: Ambiguous / conflicting destination anchors
        for amb in ambiguous_anchors[:5]:
            findings.append(LinkStructuralFinding(
                finding_type=LinkStructuralFindingType.AMBIGUOUS_ANCHOR,
                affected_url=amb.target_urls[0],
                evidence=f"Anchor phrase '{amb.anchor_text}' used for {len(amb.target_urls)} different destinations",
                observation=f"Identical anchor text '{amb.anchor_text}' points to multiple distinct destinations: {', '.join(amb.target_urls[:3])}.",
                recommendation="Use distinct, descriptive anchor text for each unique destination to provide clear topical signals to search engines.",
            ))

        # Step 5: Link Concentration Telemetry
        # Ranked by unique inlink count
        sorted_by_inlinks = sorted(inlink_counts.items(), key=lambda item: item[1], reverse=True)
        top_linked = [(u, c) for u, c in sorted_by_inlinks[:10] if c > 0]

        total_internal_links_count = len(all_internal_links)
        unique_edges_count = G.number_of_edges()

        top_5_inlinks_sum = sum(c for _, c in top_linked[:5])
        top_5_concentration = (
            round((top_5_inlinks_sum / total_internal_links_count) * 100.0, 1)
            if total_internal_links_count > 0
            else 0.0
        )

        concentration_telemetry = LinkConcentrationTelemetry(
            total_internal_links=total_internal_links_count,
            unique_internal_edges=unique_edges_count,
            top_linked_pages=top_linked,
            top_5_concentration_pct=top_5_concentration,
        )

        # Step 6: Build normalized PageLinkAnalysisRecord for observable link analysis comparison
        page_link_records: Dict[str, PageLinkAnalysisRecord] = {}
        for node_id in G.nodes():
            node_model = graph_summary.nodes.get(node_id)
            crawled_rec = crawled_record_map.get(node_id)
            is_crawled = bool(
                (node_model and node_model.crawl_state.value == "CRAWLED")
                or (crawled_rec and crawled_rec.crawl_status == CrawlStatus.FETCHED)
            )

            # Determine outlink discovery status respecting strict partial-crawl semantics
            if not is_crawled:
                discovery_status = OutlinkDiscoveryStatus.UNVERIFIED
            elif outlink_counts.get(node_id, 0) == 0:
                discovery_status = OutlinkDiscoveryStatus.NO_DISCOVERED_OUTLINKS
            else:
                discovery_status = OutlinkDiscoveryStatus.HAS_DISCOVERED_OUTLINKS

            sample_anchors = sorted(list({a for a in inlink_anchors_by_target.get(node_id, []) if a}))[:5]

            page_link_records[node_id] = PageLinkAnalysisRecord(
                url=node_id,
                crawl_depth=crawl_depth_map.get(node_id),
                inlinks_count=total_inlinks_by_target.get(node_id, inlink_counts.get(node_id, 0)),
                unique_inlinks_count=inlink_counts.get(node_id, 0),
                outlinks_count=total_outlinks_by_source.get(node_id, outlink_counts.get(node_id, 0)),
                unique_outlinks_count=outlink_counts.get(node_id, 0),
                outlink_discovery_status=discovery_status,
                sample_inlink_sources=inlink_sources.get(node_id, [])[:5],
                sample_outlink_targets=outlink_targets.get(node_id, [])[:5],
                sample_inlink_anchors=sample_anchors,
            )

        intel = SiteInternalLinkIntelligence(
            total_pages_evaluated=len(site_crawl.crawl_records),
            total_internal_links_discovered=total_internal_links_count,
            total_unique_internal_edges=unique_edges_count,
            pages_with_zero_inlinks=pages_zero_inlinks,
            pages_with_weak_inlinks=pages_weak_inlinks,
            dead_end_pages=dead_ends,
            deep_pages=deep_pages,
            broken_internal_links_count=len(broken_links_list),
            broken_internal_links=broken_links_list,
            anchor_intelligence=anchor_intel,
            link_concentration=concentration_telemetry,
            structural_findings=findings,
            inlink_sources_by_page=inlink_sources,
            outlink_targets_by_page=outlink_targets,
            inlink_counts_by_page=inlink_counts,
            outlink_counts_by_page=outlink_counts,
            crawl_depth_by_page=crawl_depth_map,
            page_internal_link_evidence=page_evidence,
            page_link_records=page_link_records,
        )

        site_crawl.internal_link_intelligence = intel
        return intel
