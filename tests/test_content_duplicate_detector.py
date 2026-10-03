"""
Unit tests for SiteContentAnalyzer (Phase 8.1 multi-page content intelligence).
Validates exact duplicate main-content clustering, near-duplicate SimHash/shingle detection,
repeated boilerplate text extraction, and site-wide structure aggregation.
"""
import pytest
from rankintel.models.schema import (
    SiteCrawlResult,
    CrawlRecord,
    CrawlStatus,
)
from rankintel.analyzers.content_analyzer import SiteContentAnalyzer


def make_record(url: str, raw_html: str, status_code: int = 200) -> CrawlRecord:
    return CrawlRecord(
        url=url,
        normalized_url=url,
        identity_url=url,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=status_code,
        raw_html=raw_html,
    )


def test_exact_duplicate_clustering():
    html_shared = """
    <!DOCTYPE html>
    <html>
    <head><title>Product Specs</title></head>
    <body>
        <main>
            <h1>Standard Widget Model 4000</h1>
            <p>This precision manufactured stainless steel component operates at extreme temperature thresholds.
            It complies with ASTM B117 salt spray endurance guidelines and ISO 9001 certified QA standards.</p>
        </main>
        <footer><p>Footer Copyright 2026</p></footer>
    </body>
    </html>
    """

    records = [
        make_record("https://example.com/widget-a", html_shared),
        make_record("https://example.com/widget-b", html_shared),
        make_record("https://example.com/widget-c", html_shared),
        make_record(
            "https://example.com/distinct-product",
            "<html><body><main><h1>Distinct Tool</h1><p>A completely different pneumatic torque wrench for aviation maintenance.</p></main></body></html>"
        ),
    ]

    site_crawl = SiteCrawlResult(crawl_records=records)
    summary = SiteContentAnalyzer.analyze_site(site_crawl)

    assert summary.total_pages_evaluated == 4
    assert summary.exact_duplicate_clusters_count == 1

    cluster = summary.exact_duplicate_clusters[0]
    assert len(cluster.urls) == 3
    assert "https://example.com/widget-a" in cluster.urls
    assert "https://example.com/widget-b" in cluster.urls
    assert "https://example.com/widget-c" in cluster.urls
    assert "https://example.com/distinct-product" not in cluster.urls


def test_near_duplicate_detection():
    # Two pages with 85%+ identical wording but slight regional variation
    base_editorial = (
        "Our enterprise compliance audit verifies regulatory conformity across European Union directives. "
        "We review technical documentation, risk management files, and declarations of conformity. "
        "Certified lead assessors conduct on-site evaluations for manufacturing facilities. "
        "Our accreditation covers machinery safety, low voltage equipment, and electromagnetic compatibility."
    )

    page_uk = f"""
    <html><head><title>Compliance Audit UK</title></head>
    <body><main>
        <h1>UK Regulatory Compliance Auditing</h1>
        <p>{base_editorial}</p>
        <p>Contact our London regional office for quotation.</p>
    </main></body></html>
    """

    page_eu = f"""
    <html><head><title>Compliance Audit EU</title></head>
    <body><main>
        <h1>EU Regulatory Compliance Auditing</h1>
        <p>{base_editorial}</p>
        <p>Contact our Berlin regional office for quotation.</p>
    </main></body></html>
    """

    page_unrelated = """
    <html><head><title>Careers Portal</title></head>
    <body><main>
        <h1>Join Our Engineering Team</h1>
        <p>We are actively seeking senior cloud infrastructure architects and automated test engineers.</p>
    </main></body></html>
    """

    records = [
        make_record("https://example.com/uk/audit", page_uk),
        make_record("https://example.com/eu/audit", page_eu),
        make_record("https://example.com/careers", page_unrelated),
    ]

    site_crawl = SiteCrawlResult(crawl_records=records)
    summary = SiteContentAnalyzer.analyze_site(site_crawl)

    assert summary.near_duplicate_pairs_count >= 1
    pair = summary.near_duplicate_pairs[0]
    assert "https://example.com/uk/audit" in (pair.url_a, pair.url_b)
    assert "https://example.com/eu/audit" in (pair.url_a, pair.url_b)
    assert pair.similarity_percentage >= 80.0
    assert pair.method == "simhash_shingle_jaccard"

    # Careers page should not be in any near-duplicate pair
    for p in summary.near_duplicate_pairs:
        assert p.url_a != "https://example.com/careers"
        assert p.url_b != "https://example.com/careers"


def test_repeated_boilerplate_blocks_detection():
    # Common shared legal disclaimer appearing on all 4 pages
    shared_disclaimer = (
        "Confidentiality Notice: The information contained in this technical certification bulletin "
        "is intended solely for accredited personnel and authorized regulatory testing authorities."
    )

    records = []
    for i in range(1, 5):
        html = f"""
        <html><body>
            <main><h1>Page Number {i} Unique Title</h1><p>Unique body text specifically dedicated to item {i} in the catalog.</p></main>
            <div class="legal-notice"><p>{shared_disclaimer}</p></div>
        </body></html>
        """
        records.append(make_record(f"https://example.com/page-{i}", html))

    site_crawl = SiteCrawlResult(crawl_records=records)
    summary = SiteContentAnalyzer.analyze_site(site_crawl)

    assert summary.repeated_boilerplate_blocks_count >= 1
    block = summary.repeated_boilerplate_blocks[0]
    assert block.page_count == 4
    assert "confidentiality notice" in block.text_snippet.lower()


def test_site_wide_content_telemetry_aggregation():
    # 1 thin page, 1 heading skip page, 1 title-H1 mismatch page, 1 clean page
    rec_thin = make_record(
        "https://example.com/thin",
        "<html><body><main><h1>Thin</h1><p>One word.</p></main></body></html>"
    )
    rec_skips = make_record(
        "https://example.com/skips",
        "<html><body><main><h1>Root</h1><h3>Skipped to H3</h3><p>Content text</p></main></body></html>"
    )
    rec_mismatch = make_record(
        "https://example.com/mismatch",
        "<html><head><title>Alpha Gamma</title></head><body><main><h1>Zeta Theta</h1><p>Content text</p></main></body></html>"
    )
    rec_clean = make_record(
        "https://example.com/clean",
        "<html><head><title>Testing Standards</title></head><body><main><h1>Testing Standards</h1><p>Substantive text</p><h2>Section</h2><p>Body</p></main></body></html>"
    )

    site_crawl = SiteCrawlResult(crawl_records=[rec_thin, rec_skips, rec_mismatch, rec_clean])
    summary = SiteContentAnalyzer.analyze_site(site_crawl)

    assert "https://example.com/thin" in summary.thin_content_urls
    assert "https://example.com/skips" in summary.heading_skip_urls
    assert "https://example.com/mismatch" in summary.title_h1_mismatch_urls
    assert "https://example.com/clean" not in summary.thin_content_urls
    assert "https://example.com/clean" not in summary.heading_skip_urls
