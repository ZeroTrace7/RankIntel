"""
Integration tests for SitemapDiscovery and SitemapFetcher using MockTransport.
Offline execution — zero live network requests.
"""
import pytest
import httpx

from rankintel.models.schema import SitemapFetchStatus, SitemapFormat
from rankintel.sitemaps.config import SitemapConfig
from rankintel.sitemaps.discovery import SitemapDiscovery
from rankintel.sitemaps.fetcher import SitemapFetcher


# ===========================================================================
# 1. SITEMAP DISCOVERY TESTS
# ===========================================================================

def test_discovery_from_robots_txt_directives():
    robots = """User-agent: *
Disallow: /admin/
Sitemap: https://example.com/sitemap_index.xml
sitemap: https://example.com/sitemap_news.xml
"""
    sitemaps = SitemapDiscovery.discover_from_robots_txt(robots)
    assert len(sitemaps) == 2
    assert sitemaps[0] == "https://example.com/sitemap_index.xml"
    assert sitemaps[1] == "https://example.com/sitemap_news.xml"


def test_discovery_fallback_to_standard_paths():
    sitemaps = SitemapDiscovery.discover_sitemap_urls(
        base_url="https://example.com",
        robots_txt_content="User-agent: *\nDisallow: /private/",
        fallback_to_standard_paths=True,
    )
    assert len(sitemaps) == 2
    assert "https://example.com/sitemap.xml" in sitemaps
    assert "https://example.com/sitemap_index.xml" in sitemaps


# ===========================================================================
# 2. SITEMAP FETCHER TESTS (MockTransport)
# ===========================================================================

def test_fetch_single_sitemap():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/home</loc></url>
        <url><loc>https://example.com/about</loc></url>
    </urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml, headers={"Content-Type": "application/xml"})

    transport = httpx.MockTransport(handler)
    fetcher = SitemapFetcher(transport=transport)
    docs, urls = fetcher.fetch_sitemaps_sync(["https://example.com/sitemap.xml"])

    assert len(docs) == 1
    assert docs[0].status == SitemapFetchStatus.SUCCESS
    assert docs[0].format == SitemapFormat.URLSET
    assert len(urls) == 2
    assert "https://example.com/home" in urls
    assert "https://example.com/about" in urls


def test_fetch_nested_sitemap_index_recursion():
    index_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
        <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
    </sitemapindex>"""

    child1_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/product/1</loc></url>
    </urlset>"""

    child2_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/product/2</loc></url>
    </urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "sitemap_index.xml" in url_str:
            return httpx.Response(200, content=index_xml)
        elif "sitemap-1.xml" in url_str:
            return httpx.Response(200, content=child1_xml)
        elif "sitemap-2.xml" in url_str:
            return httpx.Response(200, content=child2_xml)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    fetcher = SitemapFetcher(transport=transport)
    docs, urls = fetcher.fetch_sitemaps_sync(["https://example.com/sitemap_index.xml"])

    # 1 index + 2 child sitemaps = 3 documents
    assert len(docs) == 3
    assert docs[0].format == SitemapFormat.SITEMAPINDEX
    assert docs[1].format == SitemapFormat.URLSET
    assert docs[2].format == SitemapFormat.URLSET
    assert len(urls) == 2
    assert "https://example.com/product/1" in urls
    assert "https://example.com/product/2" in urls


def test_fetch_circular_loop_detection():
    # Index A points to Index B, Index B points back to Index A
    index_a = b"""<sitemapindex><sitemap><loc>https://example.com/b.xml</loc></sitemap></sitemapindex>"""
    index_b = b"""<sitemapindex><sitemap><loc>https://example.com/a.xml</loc></sitemap></sitemapindex>"""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "a.xml" in url_str:
            return httpx.Response(200, content=index_a)
        elif "b.xml" in url_str:
            return httpx.Response(200, content=index_b)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    fetcher = SitemapFetcher(transport=transport)
    docs, urls = fetcher.fetch_sitemaps_sync(["https://example.com/a.xml"])

    # First doc is a.xml (SUCCESS), second is b.xml (SUCCESS), third is a.xml again (LOOP_DETECTED)
    assert len(docs) == 3
    assert docs[0].status == SitemapFetchStatus.SUCCESS
    assert docs[1].status == SitemapFetchStatus.SUCCESS
    assert docs[2].status == SitemapFetchStatus.LOOP_DETECTED
    assert "Circular loop" in docs[2].error_message


def test_fetch_max_depth_exceeded():
    index_xml = b"""<sitemapindex><sitemap><loc>https://example.com/child.xml</loc></sitemap></sitemapindex>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=index_xml)

    transport = httpx.MockTransport(handler)
    # Configure max_depth = 0 so immediate children are rejected with MAX_DEPTH_EXCEEDED
    config = SitemapConfig(max_depth=0)
    fetcher = SitemapFetcher(config=config, transport=transport)
    docs, urls = fetcher.fetch_sitemaps_sync(["https://example.com/index.xml"])

    assert len(docs) == 2
    assert docs[0].status == SitemapFetchStatus.SUCCESS
    assert docs[1].status == SitemapFetchStatus.MAX_DEPTH_EXCEEDED


def test_fetch_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    fetcher = SitemapFetcher(transport=transport)
    docs, urls = fetcher.fetch_sitemaps_sync(["https://example.com/nonexistent.xml"])

    assert len(docs) == 1
    assert docs[0].status == SitemapFetchStatus.HTTP_ERROR
    assert docs[0].status_code == 404


def test_fetch_respects_robots_block_for_sitemap():
    class MockRobotsParser:
        def can_fetch(self, user_agent: str, url: str) -> bool:
            # Block sitemap-secret.xml
            return "secret" not in url

    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"<urlset></urlset>"))
    fetcher = SitemapFetcher(transport=transport)
    docs, urls = fetcher.fetch_sitemaps_sync(
        ["https://example.com/sitemap-secret.xml"],
        robots_parser=MockRobotsParser(),
    )

    assert len(docs) == 1
    assert docs[0].status == SitemapFetchStatus.BLOCKED_BY_ROBOTS
    assert "disallowed under robots.txt" in docs[0].error_message
