"""
Unit tests for RankIntel conservative SitemapParser (Milestone M6.5).
"""
import pytest
from rankintel.models.schema import SitemapFormat
from rankintel.sitemaps.parser import SitemapParser


def test_parse_standard_urlset():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://example.com/</loc>
            <lastmod>2026-10-01</lastmod>
            <changefreq>daily</changefreq>
            <priority>1.0</priority>
        </url>
        <url>
            <loc>https://example.com/about</loc>
            <lastmod>2026-09-15</lastmod>
            <changefreq>monthly</changefreq>
            <priority>0.8</priority>
        </url>
    </urlset>
    """
    fmt, urls, children, err = SitemapParser.parse_sitemap(xml, "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.URLSET
    assert err is None
    assert len(children) == 0
    assert len(urls) == 2
    assert urls[0].loc == "https://example.com/"
    assert urls[0].priority == 1.0
    assert urls[0].changefreq == "daily"
    assert urls[0].lastmod == "2026-10-01"
    assert urls[1].loc == "https://example.com/about"
    assert urls[1].priority == 0.8


def test_parse_sitemap_index():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap>
            <loc>https://example.com/sitemap-pages.xml</loc>
            <lastmod>2026-10-01</lastmod>
        </sitemap>
        <sitemap>
            <loc>https://example.com/sitemap-blog.xml</loc>
            <lastmod>2026-09-28</lastmod>
        </sitemap>
    </sitemapindex>
    """
    fmt, urls, children, err = SitemapParser.parse_sitemap(xml, "https://example.com/sitemap_index.xml")
    assert fmt == SitemapFormat.SITEMAPINDEX
    assert err is None
    assert len(urls) == 0
    assert len(children) == 2
    assert children[0] == "https://example.com/sitemap-pages.xml"
    assert children[1] == "https://example.com/sitemap-blog.xml"


def test_parse_namespaces_and_image_extensions():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
        <url>
            <loc>https://example.com/gallery</loc>
            <image:image>
                <image:loc>https://example.com/images/hero.jpg</image:loc>
            </image:image>
        </url>
    </urlset>
    """
    fmt, urls, children, err = SitemapParser.parse_sitemap(xml, "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.URLSET
    assert len(urls) == 1
    assert urls[0].loc == "https://example.com/gallery"


def test_parse_query_parameters_preserves_content_identity():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://example.com/product?id=1</loc>
        </url>
        <url>
            <loc>https://example.com/product?id=2</loc>
        </url>
    </urlset>
    """
    fmt, urls, children, err = SitemapParser.parse_sitemap(xml, "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.URLSET
    assert len(urls) == 2
    assert urls[0].identity_url != urls[1].identity_url
    assert "id=1" in urls[0].identity_url
    assert "id=2" in urls[1].identity_url


def test_parse_duplicate_urls_deduplicates():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/page</loc></url>
        <url><loc>https://example.com/page</loc></url>
    </urlset>
    """
    fmt, urls, children, err = SitemapParser.parse_sitemap(xml, "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.URLSET
    assert len(urls) == 1


def test_conservative_recovery_unescaped_ampersand():
    # Invalid XML due to bare '&' instead of '&amp;'
    xml = b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://example.com/items?cat=tools&sort=asc</loc>
        </url>
    </urlset>"""
    fmt, urls, children, err = SitemapParser.parse_sitemap(xml, "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.URLSET
    assert len(urls) == 1
    assert "tools" in urls[0].loc
    assert "sort=asc" in urls[0].loc
    assert err is not None and "conservative fallback" in err.lower()


def test_conservative_recovery_strictly_rejects_html_error_page():
    html_error = b"""<!DOCTYPE html>
    <html lang="en">
    <head><title>404 Not Found</title></head>
    <body>
        <h1>Not Found</h1>
        <p>The requested URL was not found on this server.</p>
        <a href="https://example.com/home">Go Home</a>
    </body>
    </html>"""
    fmt, urls, children, err = SitemapParser.parse_sitemap(html_error, "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.HTML_ERROR_PAGE
    assert len(urls) == 0
    assert len(children) == 0
    assert "HTML document" in err


def test_parse_empty_content():
    fmt, urls, children, err = SitemapParser.parse_sitemap(b"", "https://example.com/sitemap.xml")
    assert fmt == SitemapFormat.MALFORMED
    assert len(urls) == 0
    assert "Empty" in err


def test_parse_size_limit_exceeded():
    large_xml = b"<urlset>" + (b" " * 1500) + b"</urlset>"
    fmt, urls, children, err = SitemapParser.parse_sitemap(
        large_xml, "https://example.com/sitemap.xml", max_size_bytes=1000
    )
    assert fmt == SitemapFormat.MALFORMED
    assert "exceeds maximum limit" in err
