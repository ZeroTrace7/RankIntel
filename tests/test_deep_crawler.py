"""
Integration tests for AsyncDeepCrawler using mock HTTP transport.
Validates async queue, depth tracking, max_pages ceilings, domain boundary guards,
redirect handling, transient 429/503 retries, robots.txt blocking,
duplicate discovery, and CrawlState tracking without live network calls.
"""
import asyncio
import httpx
from unittest.mock import MagicMock

from rankintel.crawler.deep_crawler import AsyncDeepCrawler
from rankintel.models.schema import CrawlConfig, CrawlStatus
from rankintel.engines.seo_engine import SeoEngine

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
            <a href="/services">Services Link from About</a>
        </body></html>""",
    "https://example.com/services": """<!DOCTYPE html>
        <html><head><title>Services</title></head>
        <body>
            <h1>Services</h1>
            <a href="/services/calibration">Calibration</a>
            <a href="/about">About Link from Services</a>
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
    "https://example.com/admin": """<!DOCTYPE html>
        <html><head><title>Admin Portal</title></head>
        <body><h1>Admin Only</h1></body></html>""",
}

# State counter for transient rate-limit tests
rate_limit_attempts = 0


def mock_transport_handler(request: httpx.Request) -> httpx.Response:
    global rate_limit_attempts
    url_str = str(request.url)

    if url_str == "https://example.com/robots.txt":
        return httpx.Response(
            200,
            text="User-agent: *\nDisallow: /admin\n"
        )
    elif url_str == "https://example.com/redirect-source":
        return httpx.Response(301, headers={"Location": "https://example.com/about"})
    elif url_str == "https://example.com/broken-404":
        return httpx.Response(404, text="Not Found")
    elif url_str == "https://example.com/error-500":
        return httpx.Response(500, text="Internal Server Error")
    elif url_str == "https://example.com/transient-429":
        rate_limit_attempts += 1
        if rate_limit_attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="Rate limit exceeded")
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text="<html><body>Recovered</body></html>")
    elif url_str == "https://example.com/always-503":
        return httpx.Response(503, headers={"Retry-After": "0"}, text="Service Unavailable")
    elif url_str == "https://example.com/api/data.json":
        return httpx.Response(200, headers={"Content-Type": "application/json"}, text='{"key": "value"}')
    elif url_str in MOCK_PAGES:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text=MOCK_PAGES[url_str]
        )
    return httpx.Response(404, text="Not Found")


def test_crawler_full_site_discovery_and_depth():
    """Verify crawler discovers site hierarchy, records depth, and respects boundaries."""
    async def _run():
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

    asyncio.run(_run())


def test_crawler_respects_max_pages_ceiling():
    """Verify crawler halts popping when max_pages ceiling is reached."""
    async def _run():
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

    asyncio.run(_run())


def test_crawler_respects_max_depth_ceiling():
    """Verify crawler does not enqueue or fetch links deeper than max_depth."""
    async def _run():
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

    asyncio.run(_run())


def test_crawler_handles_redirects_and_errors():
    """Verify 3xx redirects are marked REDIRECTED and 4xx/5xx are marked FAILED."""
    async def _run():
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

    asyncio.run(_run())


def test_crawler_handles_transient_429_retry():
    """Verify crawler retries on HTTP 429 and succeeds on subsequent attempt."""
    global rate_limit_attempts
    rate_limit_attempts = 0

    async def _run():
        transport = httpx.MockTransport(mock_transport_handler)
        config = CrawlConfig(
            max_pages=2,
            max_depth=1,
            concurrency=1,
            crawl_delay=0.0,
            max_retries=2,
            retry_backoff_sec=0.01,
            respect_robots_txt=False,
        )
        crawler = AsyncDeepCrawler(config=config, transport=transport)

        result = await crawler.crawl("https://example.com/transient-429")

        assert result.pages_crawled == 1
        record = result.crawl_records[0]
        assert record.crawl_status == CrawlStatus.FETCHED
        assert record.status_code == 200
        assert record.retry_count == 1

    asyncio.run(_run())


