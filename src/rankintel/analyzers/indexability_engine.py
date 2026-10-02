"""
Indexability & Search Eligibility Engine for RankIntel.
Evaluates multi-tier search eligibility without conflating crawlability, HTTP validity,
indexability, canonicalization, and search engine index confirmation.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    CrawlabilityStatus,
    IndexabilityStatus,
    CanonicalizationSignal,
    IndexConfirmationStatus,
    SearchEligibilityRecord,
)
from rankintel.crawler.normalizer import UrlNormalizer


class IndexabilityEngine:
    """
    Evaluates search eligibility across 5 decoupled, independent dimensions:
    1. Crawlability (robots.txt permission)
    2. HTTP Status / Server Validity
    3. Indexability Directives (Meta Robots & X-Robots-Tag)
    4. Canonicalization Target & Signal
    5. Index Confirmation Telemetry
    """

    NOINDEX_DIRECTIVES: Set[str] = {"noindex", "none"}

    @classmethod
    def parse_meta_robots(cls, raw_html: Optional[str]) -> List[str]:
        """
        Parse <meta name="robots" content="..."> directives case-insensitively.
        Returns a list of lowercase, stripped directives.
        """
        if not raw_html:
            return []

        directives: List[str] = []
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            # Find meta tags with name="robots" (case-insensitive attribute search)
            for meta in soup.find_all("meta"):
                name_attr = meta.get("name", "")
                if isinstance(name_attr, str) and name_attr.strip().lower() == "robots":
                    content = meta.get("content", "")
                    if content and isinstance(content, str):
                        for part in content.split(","):
                            clean = part.strip().lower()
                            if clean and clean not in directives:
                                directives.append(clean)
        except Exception:
            pass

        return directives

    @classmethod
    def parse_x_robots_tag(
        cls,
        headers: Optional[Union[Dict[str, Any], List[Tuple[str, str]]]]
    ) -> List[str]:
        """
        Parse X-Robots-Tag directives from HTTP response headers.
        Supports single strings, comma-separated directives, and repeated header lists.
        """
        if not headers:
            return []

        directives: List[str] = []
        raw_values: List[str] = []

        if isinstance(headers, list):
            for k, v in headers:
                if str(k).strip().lower() == "x-robots-tag" and v:
                    raw_values.append(str(v))
        elif isinstance(headers, dict):
            for k, v in headers.items():
                if str(k).strip().lower() == "x-robots-tag":
                    if isinstance(v, list):
                        for item in v:
                            if item:
                                raw_values.append(str(item))
                    elif isinstance(v, str) and v:
                        raw_values.append(v)

        for val in raw_values:
            for part in val.split(","):
                clean = part.strip().lower()
                if clean and clean not in directives:
                    directives.append(clean)

        return directives

    @classmethod
    def parse_canonical_tag(cls, raw_html: Optional[str], base_url: str) -> Optional[str]:
        """
        Parse <link rel="canonical" href="..."> from HTML.
        Resolves relative URLs to absolute URLs against base_url.
        Returns normalized absolute URL or None if missing/invalid.
        """
        if not raw_html:
            return None

        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            for link in soup.find_all("link"):
                rel_attr = link.get("rel", [])
                if isinstance(rel_attr, str):
                    rel_parts = [r.strip().lower() for r in rel_attr.split()]
                elif isinstance(rel_attr, list):
                    rel_parts = [str(r).strip().lower() for r in rel_attr]
                else:
                    rel_parts = []

                if "canonical" in rel_parts:
                    href = link.get("href", "")
                    if href and isinstance(href, str) and href.strip():
                        trimmed = href.strip()
                        resolved = urljoin(base_url, trimmed)
                        return resolved
        except Exception:
            pass

        return None

    @classmethod
    def evaluate_crawlability(
        cls,
        url: str,
        record: Optional[CrawlRecord] = None,
        robots_parser: Optional[Any] = None,
    ) -> Tuple[CrawlabilityStatus, str]:
        """
        Evaluate crawlability strictly from robots.txt crawl evidence.
        Never converts BLOCKED into NOINDEX. Zero network requests performed.
        """
        # 1. Direct crawl evidence from M6.1 crawler
        if record and record.crawl_status == CrawlStatus.BLOCKED:
            reason = record.failure_reason or "robots.txt disallow"
            return CrawlabilityStatus.BLOCKED, f"Crawl blocked by robots.txt: {reason}"

        # 2. In-memory robots parser if provided
        if robots_parser is not None:
            try:
                allowed = robots_parser.can_fetch("RankIntel/2.0", url)
                if allowed:
                    return CrawlabilityStatus.ALLOWED, "robots.txt allows crawling"
                else:
                    return CrawlabilityStatus.BLOCKED, "robots.txt disallows crawling target"
            except Exception:
                pass

        # 3. If record was successfully fetched during crawl with robots enabled
        if record and record.crawl_status == CrawlStatus.FETCHED:
            return CrawlabilityStatus.ALLOWED, "URL was crawled and permitted by robots.txt"

        # 4. Inconclusive / unverified
        return CrawlabilityStatus.UNKNOWN, "robots.txt rules unavailable or unverified"

    @classmethod
    def evaluate_indexability(
        cls,
        http_status: int,
        meta_directives: List[str],
        x_robots_directives: List[str],
        has_content: bool = True,
    ) -> Tuple[IndexabilityStatus, List[str]]:
        """
        Evaluate indexability from HTTP response code and robots directives.
        Handles case-insensitive directives, including 'none' -> NOINDEX.
        Unrelated directives like 'nofollow' do NOT trigger NOINDEX.
        """
        notes: List[str] = []

        # 1. HTTP 3xx Redirects
        if 300 <= http_status <= 399:
            notes.append(f"HTTP {http_status} redirect response")
            return IndexabilityStatus.REDIRECT, notes

        # 2. HTTP 4xx / 5xx Errors or Connection Failures
        if http_status >= 400 or (http_status == 0 and not has_content):
            status_desc = f"HTTP {http_status}" if http_status > 0 else "Connection failure"
            notes.append(f"{status_desc} response indicates non-indexable error")
            return IndexabilityStatus.ERROR, notes

        # 3. Successful 2xx responses (or valid fetched content)
        if 200 <= http_status <= 299 or (http_status == 0 and has_content):
            # Check directives for noindex or none
            has_noindex = any(d in cls.NOINDEX_DIRECTIVES for d in meta_directives)
            has_x_noindex = any(d in cls.NOINDEX_DIRECTIVES for d in x_robots_directives)

            if has_noindex:
                notes.append("Meta robots directive contains 'noindex' (or 'none')")
            if has_x_noindex:
                notes.append("X-Robots-Tag header contains 'noindex' (or 'none')")

            if has_noindex or has_x_noindex:
                return IndexabilityStatus.NOINDEX, notes

            # Successful response with no noindex
            notes.append(f"HTTP {http_status or 200} response without noindex directives")
            return IndexabilityStatus.INDEXABLE, notes

        return IndexabilityStatus.UNKNOWN, ["Insufficient evidence for indexability determination"]

    @classmethod
    def evaluate_canonicalization(
        cls,
        page_url: str,
        canonical_target: Optional[str],
        crawl_records_by_url: Optional[Dict[str, CrawlRecord]] = None,
    ) -> Tuple[CanonicalizationSignal, List[str]]:
        """
        Classify canonical signal.
        CANONICALIZED_ELSEWHERE coexists with INDEXABLE.
        Does not perform external fetches.
        """
        notes: List[str] = []

        if not canonical_target or not canonical_target.strip():
            notes.append("No canonical tag declared")
            return CanonicalizationSignal.MISSING, notes

        clean_target = canonical_target.strip()
        parsed_target = urlparse(clean_target)

        # Validate basic URL validity
        if parsed_target.scheme not in ("http", "https") or not parsed_target.netloc:
            notes.append(f"Malformed or invalid canonical target: {clean_target}")
            return CanonicalizationSignal.INVALID_TARGET, notes

        # Check self-referencing via normalized URLs
        norm_page = UrlNormalizer.normalize_for_crawl(page_url)
        norm_target = UrlNormalizer.normalize_for_crawl(clean_target)

        if norm_page == norm_target:
            notes.append("Self-referencing canonical URL")
            return CanonicalizationSignal.SELF_REFERENCING, notes

        # Check domain boundaries
        is_same = UrlNormalizer.is_same_domain(clean_target, page_url)

        # Check canonical target status in crawl dataset if available
        target_record: Optional[CrawlRecord] = None
        if crawl_records_by_url:
            target_record = (
                crawl_records_by_url.get(clean_target)
                or crawl_records_by_url.get(norm_target)
            )

        if target_record:
            if target_record.status_code >= 400 or target_record.crawl_status == CrawlStatus.FAILED:
                notes.append(
                    f"Canonical target {clean_target} is known invalid (HTTP {target_record.status_code} / {target_record.crawl_status.value})"
                )
                return CanonicalizationSignal.INVALID_TARGET, notes
            if target_record.crawl_status == CrawlStatus.REDIRECTED:
                notes.append(
                    f"Canonical target {clean_target} is a redirect target (HTTP {target_record.status_code})"
                )
                return CanonicalizationSignal.INVALID_TARGET, notes

        if is_same:
            if target_record and target_record.status_code == 200:
                notes.append(f"Canonical points to verified internal target {clean_target}")
            elif not target_record:
                notes.append(f"Canonical points to {clean_target} (target not in crawl dataset; validity unverified)")
            else:
                notes.append(f"Canonical points to {clean_target}")
            return CanonicalizationSignal.CANONICALIZED_ELSEWHERE, notes
        else:
            if target_record and target_record.status_code == 200:
                notes.append(f"Canonical targets verified cross-domain URL {clean_target}")
            elif not target_record:
                notes.append(f"Canonical targets cross-domain URL {clean_target} (target not in crawl dataset; validity unverified)")
            else:
                notes.append(f"Canonical targets cross-domain URL {clean_target}")
            return CanonicalizationSignal.CROSS_DOMAIN, notes

    @classmethod
    def evaluate_confirmation(
        cls,
        gsc_bing_telemetry: Optional[Dict[str, Any]] = None,
    ) -> Tuple[IndexConfirmationStatus, str]:
        """
        Index confirmation evaluator.
        Strictly defaults to UNKNOWN. Never infers confirmation from Google queries,
        robots.txt, canonicals, sitemaps, or HTTP 200.
        """
        if gsc_bing_telemetry and isinstance(gsc_bing_telemetry, dict):
            status = gsc_bing_telemetry.get("status")
            if status == "INDEXED":
                return IndexConfirmationStatus.CONFIRMED_INDEXED, "Confirmed indexed via authenticated telemetry"
            elif status == "NOT_INDEXED":
                return IndexConfirmationStatus.CONFIRMED_NOT_INDEXED, "Confirmed not indexed via authenticated telemetry"

        return IndexConfirmationStatus.UNKNOWN, "Index confirmation unavailable (requires authenticated search console telemetry)"

    @classmethod
    def evaluate_record(
        cls,
        record: CrawlRecord,
        robots_parser: Optional[Any] = None,
        crawl_records_by_url: Optional[Dict[str, CrawlRecord]] = None,
        inbound_links_count: int = 0,
        in_sitemap: bool = False,
        gsc_bing_telemetry: Optional[Dict[str, Any]] = None,
    ) -> SearchEligibilityRecord:
        """
        Evaluate full search eligibility for a single CrawlRecord.
        Consumes existing crawl data without making new network requests.
        """
        all_notes: List[str] = []

        # 1. Crawlability
        crawlability, c_note = cls.evaluate_crawlability(
            url=record.url,
            record=record,
            robots_parser=robots_parser,
        )
        all_notes.append(c_note)

        # 2. Directives
        meta_directives = cls.parse_meta_robots(record.raw_html)
        x_robots_directives = cls.parse_x_robots_tag(record.response_headers)

        if meta_directives:
            all_notes.append(f"Meta robots: {', '.join(meta_directives)}")
        if x_robots_directives:
            all_notes.append(f"X-Robots-Tag: {', '.join(x_robots_directives)}")

        # 3. HTTP / Indexability
        if record.crawl_status in (CrawlStatus.QUEUED, CrawlStatus.SKIPPED):
            indexability = IndexabilityStatus.UNKNOWN
            idx_notes = ["URL not crawled (queued/unvisited) — indexability unknown"]
        elif record.crawl_status == CrawlStatus.BLOCKED and not (record.raw_html and record.status_code):
            indexability = IndexabilityStatus.UNKNOWN
            idx_notes = ["Crawling blocked by robots.txt — indexability cannot be evaluated from document content"]
        else:
            has_content = bool(record.raw_html and record.raw_html.strip())
            indexability, idx_notes = cls.evaluate_indexability(
                http_status=record.status_code,
                meta_directives=meta_directives,
                x_robots_directives=x_robots_directives,
                has_content=has_content,
            )
        all_notes.extend(idx_notes)

        # 4. Canonicalization
        canonical_target = cls.parse_canonical_tag(record.raw_html, record.url)
        canonicalization, canon_notes = cls.evaluate_canonicalization(
            page_url=record.url,
            canonical_target=canonical_target,
            crawl_records_by_url=crawl_records_by_url,
        )
        all_notes.extend(canon_notes)

        # 5. Confirmation
        confirmation, conf_note = cls.evaluate_confirmation(gsc_bing_telemetry)
        all_notes.append(conf_note)

        return SearchEligibilityRecord(
            url=record.url,
            crawlability=crawlability,
            indexability=indexability,
            canonicalization=canonicalization,
            confirmation=confirmation,
            canonical_target=canonical_target,
            http_status=record.status_code,
            meta_robots_directives=meta_directives,
            x_robots_tag_directives=x_robots_directives,
            in_sitemap=in_sitemap,
            inbound_links_count=inbound_links_count,
            requires_js_to_render=False,
            evaluation_notes=all_notes,
        )

    @classmethod
    def evaluate_site(
        cls,
        site_crawl: SiteCrawlResult,
        robots_parser: Optional[Any] = None,
        sitemap_urls: Optional[Set[str]] = None,
        gsc_telemetry: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, SearchEligibilityRecord]:
        """
        Evaluate search eligibility across all records in a SiteCrawlResult.
        Computes inbound link frequencies and cross-checks canonical targets.
        Zero network operations.
        """
        # Map records by multiple keys for fast cross-lookup
        crawl_records_by_url: Dict[str, CrawlRecord] = {}
        for rec in site_crawl.crawl_records:
            crawl_records_by_url[rec.url] = rec
            crawl_records_by_url[rec.normalized_url] = rec

        # Count inbound links from discovered_links across the crawl dataset
        inbound_counts: Dict[str, int] = {}
        for rec in site_crawl.crawl_records:
            for link in rec.discovered_links:
                norm_link = UrlNormalizer.normalize_for_crawl(link)
                inbound_counts[norm_link] = inbound_counts.get(norm_link, 0) + 1

        results: Dict[str, SearchEligibilityRecord] = {}
        sitemaps_set = sitemap_urls or set()

        for rec in site_crawl.crawl_records:
            inbound_cnt = inbound_counts.get(rec.normalized_url, inbound_counts.get(rec.url, 0))
            is_in_sitemap = (rec.url in sitemaps_set) or (rec.normalized_url in sitemaps_set)
            telemetry = gsc_telemetry.get(rec.url) if gsc_telemetry else None

            eligibility = cls.evaluate_record(
                record=rec,
                robots_parser=robots_parser,
                crawl_records_by_url=crawl_records_by_url,
                inbound_links_count=inbound_cnt,
                in_sitemap=is_in_sitemap,
                gsc_bing_telemetry=telemetry,
            )
            results[rec.url] = eligibility

        site_crawl.search_eligibility = results
        return results
