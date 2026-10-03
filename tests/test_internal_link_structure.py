"""
Unit tests for SiteInternalLinkAnalyzer (Phase 8.3).
Tests internal-link topology, partial-crawl semantics, weak connectivity,
dead ends, deep click depth telemetry, broken targets, anchor ambiguity,
and link concentration.
Zero live HTTP requests — completely deterministic offline execution.
"""
import pytest

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    LinkStructuralFindingType,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.analyzers.internal_link_analyzer import SiteInternalLinkAnalyzer


def make_record(
    url: str,
    raw_html: str,
    status_code: int = 200,
    depth: int = 1,
    crawl_status: CrawlStatus = CrawlStatus.FETCHED,
    discovered_links: list = None,
) -> CrawlRecord:
    clean = url.strip()
    return CrawlRecord(
        url=clean,
        normalized_url=UrlNormalizer.normalize_for_crawl(clean),
        identity_url=UrlNormalizer.get_url_identity(clean),
        crawl_status=crawl_status,
        depth=depth,
        status_code=status_code,
        raw_html=raw_html,
        discovered_links=discovered_links or [],
    )


def test_zero_inlink_partial_crawl_semantics():
    """Crawled non-root pages with 0 internal inlinks are reported factually as NO_DISCOVERED_INCOMING_LINKS."""
    root_html = """
    <html><body>
        <a href="https://example.com/page-a">Page A</a>
    </body></html>
    """
    page_a_html = """
    <html><body>
        <a href="https://example.com">Home</a>
    </body></html>
    """
    # Page B was crawled (e.g. from sitemap or seed), but no internal page in the crawl links to it
    page_b_html = """
    <html><body>
        <a href="https://example.com/page-a">Page A</a>
    </body></html>
    """

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://example.com", root_html, depth=0),
            make_record("https://example.com/page-a", page_a_html, depth=1),
            make_record("https://example.com/page-b", page_b_html, depth=1),
        ]
    )

    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com")

    # page-b should be identified as having 0 discovered incoming links
    assert "https://example.com/page-b" in intel.pages_with_zero_inlinks
    # root page must NOT be flagged as zero inlinks
    assert "https://example.com" not in intel.pages_with_zero_inlinks

    # Check structural finding
    zero_findings = [f for f in intel.structural_findings if f.finding_type == LinkStructuralFindingType.NO_DISCOVERED_INCOMING_LINKS]
    assert len(zero_findings) == 1
    assert zero_findings[0].affected_url == "https://example.com/page-b"
    assert "0 discovered internal incoming links in analyzed crawl" in zero_findings[0].evidence


def test_limited_connectivity_finding():
    """Pages with exactly 1 discovered incoming link are reported factually as LIMITED_CONNECTIVITY."""
    root_html = '<a href="https://example.com/service-hub">Services</a>'
    hub_html = '<a href="https://example.com/service-sub">Sub Service</a>'
    sub_html = '<a href="https://example.com/service-hub">Back to Hub</a>'

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://example.com", root_html, depth=0),
            make_record("https://example.com/service-hub", hub_html, depth=1),
            make_record("https://example.com/service-sub", sub_html, depth=2),
        ]
    )

    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com")

    # service-hub has 2 inlinks (from root and sub), but service-sub has only 1 inlink (from hub)
    assert "https://example.com/service-sub" in intel.pages_with_weak_inlinks
    weak_findings = [f for f in intel.structural_findings if f.finding_type == LinkStructuralFindingType.LIMITED_CONNECTIVITY]
    assert any(f.affected_url == "https://example.com/service-sub" for f in weak_findings)


def test_dead_end_page_finding():
    """Pages with 0 outbound internal links to other pages are reported as ZERO_OUTLINKS."""
    root_html = '<a href="https://example.com/contact">Contact Us</a>'
    contact_html = '<p>Call us at 555-1234 or visit our <a href="https://maps.google.com">Google Map</a></p>'

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://example.com", root_html, depth=0),
            make_record("https://example.com/contact", contact_html, depth=1),
        ]
    )

    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com")

    assert "https://example.com/contact" in intel.dead_end_pages
    dead_findings = [f for f in intel.structural_findings if f.finding_type == LinkStructuralFindingType.ZERO_OUTLINKS]
    assert len(dead_findings) == 1
    assert dead_findings[0].affected_url == "https://example.com/contact"


