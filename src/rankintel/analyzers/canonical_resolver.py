"""
Canonical Chain Resolver for RankIntel (Milestone M6.3).
Traces advisory canonical paths, multi-hop chains, loops, and redirect targets.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Set, Union
from urllib.parse import urlparse

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    CanonicalChainStatus,
    CanonicalChainRecord,
    RedirectChainRecord,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.analyzers.record_lookup import RecordLookupIndex
from rankintel.analyzers.indexability_engine import IndexabilityEngine


class CanonicalResolver:
    """
    Deterministic canonical chain resolver operating strictly on crawl evidence.
    Traces advisory canonical links without conflating canonicalization with indexability,
    and explicitly keeps canonical relationships distinct from redirect relationships.
    """

    @classmethod
    def resolve_chain(
        cls,
        source_url: str,
        records: Union[RecordLookupIndex, List[CrawlRecord], Dict[str, CrawlRecord], SiteCrawlResult],
        redirect_chains: Optional[Dict[str, RedirectChainRecord]] = None,
        max_hops: int = 10,
    ) -> CanonicalChainRecord:
        """
        Trace the canonical relationship chain starting from source_url.
        """
        if isinstance(records, RecordLookupIndex):
            index = records
        else:
            index = RecordLookupIndex(records)

        source_rec = index.lookup(source_url)
        notes: List[str] = []

        if source_rec is None:
            return CanonicalChainRecord(
                source_url=source_url,
                declared_canonical=None,
                final_canonical=None,
                total_hops=0,
                has_loop=False,
                points_to_redirect=False,
                points_to_dead_url=False,
                status=CanonicalChainStatus.UNVERIFIED_TARGET,
                hops=[source_url],
                notes=[f"Source URL {source_url} not found in crawl dataset"],
            )

        declared_target = IndexabilityEngine.parse_canonical_tag(source_rec.raw_html, source_rec.url)

        if not declared_target:
            return CanonicalChainRecord(
                source_url=source_url,
                declared_canonical=None,
                final_canonical=None,
                total_hops=0,
                has_loop=False,
                points_to_redirect=False,
                points_to_dead_url=False,
                status=CanonicalChainStatus.MISSING,
                hops=[source_url],
                notes=["No canonical tag declared"],
            )

        clean_target = declared_target.strip()
        parsed_target = urlparse(clean_target)
        if parsed_target.scheme not in ("http", "https") or not parsed_target.netloc:
            return CanonicalChainRecord(
                source_url=source_url,
                declared_canonical=clean_target,
                final_canonical=None,
                total_hops=1,
                has_loop=False,
                points_to_redirect=False,
                points_to_dead_url=False,
                status=CanonicalChainStatus.INVALID_TARGET,
                hops=[source_url, clean_target],
                notes=[f"Malformed canonical target URL: {clean_target}"],
            )

        # Self-referencing check
        source_ident = UrlNormalizer.get_url_identity(source_url)
        target_ident = UrlNormalizer.get_url_identity(clean_target)
        if source_ident == target_ident:
            return CanonicalChainRecord(
                source_url=source_url,
                declared_canonical=clean_target,
                final_canonical=clean_target,
                total_hops=0,
                has_loop=False,
                points_to_redirect=False,
                points_to_dead_url=False,
                status=CanonicalChainStatus.SELF_REFERENCING,
                hops=[source_url],
                notes=["Self-referencing canonical URL"],
            )

        # Canonical points elsewhere! Trace the chain
        current_canonical = clean_target
        canonical_hops = [source_url, clean_target]
        visited: Set[str] = {source_ident, target_ident}
        has_loop = False
        points_to_redirect = False
        points_to_dead = False
        chain_status: Optional[CanonicalChainStatus] = None

        while (len(canonical_hops) - 1) < max_hops:
            target_rec = index.lookup(current_canonical)

            if target_rec is None:
                chain_status = CanonicalChainStatus.UNVERIFIED_TARGET
                notes.append(f"Canonical target {current_canonical} not present in crawl dataset; validity unverified")
                break

            # Check if canonical target is a redirect
            is_redirect = (
                target_rec.crawl_status == CrawlStatus.REDIRECTED
                or (300 <= target_rec.status_code <= 399)
            )
            if is_redirect:
                points_to_redirect = True
                chain_status = CanonicalChainStatus.POINTS_TO_REDIRECT
                notes.append(f"Canonical points to redirected URL {current_canonical} (HTTP {target_rec.status_code})")

                # Resolve final destination of the redirect if available
                final_dest = None
                if redirect_chains:
                    chain_rec = redirect_chains.get(current_canonical) or redirect_chains.get(target_rec.url)
                    if chain_rec:
                        final_dest = chain_rec.final_url

                if not final_dest:
                    # Fallback to direct location header or failure reason
                    loc = (
                        target_rec.redirect_url
                        or (target_rec.response_headers.get("location") if target_rec.response_headers else None)
                    )
                    if loc:
                        from urllib.parse import urljoin
                        final_dest = urljoin(current_canonical, str(loc))
                    else:
                        final_dest = current_canonical

                current_canonical = final_dest
                break

            # Check if canonical target is dead / error
            if target_rec.status_code >= 400 or target_rec.crawl_status == CrawlStatus.FAILED:
                points_to_dead = True
                chain_status = CanonicalChainStatus.POINTS_TO_DEAD_URL
                notes.append(f"Canonical target {current_canonical} returns error (HTTP {target_rec.status_code} / {target_rec.crawl_status.value})")
                break

            # Target is 200 OK: check target's declared canonical tag
            next_target = IndexabilityEngine.parse_canonical_tag(target_rec.raw_html, target_rec.url)
            if not next_target:
                # Target has no canonical tag; terminates cleanly at target
                notes.append(f"Canonical target {current_canonical} is valid 200 OK with no conflicting canonical")
                break

            clean_next = next_target.strip()
            next_ident = UrlNormalizer.get_url_identity(clean_next)
            curr_ident = UrlNormalizer.get_url_identity(current_canonical)

            if next_ident == curr_ident:
                # Target has self-referencing canonical; terminates cleanly at target
                notes.append(f"Canonical target {current_canonical} is valid 200 OK with self-referencing canonical")
                break

            # Target declares yet another canonical: chain continuation!
            if next_ident in visited or clean_next in visited:
                has_loop = True
                chain_status = CanonicalChainStatus.LOOP
                canonical_hops.append(clean_next)
                current_canonical = clean_next
                notes.append(f"Canonical loop detected: {canonical_hops[-2]} -> {clean_next}")
                break

            visited.add(next_ident)
            canonical_hops.append(clean_next)
            current_canonical = clean_next

        total_hops = len(canonical_hops) - 1

        if chain_status is None:
            if total_hops == 1:
                chain_status = CanonicalChainStatus.RESOLVED
                notes.append(f"Advisory canonical points to internal target {clean_target}")
            else:
                chain_status = CanonicalChainStatus.CHAIN
                notes.append(f"Multi-hop canonical chain detected across {total_hops} hops: {' -> '.join(canonical_hops)}")

        return CanonicalChainRecord(
            source_url=source_url,
            declared_canonical=clean_target,
            final_canonical=current_canonical,
            total_hops=total_hops,
            has_loop=has_loop,
            points_to_redirect=points_to_redirect,
            points_to_dead_url=points_to_dead,
            status=chain_status,
            hops=canonical_hops,
            notes=notes,
        )

    @classmethod
    def resolve_site(
        cls,
        site_crawl: SiteCrawlResult,
        redirect_chains: Optional[Dict[str, RedirectChainRecord]] = None,
        max_hops: int = 10,
    ) -> Dict[str, CanonicalChainRecord]:
        """
        Resolve canonical chains for all pages in a SiteCrawlResult.
        """
        index = RecordLookupIndex(site_crawl.crawl_records)
        chains: Dict[str, CanonicalChainRecord] = {}

        for rec in site_crawl.crawl_records:
            if rec.raw_html:
                chain = cls.resolve_chain(rec.url, index, redirect_chains=redirect_chains, max_hops=max_hops)
                chains[rec.url] = chain

        site_crawl.canonical_chains = chains
        return chains
