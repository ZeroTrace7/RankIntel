"""
Deep Multi-Page Asynchronous Crawler for RankIntel.
High-throughput, boundary-guarded spidering powered by httpx.AsyncClient.
"""
from __future__ import annotations
import asyncio
import time
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Set
from bs4 import BeautifulSoup

import httpx

from rankintel.models.schema import (
    CrawlConfig,
    SiteCrawlResult,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.crawler.frontier import CrawlFrontier


class AsyncDeepCrawler:
    """Production-grade asynchronous crawler honoring boundaries, limits, and robots.txt."""

    def __init__(
        self,
        config: Optional[CrawlConfig] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None
    ):
        self.config = config or CrawlConfig()
        self.transport = transport
        self._robots_parser = None
        self._robots_loaded = False

    def _init_robots(self, base_url: str) -> None:
        """Fetch and parse robots.txt rules if respect_robots_txt is True."""
        if not self.config.respect_robots_txt or self._robots_loaded:
            return

        from urllib.robotparser import RobotFileParser
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self._robots_parser = RobotFileParser()

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(robots_url)
                if resp.status_code == 200:
                    self._robots_parser.parse(resp.text.splitlines())
                else:
                    self._robots_parser.allow_all = True
        except Exception:
            self._robots_parser.allow_all = True

        self._robots_loaded = True

    def is_allowed_by_robots(self, url: str) -> bool:
        """Check whether URL is permitted under robots.txt."""
        if not self.config.respect_robots_txt or not self._robots_parser:
            return True
        try:
            return self._robots_parser.can_fetch(self.config.user_agent, url)
        except Exception:
            return True

    def crawl_sync(self, start_url: str, config: Optional[CrawlConfig] = None) -> SiteCrawlResult:
        """Synchronous entry point for running the async crawler."""
        if config:
            self.config = config
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already in an event loop, run in a separate thread to prevent blocking
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.crawl(start_url)).result()
        else:
            return asyncio.run(self.crawl(start_url))

    async def crawl(self, start_url: str) -> SiteCrawlResult:
        """Run asynchronous multi-page crawl starting from start_url."""
        t0 = time.time()
        if not start_url.startswith("http://") and not start_url.startswith("https://"):
            start_url = "https://" + start_url

        self._init_robots(start_url)
        frontier = CrawlFrontier(base_url=start_url, config=self.config)

        # Enqueue seed URL
        frontier.add_url(start_url, depth=0, parent_url=None, discovery_source="seed")

        sem = asyncio.Semaphore(self.config.concurrency)
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=self.config.concurrency
        )

        async with httpx.AsyncClient(
            headers=headers,
            limits=limits,
            timeout=self.config.timeout_sec,
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            active_tasks: Set[asyncio.Task] = set()

            while frontier.has_work() or active_tasks:
                while frontier.has_work() and len(active_tasks) < self.config.concurrency:
                    try:
                        item = frontier.queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    norm_url, depth, parent_url, discovery_source = item
                    task = asyncio.create_task(
                        self._process_url(client, frontier, sem, norm_url, depth, parent_url)
                    )
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)

                if active_tasks:
                    # Wait for at least one active task to complete
                    done, _ = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in done:
                        try:
                            t.result()
                        except Exception:
                            pass
                else:
                    break

        duration_sec = time.time() - t0
        return frontier.build_result(duration_sec)

    async def _process_url(
        self,
        client: httpx.AsyncClient,
        frontier: CrawlFrontier,
        sem: asyncio.Semaphore,
        norm_url: str,
        depth: int,
        parent_url: Optional[str]
    ) -> None:
        """Fetch and extract links from a single URL."""
        if not frontier.can_fetch_more():
            frontier.mark_skipped(norm_url, "Page limit reached")
            return

        if not self.is_allowed_by_robots(norm_url):
            frontier.mark_blocked(norm_url, "Disallowed by robots.txt")
            return

        retries = 0
        resp = None
        fetch_dur = 0.0

        while True:
            if self.config.crawl_delay > 0:
                await asyncio.sleep(self.config.crawl_delay)

            async with sem:
                t_fetch_start = time.time()
                try:
                    resp = await client.get(norm_url)
                    fetch_dur = time.time() - t_fetch_start
                except (httpx.RequestError, asyncio.TimeoutError) as e:
                    fetch_dur = time.time() - t_fetch_start
                    if retries < self.config.max_retries:
                        retries += 1
                        backoff = self.config.retry_backoff_sec * (2 ** (retries - 1))
                        await asyncio.sleep(backoff)
                        continue
                    frontier.mark_failed(norm_url, str(e), status_code=0, retry_count=retries)
                    return

            # Handle transient rate limiting (429) or temporary server unavailability (503)
            if resp.status_code in (429, 503) and retries < self.config.max_retries:
                retries += 1
                retry_after_str = resp.headers.get("retry-after")
                backoff = self.config.retry_backoff_sec * (2 ** (retries - 1))
                if retry_after_str and retry_after_str.isdigit():
                    backoff = min(float(retry_after_str), 5.0)
                await asyncio.sleep(backoff)
                continue

            break

        # Extract response headers, preserving multiple X-Robots-Tag if present
        resp_headers: Dict[str, Any] = dict(resp.headers)
        if hasattr(resp.headers, "get_list"):
            x_robots = resp.headers.get_list("x-robots-tag")
            if len(x_robots) > 1:
                resp_headers["x-robots-tag"] = x_robots
            elif len(x_robots) == 1:
                resp_headers["x-robots-tag"] = x_robots[0]

        # Handle Redirects (3xx)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("location", "")
            if location:
                abs_location = urljoin(norm_url, location)
                frontier.mark_redirected(
                    norm_url,
                    resp.status_code,
                    abs_location,
                    response_headers=resp_headers,
                    fetch_time_sec=fetch_dur,
                )
                # Enqueue redirect target if within boundaries
                if depth <= self.config.max_depth:
                    frontier.add_url(
                        abs_location,
                        depth=depth,
                        parent_url=norm_url,
                        discovery_source="redirect"
                    )
            else:
                frontier.mark_failed(norm_url, f"Redirect {resp.status_code} missing Location header", status_code=resp.status_code, retry_count=retries, response_headers=resp_headers)
            return

        # Handle Errors (4xx, 5xx)
        if resp.status_code >= 400:
            frontier.mark_failed(norm_url, f"HTTP {resp.status_code}", status_code=resp.status_code, retry_count=retries, response_headers=resp_headers)
            return

        # Handle 200 OK
        content_type = resp.headers.get("content-type", "").lower()
        body_bytes = len(resp.content)
        raw_html = resp.text

        discovered_links: List[str] = []
        if "text/html" in content_type or "application/xhtml" in content_type or not content_type:
            try:
                soup = BeautifulSoup(raw_html, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                        continue
                    full_link = urljoin(norm_url, href)
                    discovered_links.append(full_link)
                    if depth + 1 <= self.config.max_depth:
                        frontier.add_url(
                            full_link,
                            depth=depth + 1,
                            parent_url=norm_url,
                            discovery_source="internal_link"
                        )
            except Exception:
                pass

        frontier.mark_fetched(
            norm_url=norm_url,
            status_code=resp.status_code,
            content_type=content_type,
            response_bytes=body_bytes,
            fetch_time_sec=fetch_dur,
            discovered_links=discovered_links,
            raw_html=raw_html,
            retry_count=retries,
            response_headers=resp_headers,
        )
