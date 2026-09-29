"""
Browser Engine Adapter — Handles JavaScript rendering and DOM extraction.
Leverages crawl4ai when installed, with async httpx fallback.
"""
from __future__ import annotations
import time
import json
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    OnPageEvidence,
    SchemaEvidence,
    EngineResult
)

try:
    import crawl4ai
    HAS_CRAWL4AI = True
except ImportError:
    HAS_CRAWL4AI = False

class BrowserEngine:
    """Specialized engine for JavaScript rendering, dynamic DOM extraction, and client-side schemas."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    def execute_sync(self, url: str) -> EngineResult:
        """Execute browser rendering or async-fetch fallback."""
        t0 = time.time()
        
        # If crawl4ai is installed and ready, we can use it
        if HAS_CRAWL4AI:
            try:
                # Crawl4ai run
                from crawl4ai import WebCrawler
                crawler = WebCrawler(verbose=False)
                crawler.warmup()
                result = crawler.run(url=url)
                
                if result and result.success:
                    soup = BeautifulSoup(result.html or "", "html.parser")
                    on_page = self._parse_on_page(soup, url, round(time.time() - t0, 2))
                    on_page.engine_source = "crawl4ai_browser_dom"
                    
                    schema_ev = self._parse_schema(soup)
                    schema_ev.engine_source = "crawl4ai_browser_dom"
                    schema_ev.is_injected_via_js = True

                    return EngineResult(
                        engine_name="crawl4ai_browser",
                        status="success",
                        execution_time_sec=round(time.time() - t0, 2),
                        on_page=on_page,
                        schema_data=schema_ev
                    )
            except Exception as e:
                pass  # Fall through to resilient httpx fallback

        # Resilient HTTP fallback with browser headers
        import httpx
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
            }
            with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                dur = round(time.time() - t0, 2)
                
                soup = BeautifulSoup(resp.text, "html.parser")
                on_page = self._parse_on_page(soup, url, dur)
                on_page.status_code = resp.status_code
                on_page.engine_source = "browser_client_render_check"

                schema_ev = self._parse_schema(soup)
                schema_ev.engine_source = "browser_client_render_check"

                return EngineResult(
                    engine_name="browser_engine",
                    status="success" if resp.status_code == 200 else "error",
                    execution_time_sec=dur,
                    on_page=on_page,
                    schema_data=schema_ev
                )
        except Exception as e:
            return EngineResult(
                engine_name="browser_engine",
                status="error",
                error_message=str(e),
                execution_time_sec=round(time.time() - t0, 2)
            )

    def _parse_on_page(self, soup: BeautifulSoup, url: str, dur: float) -> OnPageEvidence:
        on_page = OnPageEvidence(url=url, status_code=200, response_time_sec=dur)
        
        t_tag = soup.find('title')
        title = t_tag.text.strip() if t_tag else ""
        on_page.title = title
        on_page.title_length = len(title)

        m_tag = soup.find('meta', attrs={'name': 'description'})
        m_desc = m_tag['content'].strip() if m_tag and m_tag.get('content') else ""
        on_page.meta_description = m_desc
        on_page.meta_desc_length = len(m_desc)

        on_page.h1_text = [h1.get_text().strip() for h1 in soup.find_all('h1') if h1.get_text().strip()]
        on_page.h1_count = len(on_page.h1_text)

        on_page.h2_text = [h2.get_text().strip() for h2 in soup.find_all('h2') if h2.get_text().strip()]
        on_page.h2_count = len(on_page.h2_text)

        on_page.h3_text = [h3.get_text().strip() for h3 in soup.find_all('h3') if h3.get_text().strip()]
        on_page.h3_count = len(on_page.h3_text)

        imgs = soup.find_all('img')
        on_page.total_images = len(imgs)
        on_page.images_with_alt = len([img for img in imgs if img.get('alt') and img.get('alt').strip()])

        for s in soup(["script", "style", "nav", "footer"]):
            s.extract()
        text = soup.get_text(separator=' ')
        on_page.word_count = len(text.split())
        return on_page

    def _parse_schema(self, soup: BeautifulSoup) -> SchemaEvidence:
        schema_ev = SchemaEvidence()
        schema_tags = soup.find_all('script', type='application/ld+json')
        schema_ev.blocks_count = len(schema_tags)
        
        detected = []
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
                    if "@graph" in data and isinstance(data["@graph"], list):
                        items = data["@graph"]
                    else:
                        items = [data]
                for item in items:
                    t = item.get("@type")
                    if t:
                        if isinstance(t, list):
                            for sub_t in t:
                                detected.append(str(sub_t))
                        else:
                            detected.append(str(t))
            except Exception as e:
                schema_ev.validation_issues.append(str(e))
        
        schema_ev.detected_types = list(set(detected))
        return schema_ev
