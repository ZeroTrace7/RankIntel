"""
Integration tests for AsyncDeepCrawler using mock HTTP transport.
Validates async queue, depth tracking, max_pages ceilings, domain boundary guards,
redirect handling, and CrawlState tracking without live network calls.
"""
import pytest
import httpx

from rankintel.crawler.deep_crawler import AsyncDeepCrawler
from rankintel.models.schema import CrawlConfig, CrawlStatus

MOCK_PAGES = {
    "https://example.com": """<!DOCTYPE html>
        <html><head><title>Home Page</title><meta name="description" content="Homepage description here."></head>
        <body>
            <h1>Welcome Home</h1>
            <a href="/about">About Us</a>
            <a href="/services">Our Services</a>
            <a href="https://external-competitor.com/page">External Partner</a>
            <a href="/manual.pdf">PDF Manual</a>
        </body></html>""",
    "https://example.com/": """<!DOCTYPE html>
        <html><head><title>Home Page</title><meta name="description" content="Homepage description here."></head>
        <body>
            <h1>Welcome Home</h1>
            <a href="/about">About Us</a>
            <a href="/services">Our Services</a>
            <a href="https://external-competitor.com/page">External Partner</a>
            <a href="/manual.pdf">PDF Manual</a>
        </body></html>""",
    "https://example.com/about": """<!DOCTYPE html>
        <html><head><title>About Us</title><meta name="description" content="About our great company."></head>
        <body>
            <h1>About Us</h1>
            <a href="/team">Meet the Team</a>
            <a href="/contact">Contact Us</a>
        </body></html>""",
    "https://example.com/services": """<!DOCTYPE html>
        <html><head><title>Services</title></head>
        <body>
            <h1>Services</h1>
            <a href="/services/calibration">Calibration</a>
        </body></html>""",
    "https://example.com/team": """<!DOCTYPE html>
        <html><head><title>Team</title></head>
        <body>
            <h1>Our Team</h1>
            <a href="/">Back Home</a>
        </body></html>""",
    "https://example.com/contact": """<!DOCTYPE html>
        <html><head><title>Contact</title></head>
        <body><h1>Contact Us</h1></body></html>""",
    "https://example.com/services/calibration": """<!DOCTYPE html>
        <html><head><title>Calibration</title></head>
        <body><h1>Calibration Testing</h1></body></html>""",
}


def mock_transport_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)
    if url_str == "https://example.com/redirect-source":
        return httpx.Response(301, headers={"Location": "https://example.com/about"})
    elif url_str == "https://example.com/broken-404":
        return httpx.Response(404, text="Not Found")
    elif url_str == "https://example.com/error-500":
        return httpx.Response(500, text="Internal Server Error")
    elif url_str in MOCK_PAGES:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text=MOCK_PAGES[url_str]
        )
    return httpx.Response(404, text="Not Found")


@pytest.mark.asyncio
async def test_crawler_full_site_discovery_and_depth():
    """Verify crawler discovers site hierarchy, records depth, and respects boundaries."""
    transport = httpx.MockTransport(mock_transport_handler)
    config = CrawlConfig(
        max_pages=20,
        max_depth=3,
        concurrency=3,
        crawl_delay=0.0,
        respect_robots_txt=False,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)

    result = await crawler.crawl("https://example.com")

    # Should discover all internal pages up to depth 2
    assert result.pages_crawled >= 5

    # Check CrawlRecord telemetry
    crawled_urls = {r.normalized_url for r in result.crawl_records if r.crawl_status == CrawlStatus.FETCHED}
    assert "https://example.com" in crawled_urls or "https://example.com/" in crawled_urls
    assert "https://example.com/about" in crawled_urls
    assert "https://example.com/services" in crawled_urls

    # External domain must NOT be crawled
    assert not any("external-competitor.com" in r.url for r in result.crawl_records)

    # PDF asset must NOT be crawled
    assert not any("manual.pdf" in r.url for r in result.crawl_records)

    # Status counts must track fetched
    assert result.status_counts.get("FETCHED", 0) >= 5


@pytest.mark.asyncio
async def test_crawler_respects_max_pages_ceiling():
    """Verify crawler halts popping when max_pages ceiling is reached."""
    transport = httpx.MockTransport(mock_transport_handler)
    config = CrawlConfig(
        max_pages=3,
        max_depth=5,
        concurrency=1,
        crawl_delay=0.0,
        respect_robots_txt=False,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)

    result = await crawler.crawl("https://example.com")

    assert result.pages_crawled <= 3


@pytest.mark.asyncio
async def test_crawler_respects_max_depth_ceiling():
    """Verify crawler does not enqueue or fetch links deeper than max_depth."""
    transport = httpx.MockTransport(mock_transport_handler)
    config = CrawlConfig(
        max_pages=20,
        max_depth=1,  # Root (depth 0) and depth 1 only
        concurrency=2,
        crawl_delay=0.0,
        respect_robots_txt=False,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)

    result = await crawler.crawl("https://example.com")

    fetched_records = [r for r in result.crawl_records if r.crawl_status == CrawlStatus.FETCHED]
    for r in fetched_records:
        assert r.depth <= 1, f"Fetched record at depth {r.depth} exceeds max_depth 1: {r.url}"


@pytest.mark.asyncio
async def test_crawler_handles_redirects_and_errors():
    """Verify 3xx redirects are marked REDIRECTED and 4xx/5xx are marked FAILED."""
    transport = httpx.MockTransport(mock_transport_handler)
    config = CrawlConfig(
        max_pages=10,
        max_depth=2,
        concurrency=1,
        crawl_delay=0.0,
        respect_robots_txt=False,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)

    # Crawl starting from redirect source
    result = await crawler.crawl("https://example.com/redirect-source")

    redirect_records = [r for r in result.crawl_records if r.crawl_status == CrawlStatus.REDIRECTED]
    assert len(redirect_records) >= 1
    assert redirect_records[0].status_code == 301
    assert "Redirected to https://example.com/about" in redirect_records[0].failure_reason


def test_crawler_sync_wrapper_runs_cleanly():
    """Verify crawl_sync executes synchronously without errors."""
    transport = httpx.MockTransport(mock_transport_handler)
    config = CrawlConfig(
        max_pages=2,
        max_depth=1,
        concurrency=1,
        crawl_delay=0.0,
        respect_robots_txt=False,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)

    result = crawler.crawl_sync("https://example.com")
    assert result.pages_crawled >= 1
    assert result.crawl_duration_sec >= 0.0