def test_deep_click_depth_telemetry():
    """Depth > 3 is reported as neutral topology telemetry."""
    r0 = make_record("https://example.com", '<a href="https://example.com/d1">d1</a>', depth=0)
    r1 = make_record("https://example.com/d1", '<a href="https://example.com/d2">d2</a>', depth=1)
    r2 = make_record("https://example.com/d2", '<a href="https://example.com/d3">d3</a>', depth=2)
    r3 = make_record("https://example.com/d3", '<a href="https://example.com/d4">d4</a>', depth=3)
    r4 = make_record("https://example.com/d4", '<a href="https://example.com/d1">back</a>', depth=4)

    site_crawl = SiteCrawlResult(crawl_records=[r0, r1, r2, r3, r4])
    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com")

    assert "https://example.com/d4" in intel.deep_pages
    deep_findings = [f for f in intel.structural_findings if f.finding_type == LinkStructuralFindingType.DEEP_CLICK_DEPTH]
    assert len(deep_findings) == 1
    assert deep_findings[0].affected_url == "https://example.com/d4"
    assert "crawl depth 4" in deep_findings[0].evidence


def test_broken_internal_links_detection():
    """Internal links targeting crawled records with status >= 400 are reported as BROKEN_TARGET."""
    root_html = """
    <html><body>
        <a href="https://example.com/valid">Valid Page</a>
        <a href="https://example.com/missing-page">404 Page</a>
    </body></html>
    """
    valid_html = '<a href="https://example.com">Home</a>'

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://example.com", root_html, depth=0),
            make_record("https://example.com/valid", valid_html, depth=1),
            make_record(
                "https://example.com/missing-page",
                "",
                status_code=404,
                depth=1,
                crawl_status=CrawlStatus.FAILED,
            ),
        ]
    )

    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com")

    assert intel.broken_internal_links_count == 1
    broken = intel.broken_internal_links[0]
    assert broken.source_url == "https://example.com"
    assert broken.target_url == "https://example.com/missing-page"
    assert broken.status_code == 404
    assert broken.anchor_text == "404 Page"


def test_anchor_ambiguity_detection():
    """Identical anchor text pointing to multiple distinct destinations is flagged."""
    p1_html = '<a href="https://example.com/services-a">Our Services</a>'
    p2_html = '<a href="https://example.com/services-b">Our Services</a>'

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://example.com/p1", p1_html, depth=1),
            make_record("https://example.com/p2", p2_html, depth=1),
            make_record("https://example.com/services-a", '<a href="/p1">back</a>', depth=2),
            make_record("https://example.com/services-b", '<a href="/p2">back</a>', depth=2),
        ]
    )

    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com/p1")

    assert intel.anchor_intelligence.conflicting_anchors_count >= 1
    amb = intel.anchor_intelligence.conflicting_anchors[0]
    assert amb.anchor_text == "our services"
    assert len(amb.target_urls) == 2
    assert "https://example.com/services-a" in amb.target_urls
    assert "https://example.com/services-b" in amb.target_urls


def test_link_concentration_telemetry():
    """Link concentration computes top-linked pages and top-5 concentration percentage."""
    root_html = """
    <a href="https://example.com/hub">Hub</a>
    <a href="https://example.com/hub">Hub Again</a>
    <a href="https://example.com/other">Other</a>
    """
    p1_html = '<a href="https://example.com/hub">Hub</a>'

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://example.com", root_html, depth=0),
            make_record("https://example.com/hub", '<a href="/">Home</a>', depth=1),
            make_record("https://example.com/other", '<a href="/">Home</a>', depth=1),
        ]
    )

    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com")

    assert intel.link_concentration.total_internal_links > 0
    assert len(intel.link_concentration.top_linked_pages) > 0
    top_page = intel.link_concentration.top_linked_pages[0][0]
    assert "hub" in top_page or "example.com" in top_page
    assert intel.link_concentration.top_5_concentration_pct > 0.0
