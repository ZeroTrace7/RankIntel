"""
Asynchronous and Synchronous Sitemap Fetcher for RankIntel.
Recursively traverses sitemap indexes with loop detection, depth constraints,
and strict robots.txt adherence.
"""
from __future__ import annotations
import asyncio
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx

from rankintel.models.schema import (
    SitemapFormat,
    SitemapFetchStatus,
    SitemapDocumentRecord,
    SitemapUrlRecord,
)
from rankintel.sitemaps.config import SitemapConfig
from rankintel.sitemaps.parser import SitemapParser
from rankintel.crawler.normalizer import UrlNormalizer


class SitemapFetcher:
    """Production recursive sitemap traversal client."""

    def __init__(
        self,
        config: Optional[SitemapConfig] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.config = config or SitemapConfig()
        self.transport = transport

    def fetch_sitemaps_sync(
        self,
        sitemap_urls: List[str],
        robots_parser: Optional[Any] = None,
    ) -> Tuple[List[SitemapDocumentRecord], Dict[str, SitemapUrlRecord]]:
        """Synchronous wrapper for recursive sitemap fetching."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run, self.fetch_sitemaps(sitemap_urls, robots_parser=robots_parser)
                ).result()
        else:
            return asyncio.run(self.fetch_sitemaps(sitemap_urls, robots_parser=robots_parser))

    async def fetch_sitemaps(
        self,
        sitemap_urls: List[str],
        robots_parser: Optional[Any] = None,
    ) -> Tuple[List[SitemapDocumentRecord], Dict[str, SitemapUrlRecord]]:
        """
        Recursively fetch and parse sitemap documents and sitemap indexes.
        Returns:
            (documents_list, url_records_by_identity)
        """
        documents: List[SitemapDocumentRecord] = []
        url_records: Dict[str, SitemapUrlRecord] = {}
        visited_normalized: Set[str] = set()

        queue: deque[Tuple[str, int]] = deque((url.strip(), 0) for url in sitemap_urls if url.strip())

        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/xml,text/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(
            headers=headers,
            timeout=self.config.timeout_sec,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            while queue and len(documents) < self.config.max_sitemaps:
                curr_url, depth = queue.popleft()

                # 1. Depth check
                if depth > self.config.max_depth:
                    documents.append(
                        SitemapDocumentRecord(
                            url=curr_url,
                            status=SitemapFetchStatus.MAX_DEPTH_EXCEEDED,
                            depth=depth,
                            error_message=f"Exceeded maximum sitemap nesting depth ({self.config.max_depth})",
                        )
                    )
                    continue

                # 2. Cycle / loop detection
                norm_url = UrlNormalizer.normalize_for_crawl(curr_url)
                if norm_url in visited_normalized:
                    documents.append(
                        SitemapDocumentRecord(
                            url=curr_url,
                            status=SitemapFetchStatus.LOOP_DETECTED,
                            depth=depth,
                            error_message="Circular loop detected in sitemap index hierarchy",
                        )
                    )
                    continue
                visited_normalized.add(norm_url)

                # 3. Robots.txt check for sitemap URL itself
                if self.config.respect_robots_txt and robots_parser is not None:
                    try:
                        allowed = robots_parser.can_fetch(self.config.user_agent, curr_url)
                        if not allowed:
                            documents.append(
                                SitemapDocumentRecord(
                                    url=curr_url,
                                    status=SitemapFetchStatus.BLOCKED_BY_ROBOTS,
                                    depth=depth,
                                    error_message="Sitemap URL is disallowed under robots.txt rules",
                                )
                            )
                            continue
                    except Exception:
                        pass

                # 4. HTTP Fetch
                t0 = time.time()
                resp = None
                try:
                    resp = await client.get(curr_url)
                    dur = round(time.time() - t0, 3)
                except httpx.TimeoutException:
                    documents.append(
                        SitemapDocumentRecord(
                            url=curr_url,
                            status=SitemapFetchStatus.CONNECTION_FAILED,
                            depth=depth,
                            fetch_time_sec=round(time.time() - t0, 3),
                            error_message="Connection timeout while fetching sitemap",
                        )
                    )
                    continue
                except httpx.RequestError as req_err:
                    documents.append(
                        SitemapDocumentRecord(
                            url=curr_url,
                            status=SitemapFetchStatus.CONNECTION_FAILED,
                            depth=depth,
                            fetch_time_sec=round(time.time() - t0, 3),
                            error_message=f"Network error: {req_err}",
                        )
                    )
                    continue

                # 5. Handle HTTP status code
                if resp.status_code != 200:
                    documents.append(
                        SitemapDocumentRecord(
                            url=curr_url,
                            status=SitemapFetchStatus.HTTP_ERROR,
                            status_code=resp.status_code,
                            depth=depth,
                            fetch_time_sec=dur,
                            error_message=f"HTTP {resp.status_code} returned for sitemap",
                        )
                    )
                    continue

                # 6. Parse sitemap body
                fmt, parsed_urls, child_sitemaps, parse_err = SitemapParser.parse_sitemap(
                    content=resp.content,
                    source_url=curr_url,
                    max_size_bytes=self.config.max_size_bytes,
                )

                if fmt in (SitemapFormat.HTML_ERROR_PAGE, SitemapFormat.MALFORMED):
                    doc_status = SitemapFetchStatus.MALFORMED_CONTENT
                else:
                    doc_status = SitemapFetchStatus.SUCCESS

                doc_rec = SitemapDocumentRecord(
                    url=curr_url,
                    status=doc_status,
                    format=fmt,
                    status_code=resp.status_code,
                    fetch_time_sec=dur,
                    urls_found_count=len(parsed_urls),
                    child_sitemaps_count=len(child_sitemaps),
                    child_sitemaps=child_sitemaps,
                    error_message=parse_err,
                    depth=depth,
                )
                documents.append(doc_rec)

                # 7. Queue children if sitemap index
                if fmt == SitemapFormat.SITEMAPINDEX and child_sitemaps:
                    for child in child_sitemaps:
                        if len(documents) + len(queue) < self.config.max_sitemaps:
                            queue.append((child, depth + 1))

                # 8. Accumulate URL records up to limit
                if fmt == SitemapFormat.URLSET and parsed_urls:
                    for u_rec in parsed_urls:
                        if len(url_records) >= self.config.max_urls:
                            break
                        if u_rec.identity_url not in url_records:
                            url_records[u_rec.identity_url] = u_rec

        return documents, url_records