def test_crawler_eventual_503_failure_records_retry_count():
    """Verify crawler exhausts retries on permanent 503 and records failure."""
    async def _run():
        transport = httpx.MockTransport(mock_transport_handler)
        config = CrawlConfig(
            max_pages=2,
            max_depth=1,
            concurrency=1,
            crawl_delay=0.0,
            max_retries=2,
            retry_backoff_sec=0.01,
            respect_robots_txt=False,
        )
        crawler = AsyncDeepCrawler(config=config, transport=transport)

        result = await crawler.crawl("https://example.com/always-503")

        record = result.crawl_records[0]
        assert record.crawl_status == CrawlStatus.FAILED
        assert record.status_code == 503
        assert record.retry_count == 2

    asyncio.run(_run())


def test_crawler_duplicate_discovery_tracking():
    """Verify that multiple links to the same URL increment duplicate counts."""
    async def _run():
        transport = httpx.MockTransport(mock_transport_handler)
        config = CrawlConfig(
            max_pages=10,
            max_depth=3,
            concurrency=1,
            crawl_delay=0.0,
            respect_robots_txt=False,
        )
        crawler = AsyncDeepCrawler(config=config, transport=transport)

        result = await crawler.crawl("https://example.com")

        # In MOCK_PAGES, /about links to /services, and /services links to /about
        # Creating cross-link duplicates
        assert result.status_counts.get("DUPLICATE", 0) > 0

    asyncio.run(_run())


def test_crawler_robots_txt_blocking():
    """Verify that URLs disallowed by robots.txt are marked BLOCKED and not fetched."""
    from urllib.robotparser import RobotFileParser
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /admin"])

    async def _run():
        transport = httpx.MockTransport(mock_transport_handler)
        config = CrawlConfig(
            max_pages=5,
            max_depth=1,
            concurrency=1,
            crawl_delay=0.0,
            respect_robots_txt=True,
        )
        crawler = AsyncDeepCrawler(config=config, transport=transport)
        crawler._robots_parser = rp
        crawler._robots_loaded = True

        result = await crawler.crawl("https://example.com/admin")

        assert len(result.crawl_records) == 1
        record = result.crawl_records[0]
        assert record.crawl_status == CrawlStatus.BLOCKED
        assert "Disallowed by robots.txt" in record.failure_reason

    asyncio.run(_run())


def test_crawler_non_html_mime_not_parsed():
    """Verify non-HTML content-type (e.g. JSON) is fetched but not parsed for links."""
    async def _run():
        transport = httpx.MockTransport(mock_transport_handler)
        config = CrawlConfig(
            max_pages=2,
            max_depth=1,
            concurrency=1,
            crawl_delay=0.0,
            respect_robots_txt=False,
        )
        crawler = AsyncDeepCrawler(config=config, transport=transport)

        result = await crawler.crawl("https://example.com/api/data.json")

        record = result.crawl_records[0]
        assert record.crawl_status == CrawlStatus.FETCHED
        assert "application/json" in record.content_type
        assert len(record.discovered_links) == 0

    asyncio.run(_run())


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


def test_single_page_backward_compatibility():
    """Verify single-page audit behavior and data models are completely intact."""
    engine = SeoEngine()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><head><title>Test Title</title></head><body><h1>Heading</h1><p>Body</p></body></html>"
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.history = []

    from unittest.mock import patch
    with patch("requests.get", return_value=mock_resp):
        on_page, schema = engine.audit_static_page("https://example.com")

    assert on_page.status_code == 200
    assert on_page.title == "Test Title"
    assert on_page.h1_count == 1


def test_crawler_integrates_indexability_and_hygiene_in_result():
    """Verify crawler automatically populates search_eligibility and chains."""
    transport = httpx.MockTransport(mock_transport_handler)
    config = CrawlConfig(
        max_pages=3,
        max_depth=1,
        concurrency=1,
        crawl_delay=0.0,
        respect_robots_txt=False,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)
    result = crawler.crawl_sync("https://example.com")

    assert len(result.search_eligibility) > 0
    assert "https://example.com" in result.search_eligibility
    assert len(result.canonical_chains) > 0

