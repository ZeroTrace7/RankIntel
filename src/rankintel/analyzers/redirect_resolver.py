"""
Redirect Chain Resolver for RankIntel (Milestone M6.3).
Traces multi-hop 3xx chains, loops, broken targets, and latencies from crawl evidence.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Union
from urllib.parse import urljoin

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    RedirectHop,
    RedirectChainStatus,
    RedirectChainRecord,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.analyzers.record_lookup import RecordLookupIndex


class RedirectResolver:
    """
    Deterministic redirect chain resolver operating strictly on crawl evidence.
    Traces multi-hop redirect paths, detects loops, tracks latency, and classifies chain health.
    """

    REDIRECT_STATUS_CODES: Set[int] = {301, 302, 303, 307, 308}

    @classmethod
    def extract_location(cls, record: CrawlRecord) -> Optional[str]:
        """Extract declared redirect target location from CrawlRecord evidence."""
        # 1. Direct redirect_url attribute
        if record.redirect_url and record.redirect_url.strip():
            return record.redirect_url.strip()

        # 2. Response headers (case-insensitive)
        headers = record.response_headers or {}
        for k, v in headers.items():
            if str(k).strip().lower() == "location" and v:
                if isinstance(v, list) and v:
                    return str(v[0]).strip()
                return str(v).strip()

        # 3. Fallback: Parse from failure_reason
        if record.failure_reason and record.failure_reason.startswith("Redirected to "):
            loc = record.failure_reason[len("Redirected to "):].strip()
            if loc:
                return loc

        return None

    @classmethod
    def resolve_chain(
        cls,
        initial_url: str,
        records: Union[RecordLookupIndex, List[CrawlRecord], Dict[str, CrawlRecord], SiteCrawlResult],
        max_hops: int = 10,
    ) -> RedirectChainRecord:
        """
        Trace the full redirect chain for an initial URL.
        """
        if isinstance(records, RecordLookupIndex):
            index = records
        else:
            index = RecordLookupIndex(records)

        current_url = initial_url.strip() if initial_url else ""
        hops: List[RedirectHop] = []
        visited_urls: Set[str] = set()
        notes: List[str] = []

        initial_ident = UrlNormalizer.get_url_identity(current_url)
        visited_urls.add(initial_ident)
        visited_urls.add(current_url)

        has_loop = False
        status: Optional[RedirectChainStatus] = None
        final_url = current_url

        while len(hops) < max_hops:
            rec = index.lookup(current_url)

            if rec is None:
                # Target is outside crawl boundaries or max_pages ceiling reached
                status = RedirectChainStatus.UNVERIFIED_TARGET
                final_url = current_url
                notes.append(f"Redirect target {current_url} could not be verified in crawl dataset")
                break

            is_redirect = (
                rec.crawl_status == CrawlStatus.REDIRECTED
                or rec.status_code in cls.REDIRECT_STATUS_CODES
            )

            if not is_redirect:
                # Terminal destination reached!
                final_url = rec.url or current_url
                if rec.status_code == 200:
                    if len(hops) > 1:
                        status = RedirectChainStatus.MULTI_HOP
                        notes.append(f"Resolved to 200 OK after {len(hops)} hops (multi-hop redirect chain)")
                    elif len(hops) == 1:
                        status = RedirectChainStatus.RESOLVED
                        notes.append("Clean 1-hop redirect resolved to 200 OK")
                    else:
                        status = RedirectChainStatus.RESOLVED
                        notes.append("URL returned 200 OK (no redirects)")
                elif rec.status_code >= 400 or rec.crawl_status == CrawlStatus.FAILED:
                    status = RedirectChainStatus.BROKEN_TARGET
                    notes.append(f"Redirect chain terminates at broken response (HTTP {rec.status_code} / {rec.crawl_status.value})")
                else:
                    status = RedirectChainStatus.RESOLVED
                    notes.append(f"Redirect chain reached terminal status HTTP {rec.status_code}")
                break

            # It is a 3xx redirect. Extract location header
            raw_loc = cls.extract_location(rec)
            if not raw_loc:
                status = RedirectChainStatus.MISSING_LOCATION
                final_url = current_url
                notes.append(f"HTTP {rec.status_code} redirect missing Location header")
                break

            next_url = urljoin(current_url, raw_loc.strip())
            latency_ms = round(rec.fetch_time_sec * 1000, 2) if rec.fetch_time_sec > 0 else None

            hop = RedirectHop(
                url=current_url,
                status_code=rec.status_code,
                location=next_url,
                latency_ms=latency_ms,
            )
            hops.append(hop)

            # Check for loop / cycle
            next_ident = UrlNormalizer.get_url_identity(next_url)
            if next_ident in visited_urls or next_url in visited_urls:
                has_loop = True
                status = RedirectChainStatus.LOOP
                final_url = next_url
                notes.append(f"Redirect loop detected: {current_url} -> {next_url}")
                break

            visited_urls.add(next_ident)
            visited_urls.add(next_url)
            current_url = next_url

        if status is None and len(hops) >= max_hops:
            status = RedirectChainStatus.EXCEEDED_MAX_HOPS
            final_url = current_url
            notes.append(f"Redirect chain exceeded safety hop limit of {max_hops} hops")

        # Sum latency across hops where recorded
        hop_latencies = [h.latency_ms for h in hops if h.latency_ms is not None]
        total_latency = round(sum(hop_latencies), 2) if hop_latencies else None

        return RedirectChainRecord(
            initial_url=initial_url,
            final_url=final_url,
            total_hops=len(hops),
            hops=hops,
            has_loop=has_loop,
            status=status or RedirectChainStatus.RESOLVED,
            total_latency_ms=total_latency,
            notes=notes,
        )

    @classmethod
    def resolve_site(
        cls,
        site_crawl: SiteCrawlResult,
        max_hops: int = 10,
    ) -> Dict[str, RedirectChainRecord]:
        """
        Resolve redirect chains for all redirecting records in a SiteCrawlResult.
        """
        index = RecordLookupIndex(site_crawl.crawl_records)
        chains: Dict[str, RedirectChainRecord] = {}

        for rec in site_crawl.crawl_records:
            if rec.crawl_status == CrawlStatus.REDIRECTED or rec.status_code in cls.REDIRECT_STATUS_CODES:
                chain = cls.resolve_chain(rec.url, index, max_hops=max_hops)
                chains[rec.url] = chain

        site_crawl.redirect_chains = chains
        return chains
