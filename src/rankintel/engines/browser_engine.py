"""
Browser Engine — JavaScript rendering via crawl4ai AsyncWebCrawler.
Falls back to httpx when crawl4ai/Playwright is not available.

Key change from previous version:
- Uses AsyncWebCrawler (crawl4ai ≥0.4 current API) instead of removed WebCrawler
- Stores CrawlResult.html in EngineResult.raw_html for use by TrustEvaluator and GeoEngine
- httpx fallback is clearly labeled as "httpx_static_fallback" — not a browser render
"""
from __future__ import annotations
import asyncio
import concurrent.futures
import logging
import time
import json
from typing import List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

from rankintel.models.schema import (
    OnPageEvidence,
    SchemaEvidence,
    EngineResult
)

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig
    HAS_CRAWL4AI = True
except ImportError:
    HAS_CRAWL4AI = False


class BrowserEngine:
    """JavaScript rendering engine. Uses crawl4ai AsyncWebCrawler when available."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    def execute_sync(self, url: str) -> EngineResult:
        """Synchronous entry point. Runs async crawl4ai in a new event loop, falls back to httpx."""
        t0 = time.time()
        if HAS_CRAWL4AI:
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        return pool.submit(asyncio.run, self._execute_async(url, t0)).result()
                else:
                    return asyncio.run(self._execute_async(url, t0))
            except Exception as e:
                logger.warning(f"crawl4ai async browser execution failed: {e}; falling back to httpx")
        return self._execute_httpx_fallback(url, t0)

    async def _execute_async(self, url: str, t0: float) -> EngineResult:
        """Run crawl4ai AsyncWebCrawler and return EngineResult with raw_html."""
        config = BrowserConfig(headless=self.headless)
        async with AsyncWebCrawler(config=config) as crawler:
            result = await crawler.arun(url=url)

        if not result.success:
            raise RuntimeError(result.error_message or "crawl4ai returned failure")

        html = result.html or ""
        soup = BeautifulSoup(html, "html.parser")

        # Use crawl4ai metadata where available; fall back to BeautifulSoup
        meta = result.metadata or {}
        title = str(meta.get("title") or "")
        if not title:
            t_tag = soup.find("title")
            title = t_tag.text.strip() if t_tag else ""

        # Use crawl4ai's pre-classified link lists
        raw_links = result.links or {}
        internal = [lk.get("href", "") for lk in raw_links.get("internal", []) if lk.get("href")]
        external = [lk.get("href", "") for lk in raw_links.get("external", []) if lk.get("href")]

        # Parse schema BEFORE _build_on_page strips <script> tags from soup
        schema_ev = self._parse_schema(soup)
        schema_ev.engine_source = "crawl4ai_browser_dom"
        schema_ev.is_injected_via_js = True  # browser engine can see JS-injected schema

        duration = round(time.time() - t0, 2)
        on_page = self._build_on_page(soup, url, title, internal, external, duration)
        on_page.status_code = result.status_code or 200
        on_page.engine_source = "crawl4ai_browser_dom"

        return EngineResult(
            engine_name="browser_engine",
            status="success",
            execution_time_sec=duration,
            on_page=on_page,
            schema_data=schema_ev,
            raw_html=html,  # Stored for TrustEvaluator and GeoOptimizerAdapter
        )

    def _execute_httpx_fallback(self, url: str, t0: Optional[float] = None) -> EngineResult:
        """Plain HTTP fallback — no JS execution. Clearly labeled."""
        import httpx
        if t0 is None:
            t0 = time.time()
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            duration = round(time.time() - t0, 2)

            # Parse schema BEFORE _build_on_page strips <script> tags
            schema_ev = self._parse_schema(soup)
            schema_ev.engine_source = "httpx_static_fallback"
            schema_ev.is_injected_via_js = False  # Cannot detect JS injection via plain HTTP

            on_page = self._build_on_page(soup, url, "", [], [], duration)
            on_page.status_code = resp.status_code
            on_page.engine_source = "httpx_static_fallback"  # NOT browser rendering

            return EngineResult(
                engine_name="browser_engine",
                status="fallback",
                error_message="Browser rendering unavailable; static httpx fallback used (no JavaScript execution)",
                execution_time_sec=duration,
                on_page=on_page,
                schema_data=schema_ev,
                raw_html=html,  # Still store HTML for TrustEvaluator even on fallback path
            )
        except Exception as e:
            return EngineResult(
                engine_name="browser_engine",
                status="error",
                error_message=str(e),
                execution_time_sec=round(time.time() - t0, 2),
            )

    def _build_on_page(
        self, soup: BeautifulSoup, url: str, title: str,
        internal: List[str], external: List[str], dur: float
    ) -> OnPageEvidence:
        on_page = OnPageEvidence(url=url, status_code=200, response_time_sec=dur)

        if not title:
            t_tag = soup.find("title")
            title = t_tag.get_text().strip() if t_tag else ""
        on_page.title = title
        on_page.title_length = len(title)

        m_tag = soup.find("meta", attrs={"name": "description"})
        m_desc = m_tag["content"].strip() if m_tag and m_tag.get("content") else ""
        on_page.meta_description = m_desc
        on_page.meta_desc_length = len(m_desc)

        c_tag = soup.find("link", attrs={"rel": lambda v: v and "canonical" in (v if isinstance(v, list) else [str(v).lower()])})
        if c_tag and c_tag.get("href"):
            on_page.canonical_url = c_tag["href"].strip()

        on_page.h1_text = [h.get_text().strip() for h in soup.find_all("h1") if h.get_text().strip()]
        on_page.h1_count = len(on_page.h1_text)
        on_page.h2_text = [h.get_text().strip() for h in soup.find_all("h2") if h.get_text().strip()]
        on_page.h2_count = len(on_page.h2_text)
        on_page.h3_text = [h.get_text().strip() for h in soup.find_all("h3") if h.get_text().strip()]
        on_page.h3_count = len(on_page.h3_text)

        imgs = soup.find_all("img")
        on_page.total_images = len(imgs)
        on_page.images_with_alt = len([img for img in imgs if img.get("alt") and img.get("alt").strip()])

        on_page.internal_links = internal or []
        on_page.external_links = external or []

        # Word count — strip scripts/styles/nav/footer first
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.extract()
        on_page.word_count = len(soup.get_text(separator=" ").split())

        return on_page

    def _parse_schema(self, soup: BeautifulSoup) -> SchemaEvidence:
        schema_ev = SchemaEvidence()
        schema_tags = soup.find_all("script", type="application/ld+json")
        schema_ev.blocks_count = len(schema_tags)

        detected = []
        sameas_urls = []
        has_org = False
        has_author = False

        for tag in schema_tags:
            try:
                c = tag.string if tag.string else tag.text
                if not c:
                    continue
                data = json.loads(c, strict=False)
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("@graph", [data]) if "@graph" in data and isinstance(data["@graph"], list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    t = item.get("@type")
                    if t:
                        detected.extend([str(t)] if isinstance(t, str) else [str(x) for x in t])

                    type_str = str(t)
                    if any(o in type_str for o in ["Organization", "Corporation", "LocalBusiness", "ProfessionalService"]):
                        has_org = True
                    if any(p in type_str for p in ["Person", "Author"]):
                        has_author = True

                    sameas = item.get("sameAs")
                    if sameas:
                        if isinstance(sameas, list):
                            for s_u in sameas:
                                if isinstance(s_u, str) and s_u.startswith("http"):
                                    sameas_urls.append(s_u)
                        elif isinstance(sameas, str) and sameas.startswith("http"):
                            sameas_urls.append(sameas)
            except Exception as e:
                schema_ev.validation_issues.append(str(e))

        schema_ev.detected_types = list(set(detected))
        schema_ev.sameas_urls = list(set(sameas_urls))
        schema_ev.has_organization = has_org
        schema_ev.has_author = has_author
        return schema_ev
