"""
Crawl Frontier for RankIntel Deep Asynchronous Crawling.
Maintains the queue, visited sets, depth constraints, page ceilings, and CrawlState tracking.
"""
from __future__ import annotations
import asyncio
from typing import Dict, List, Optional, Set, Tuple
from rankintel.models.schema import (
    CrawlStatus,
    CrawlConfig,
    CrawlRecord,
    PageSummary,
    SiteCrawlResult,
)
from rankintel.crawler.normalizer import UrlNormalizer


class CrawlFrontier:
    """Thread-safe, depth-aware crawl frontier for async multi-page spidering."""

    def __init__(self, base_url: str, config: Optional[CrawlConfig] = None):
        self.base_url = base_url
        self.config = config or CrawlConfig()
        self.visited: Set[str] = set()
        self.enqueued: Set[str] = set()
        self.queue: asyncio.Queue[Tuple[str, int, Optional[str], str]] = asyncio.Queue()
        self.records: Dict[str, CrawlRecord] = {}
        self.fetched_count: int = 0
        self.duplicate_count: int = 0

    def add_url(
        self,
        url: str,
        depth: int,
        parent_url: Optional[str] = None,
        discovery_source: str = "internal_link"
    ) -> bool:
        """
        Evaluate and enqueue a discovered URL.
        Returns True if enqueued, False if rejected by boundary/depth/deduplication rules.
        """
        if not url:
            return False

        # Reject non-HTML mime types (images, pdfs, archives)
        if not UrlNormalizer.is_crawlable_mime(url):
            return False

        # Reject out-of-domain targets
        if not UrlNormalizer.is_same_domain(url, self.base_url, self.config.allowed_subdomains):
            return False

        # Depth ceiling
        if depth > self.config.max_depth:
            return False

        # Normalization
        norm_url = UrlNormalizer.normalize_for_crawl(url, parent_url)
        identity_url = UrlNormalizer.get_url_identity(url, parent_url)

        # Deduplication
        if norm_url in self.enqueued or norm_url in self.visited:
            self.duplicate_count += 1
            return False

        # Stop enqueueing if we have already far exceeded the crawl page budget
        if self.fetched_count >= self.config.max_pages:
            return False

        self.enqueued.add(norm_url)
        record = CrawlRecord(
            url=url,
            normalized_url=norm_url,
            identity_url=identity_url,
            crawl_status=CrawlStatus.QUEUED,
            depth=depth,
            parent_url=parent_url,
            discovery_source=discovery_source,
        )
        self.records[norm_url] = record
        self.queue.put_nowait((norm_url, depth, parent_url, discovery_source))
        return True

    def mark_fetched(
        self,
        norm_url: str,
        status_code: int,
        content_type: str,
        response_bytes: int,
        fetch_time_sec: float,
        discovered_links: List[str],
        raw_html: Optional[str] = None,
        retry_count: int = 0,
        response_headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record successful or finalized HTTP response."""
        self.visited.add(norm_url)
        self.fetched_count += 1
        record = self.records.get(norm_url)
        if record:
            record.crawl_status = CrawlStatus.FETCHED
            record.status_code = status_code
            record.content_type = content_type
            record.response_bytes = response_bytes
            record.fetch_time_sec = round(fetch_time_sec, 3)
            record.discovered_links = discovered_links
            record.raw_html = raw_html
            record.retry_count = retry_count
            if response_headers:
                record.response_headers = response_headers

    def mark_blocked(self, norm_url: str, reason: str = "robots.txt disallow") -> None:
        """Record URL blocked by robots.txt."""
        self.visited.add(norm_url)
        record = self.records.get(norm_url)
        if record:
            record.crawl_status = CrawlStatus.BLOCKED
            record.failure_reason = reason

    def mark_failed(
        self,
        norm_url: str,
        error: str,
        status_code: int = 0,
        retry_count: int = 0,
        response_headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record URL network failure or exception."""
        self.visited.add(norm_url)
        record = self.records.get(norm_url)
        if record:
            record.crawl_status = CrawlStatus.FAILED
            record.status_code = status_code
            record.failure_reason = error
            record.retry_count = retry_count
            if response_headers:
                record.response_headers = response_headers

    def mark_skipped(self, norm_url: str, reason: str) -> None:
        """Record URL skipped due to policy or limit."""
        self.visited.add(norm_url)
        record = self.records.get(norm_url)
        if record:
            record.crawl_status = CrawlStatus.SKIPPED
            record.failure_reason = reason

    def mark_redirected(
        self,
        norm_url: str,
        status_code: int,
        location: str,
        response_headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record URL returned a redirect."""
        self.visited.add(norm_url)
        self.fetched_count += 1
        record = self.records.get(norm_url)
        if record:
            record.crawl_status = CrawlStatus.REDIRECTED
            record.status_code = status_code
            record.failure_reason = f"Redirected to {location}"
            if response_headers:
                record.response_headers = response_headers

    def can_fetch_more(self) -> bool:
        """Check whether page limit budget has not been exceeded."""
        return self.fetched_count < self.config.max_pages

    def has_work(self) -> bool:
        """Check whether there are enqueued URLs waiting and crawl budget is remaining."""
        return not self.queue.empty() and self.fetched_count < self.config.max_pages

    def build_result(self, duration_sec: float) -> SiteCrawlResult:
        """Build structured SiteCrawlResult from all crawl records."""
        status_counts: Dict[str, int] = {}
        pages: List[PageSummary] = []
        broken_links: List[str] = []
        thin_content: List[str] = []
        missing_h1: List[str] = []
        no_meta_desc: List[str] = []
        title_counts: Dict[str, int] = {}

        for rec in self.records.values():
            s_name = rec.crawl_status.value
            status_counts[s_name] = status_counts.get(s_name, 0) + 1

            if rec.status_code >= 400 or rec.crawl_status == CrawlStatus.FAILED:
                broken_links.append(rec.url)

            # Build PageSummary if HTML was fetched
            if rec.crawl_status in (CrawlStatus.FETCHED, CrawlStatus.REDIRECTED) and rec.status_code:
                issues: List[str] = []
                if rec.status_code >= 400:
                    issues.append(f"HTTP_{rec.status_code}")

                # Quick HTML checks if raw_html exists
                title = ""
                meta_desc = ""
                h1_count = 0
                has_canonical = False
                word_count = 0

                if rec.raw_html:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(rec.raw_html, "html.parser")
                    t_tag = soup.find("title")
                    if t_tag:
                        title = t_tag.get_text().strip()
                        if title:
                            title_counts[title] = title_counts.get(title, 0) + 1

                    m_tag = soup.find("meta", attrs={"name": "description"})
                    if m_tag and m_tag.get("content"):
                        meta_desc = m_tag["content"].strip()
                    else:
                        if rec.status_code == 200:
                            no_meta_desc.append(rec.url)
                            issues.append("NO_META_DESC")

                    h1_tags = soup.find_all("h1")
                    h1_count = len(h1_tags)
                    if h1_count == 0 and rec.status_code == 200:
                        missing_h1.append(rec.url)
                        issues.append("MISSING_H1")

                    c_tag = soup.find("link", attrs={"rel": "canonical"})
                    has_canonical = bool(c_tag and c_tag.get("href"))

                    # Word count
                    for s in soup(["script", "style", "nav", "footer"]):
                        s.extract()
                    words = soup.get_text(separator=" ").split()
                    word_count = len(words)
                    if word_count < 300 and rec.status_code == 200:
                        thin_content.append(rec.url)
                        issues.append("THIN_CONTENT")

                pages.append(PageSummary(
                    url=rec.url,
                    status_code=rec.status_code or 200,
                    title=title,
                    title_length=len(title),
                    meta_desc_length=len(meta_desc),
                    h1_count=h1_count,
                    has_canonical=has_canonical,
                    word_count=word_count,
                    issues=issues,
                ))

        if self.duplicate_count > 0:
            status_counts[CrawlStatus.DUPLICATE.value] = self.duplicate_count

        duplicate_titles = [t for t, c in title_counts.items() if c > 1 and t]

        site_wide_issues: List[str] = []
        if broken_links:
            site_wide_issues.append(f"{len(broken_links)} broken response URLs (HTTP 4xx/5xx or failed)")
        if missing_h1:
            site_wide_issues.append(f"{len(missing_h1)} pages missing an H1 tag")
        if thin_content:
            site_wide_issues.append(f"{len(thin_content)} pages with thin content (<300 words)")
        if duplicate_titles:
            site_wide_issues.append(f"{len(duplicate_titles)} duplicate title tags detected across pages")
        if no_meta_desc:
            site_wide_issues.append(f"{len(no_meta_desc)} pages without a meta description")

        return SiteCrawlResult(
            pages_crawled=self.fetched_count,
            pages_with_issues=len([p for p in pages if p.issues]),
            crawl_depth=self.config.max_depth,
            crawl_duration_sec=round(duration_sec, 2),
            status_counts=status_counts,
            crawl_records=list(self.records.values()),
            pages=pages,
            site_wide_issues=site_wide_issues,
            broken_links=broken_links,
            duplicate_titles=duplicate_titles,
            missing_h1_pages=missing_h1,
            thin_content_pages=thin_content,
            pages_without_meta_desc=no_meta_desc,
        )
