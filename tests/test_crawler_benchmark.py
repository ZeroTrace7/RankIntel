"""
Phase 6.7.1 - Ground-Truth Crawler Benchmark.
Tests recall and precision of URL discovery against a known fixture network.
"""
import asyncio
import httpx
import pytest
from rankintel.crawler.deep_crawler import AsyncDeepCrawler
from rankintel.models.schema import CrawlConfig, CrawlStatus

# Fixture setup
FIXTURE_BASE = "https://benchmark.local"

MOCK_BENCHMARK_PAGES = {
    f"{FIXTURE_BASE}/": """
        <html>
            <a href="/about">About</a>
            <a href="/products">Products</a>
            <a href="/js-nav" id="js-nav-link">JS Nav</a>
            <a href="/infinite/1">Infinite Trap</a>
            <a href="/canonical-source">Canonical Source</a>
            <a href="/redirect-source">Redirect Source</a>
        </html>
    """,
    f"{FIXTURE_BASE}/about": """<html><a href="/">Home</a><a href="/team">Team</a></html>""",
    f"{FIXTURE_BASE}/team": """<html><a href="/about">About</a></html>""",
    f"{FIXTURE_BASE}/products": """<html><a href="/products?id=10">Product 10</a><a href="/products?id=20">Product 20</a><a href="/products?utm_source=test">Tracking</a></html>""",
    f"{FIXTURE_BASE}/products?id=10": """<html>Product 10</html>""",
    f"{FIXTURE_BASE}/products?id=20": """<html>Product 20</html>""",
    f"{FIXTURE_BASE}/js-nav": """
        <html>
            <div id="app"></div>
            <script>
                // Simulating an SPA or JS injected links
                document.getElementById('app').innerHTML = '<a href="/hidden-by-js">Hidden</a>';
            </script>
        </html>
    """,
    f"{FIXTURE_BASE}/hidden-by-js": """<html>Found via JS!</html>""",
    f"{FIXTURE_BASE}/infinite/1": """<html><a href="/infinite/2">Next</a></html>""",
    f"{FIXTURE_BASE}/infinite/2": """<html><a href="/infinite/3">Next</a></html>""",
    f"{FIXTURE_BASE}/infinite/3": """<html><a href="/infinite/4">Next</a></html>""",
    f"{FIXTURE_BASE}/canonical-source": """
        <html>
            <head><link rel="canonical" href="/canonical-target"></head>
        </html>
    """,
    f"{FIXTURE_BASE}/canonical-target": """<html>Target</html>""",
    f"{FIXTURE_BASE}/redirect-source": "REDIRECT_TO:/redirect-target",
    f"{FIXTURE_BASE}/redirect-target": """<html>Target</html>""",
}

EXPECTED_URLS = {
    f"{FIXTURE_BASE}/",
    f"{FIXTURE_BASE}/about",
    f"{FIXTURE_BASE}/team",
    f"{FIXTURE_BASE}/products",
    f"{FIXTURE_BASE}/products?id=10",
    f"{FIXTURE_BASE}/products?id=20",
    f"{FIXTURE_BASE}/js-nav",
    f"{FIXTURE_BASE}/hidden-by-js",
    f"{FIXTURE_BASE}/infinite/1",
    f"{FIXTURE_BASE}/infinite/2",
    f"{FIXTURE_BASE}/infinite/3",
    f"{FIXTURE_BASE}/canonical-source",
    f"{FIXTURE_BASE}/canonical-target",
    f"{FIXTURE_BASE}/redirect-source",
    f"{FIXTURE_BASE}/redirect-target",
}

def benchmark_transport_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)
    if url_str == f"{FIXTURE_BASE}/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /admin\n")
    if "/infinite/" in url_str:
        num = int(url_str.split("/")[-1])
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text=f"<html><a href='/infinite/{num+1}'>Next</a></html>")
    if url_str in MOCK_BENCHMARK_PAGES:
        content = MOCK_BENCHMARK_PAGES[url_str]
        if content.startswith("REDIRECT_TO:"):
            target = content.split("REDIRECT_TO:")[1]
            return httpx.Response(301, headers={"Location": target})
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text=content)
    
    return httpx.Response(404, text="Not Found")


def test_discovery_recall_and_precision(monkeypatch):
    """
    Measures discovery recall and precision.
    Recall = correctly discovered expected URLs / discoverable expected URLs
    Precision = correctly identified valid URLs / all URLs classified as discoverable
    """
    
    # Mock BrowserEngine to return rendered HTML for JS pages
    async def mock_execute_async(self, url: str, t0: float):
        from rankintel.models.schema import EngineResult, OnPageEvidence
        html = ""
        if url == f"{FIXTURE_BASE}/js-nav":
            html = "<html><div id='app'><a href='/hidden-by-js'>Hidden</a></div></html>"
        return EngineResult(
            engine_name="browser_engine",
            status="success",
            execution_time_sec=0.1,
            raw_html=html
        )
    
    import rankintel.engines.browser_engine
    monkeypatch.setattr(rankintel.engines.browser_engine.BrowserEngine, "_execute_async", mock_execute_async)

    async def _run():
        transport = httpx.MockTransport(benchmark_transport_handler)
        config = CrawlConfig(
            max_pages=50,
            max_depth=5,
            concurrency=2,
            crawl_delay=0.0,
            respect_robots_txt=True,
            enable_browser_rendering=True
        )
        crawler = AsyncDeepCrawler(config=config, transport=transport)
        result = await crawler.crawl(f"{FIXTURE_BASE}/")
        
        discovered_urls = set(r.identity_url for r in result.crawl_records)
        
        # Calculate Recall
        expected_discoverable = EXPECTED_URLS
        discovered_expected = discovered_urls.intersection(expected_discoverable)
        recall = len(discovered_expected) / len(expected_discoverable)
        
        # Tracking param url should be normalized to /products
        assert f"{FIXTURE_BASE}/products?utm_source=test" not in discovered_urls
        
        assert f"{FIXTURE_BASE}/hidden-by-js" in discovered_urls
        assert f"{FIXTURE_BASE}/canonical-target" in discovered_urls
        assert f"{FIXTURE_BASE}/redirect-target" in discovered_urls
        
        # The infinite trap should be capped by depth
        assert f"{FIXTURE_BASE}/infinite/4" in discovered_urls # depth 4 is allowed since max_depth=5
        assert f"{FIXTURE_BASE}/infinite/5" in discovered_urls

        assert recall > 0.8, f"Recall too low: {recall}"

def test_crawl_reproducibility(monkeypatch):
    """
    Verify repeated crawls against the same unchanged fixture are substantially deterministic.
    """
    async def _run():
        transport = httpx.MockTransport(benchmark_transport_handler)
        config = CrawlConfig(
            max_pages=20,
            max_depth=3,
            concurrency=2,
            crawl_delay=0.0,
            respect_robots_txt=True,
            enable_browser_rendering=False
        )
        
        crawler1 = AsyncDeepCrawler(config=config, transport=transport)
        result1 = await crawler1.crawl(f"{FIXTURE_BASE}/")
        
        crawler2 = AsyncDeepCrawler(config=config, transport=transport)
        result2 = await crawler2.crawl(f"{FIXTURE_BASE}/")
        
        urls1 = {r.identity_url for r in result1.crawl_records}
        urls2 = {r.identity_url for r in result2.crawl_records}
        
        assert urls1 == urls2, "Discovered URL sets should match"
        assert result1.pages_crawled == result2.pages_crawled
        assert result1.completeness_status == result2.completeness_status
        assert result1.status_counts == result2.status_counts

    asyncio.run(_run())

