"""
Unit tests for RankIntel Cross-Page Entity Consistency & Candidate Identification (Phase 8.2).
"""
import pytest
from rankintel.models.schema import (
    SiteCrawlResult,
    CrawlRecord,
    CrawlStatus,
)
from rankintel.analyzers.entity_analyzer import SiteEntityAnalyzer


def make_record(url: str, html: str, depth: int = 1) -> CrawlRecord:
    return CrawlRecord(
        url=url,
        normalized_url=url,
        identity_url=url,
        crawl_status=CrawlStatus.FETCHED,
        depth=depth,
        status_code=200,
        raw_html=html,
    )


def test_primary_organization_candidate_identification():
    """Verify primary candidate identification with explicit selection rationale."""
    page_root = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Apex Metrology - Precision Calibration</title>
        <meta property="og:site_name" content="Apex Metrology">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Apex Metrology Labs",
            "url": "https://apexmetrology.com"
        }
        </script>
    </head>
    <body>
        <main><h1>Welcome to Apex Metrology</h1></main>
        <footer>&copy; 2026 Apex Metrology Labs. All rights reserved.</footer>
    </body>
    </html>
    """

    page_about = """
    <!DOCTYPE html>
    <html>
    <head><title>About Apex</title></head>
    <body>
        <main><h1>About Our Laboratory</h1></main>
        <footer>&copy; 2026 Apex Metrology Labs.</footer>
    </body>
    </html>
    """

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://apexmetrology.com/", page_root, depth=0),
            make_record("https://apexmetrology.com/about", page_about, depth=1),
        ]
    )

    intel = SiteEntityAnalyzer.analyze_site(site_crawl)

    assert intel.total_pages_evaluated == 2
    assert intel.primary_organization_candidate is not None
    poc = intel.primary_organization_candidate
    assert "Apex Metrology" in (poc.candidate_name or "")
    assert len(poc.selection_reasons) >= 2
    assert any("root/homepage" in r for r in poc.selection_reasons)
    assert any("JSON-LD" in r for r in poc.selection_reasons)
    assert intel.inconsistencies_count == 0


def test_cross_page_conflicting_addresses_and_phones():
    """Verify detection of conflicting physical addresses and phone numbers across crawled pages."""
    page_a = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Zenith Calibration Co",
            "telephone": "+1-555-111-2222",
            "address": "123 Industrial Way, Dallas, TX 75001"
        }
        </script>
    </head>
    <body><h1>Services</h1></body>
    </html>
    """

    page_b = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Zenith Calibration Co",
            "telephone": "+1-555-999-8888",
            "address": "999 Ocean Blvd, Miami, FL 33101"
        }
        </script>
    </head>
    <body><h1>Locations</h1></body>
    </html>
    """

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://zenithcal.com/services", page_a, depth=1),
            make_record("https://zenithcal.com/locations", page_b, depth=1),
        ]
    )

    intel = SiteEntityAnalyzer.analyze_site(site_crawl)

    assert intel.inconsistencies_count >= 2
    attr_names = [inc.attribute for inc in intel.inconsistencies]
    assert "address" in attr_names
    assert "telephone" in attr_names

    addr_inc = next(inc for inc in intel.inconsistencies if inc.attribute == "address")
    assert len(addr_inc.conflicting_values) == 2
    assert any("Dallas" in val for val in addr_inc.conflicting_values.keys())
    assert any("Miami" in val for val in addr_inc.conflicting_values.keys())

    phone_inc = next(inc for inc in intel.inconsistencies if inc.attribute == "telephone")
    assert len(phone_inc.conflicting_values) == 2


def test_cross_page_conflicting_structured_urls():
    """Verify detection of conflicting structured data URLs for the same entity."""
    page_1 = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Global Test Lab",
            "url": "https://globaltestlab.com"
        }
        </script>
    </head>
    <body><h1>Page 1</h1></body>
    </html>
    """

    page_2 = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Global Test Lab",
            "url": "https://globaltestlab.net"
        }
        </script>
    </head>
    <body><h1>Page 2</h1></body>
    </html>
    """

    site_crawl = SiteCrawlResult(
        crawl_records=[
            make_record("https://globaltestlab.com/page1", page_1, depth=1),
            make_record("https://globaltestlab.com/page2", page_2, depth=1),
        ]
    )

    intel = SiteEntityAnalyzer.analyze_site(site_crawl)
    url_incs = [inc for inc in intel.inconsistencies if inc.attribute == "url"]
    assert len(url_incs) == 1
    assert "https://globaltestlab.com" in url_incs[0].conflicting_values
    assert "https://globaltestlab.net" in url_incs[0].conflicting_values
