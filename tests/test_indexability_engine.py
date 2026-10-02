"""
Deterministic unit and integration tests for RankIntel IndexabilityEngine (Milestone M6.2).
Validates multi-tier search eligibility without conflating crawlability, HTTP status,
indexability directives, canonicalization signals, or index confirmation telemetry.
All tests use synthetic HTML and deterministic mock data. No external network requests.
"""
import pytest
from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    CrawlabilityStatus,
    IndexabilityStatus,
    CanonicalizationSignal,
    IndexConfirmationStatus,
    SearchEligibilityRecord,
)
from rankintel.analyzers.indexability_engine import IndexabilityEngine


# ---------------------------------------------------------------------------
# 1. HTTP Status & Indexability Tests
# ---------------------------------------------------------------------------

def test_http_200_without_directives_is_indexable():
    """1. HTTP 200 without noindex directives evaluates to INDEXABLE."""
    rec = CrawlRecord(
        url="https://example.com/clean",
        normalized_url="https://example.com/clean",
        identity_url="https://example.com/clean",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><head><title>Clean Page</title></head><body>Hello</body></html>",
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.INDEXABLE
    assert result.http_status == 200
    assert any("HTTP 200 response" in note for note in result.evaluation_notes)


def test_http_301_302_redirect_evaluates_to_redirect():
    """2. HTTP 301/302 responses evaluate to REDIRECT indexability."""
    for code in (301, 302, 307, 308):
        rec = CrawlRecord(
            url="https://example.com/old",
            normalized_url="https://example.com/old",
            identity_url="https://example.com/old",
            crawl_status=CrawlStatus.REDIRECTED,
            depth=1,
            status_code=code,
        )
        result = IndexabilityEngine.evaluate_record(rec)
        assert result.indexability == IndexabilityStatus.REDIRECT
        assert any(f"HTTP {code} redirect" in note for note in result.evaluation_notes)


def test_http_404_evaluates_to_error():
    """3. HTTP 404 response evaluates to ERROR."""
    rec = CrawlRecord(
        url="https://example.com/missing",
        normalized_url="https://example.com/missing",
        identity_url="https://example.com/missing",
        crawl_status=CrawlStatus.FAILED,
        depth=1,
        status_code=404,
        raw_html="<html><body>Not Found</body></html>",
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.ERROR
    assert any("404" in note for note in result.evaluation_notes)


def test_http_500_evaluates_to_error():
    """4. HTTP 500 response evaluates to ERROR."""
    rec = CrawlRecord(
        url="https://example.com/crash",
        normalized_url="https://example.com/crash",
        identity_url="https://example.com/crash",
        crawl_status=CrawlStatus.FAILED,
        depth=1,
        status_code=500,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.ERROR
    assert any("500" in note for note in result.evaluation_notes)


# ---------------------------------------------------------------------------
# 2. Meta Robots Directive Tests
# ---------------------------------------------------------------------------

def test_meta_robots_noindex_evaluates_to_noindex():
    """5. Meta robots 'noindex' triggers NOINDEX status."""
    html = '<html><head><meta name="robots" content="noindex"></head><body>Private</body></html>'
    rec = CrawlRecord(
        url="https://example.com/private",
        normalized_url="https://example.com/private",
        identity_url="https://example.com/private",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.NOINDEX
    assert "noindex" in result.meta_robots_directives


def test_meta_robots_case_insensitive_noindex():
    """6. Meta robots casing variations (NOINDEX, nOiNdEx) are correctly parsed."""
    html = '<html><head><META NAME="ROBOTS" CONTENT="NOINDEX, FOLLOW"></head><body>Secret</body></html>'
    rec = CrawlRecord(
        url="https://example.com/secret",
        normalized_url="https://example.com/secret",
        identity_url="https://example.com/secret",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.NOINDEX
    assert "noindex" in result.meta_robots_directives
    assert "follow" in result.meta_robots_directives


def test_meta_robots_nofollow_only_remains_indexable():
    """7. Meta robots 'nofollow' alone does NOT trigger NOINDEX."""
    html = '<html><head><meta name="robots" content="nofollow"></head><body>Follow Links Blocked</body></html>'
    rec = CrawlRecord(
        url="https://example.com/nofollow-only",
        normalized_url="https://example.com/nofollow-only",
        identity_url="https://example.com/nofollow-only",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.INDEXABLE
    assert "nofollow" in result.meta_robots_directives
    assert "noindex" not in result.meta_robots_directives


def test_x_robots_tag_noindex():
    """8. X-Robots-Tag header 'noindex' triggers NOINDEX."""
    rec = CrawlRecord(
        url="https://example.com/header-noindex",
        normalized_url="https://example.com/header-noindex",
        identity_url="https://example.com/header-noindex",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body>Header Controlled</body></html>",
        response_headers={"x-robots-tag": "noindex"},
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.NOINDEX
    assert "noindex" in result.x_robots_tag_directives


def test_multiple_x_robots_tag_values_preserved():
    """9. Multiple X-Robots-Tag headers (list or comma-separated) are preserved and combined."""
    # List format (e.g. from resp.headers.get_list)
    rec1 = CrawlRecord(
        url="https://example.com/multi-header",
        normalized_url="https://example.com/multi-header",
        identity_url="https://example.com/multi-header",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body>Multi Header</body></html>",
        response_headers={"x-robots-tag": ["noindex", "noarchive", "unavailable_after: 2026-12-31"]},
    )
    result1 = IndexabilityEngine.evaluate_record(rec1)
    assert result1.indexability == IndexabilityStatus.NOINDEX
    assert "noindex" in result1.x_robots_tag_directives
    assert "noarchive" in result1.x_robots_tag_directives

    # Comma-separated format
    rec2 = CrawlRecord(
        url="https://example.com/comma-header",
        normalized_url="https://example.com/comma-header",
        identity_url="https://example.com/comma-header",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body>Comma Header</body></html>",
        response_headers={"x-robots-tag": "noindex, nosnippet"},
    )
    result2 = IndexabilityEngine.evaluate_record(rec2)
    assert result2.indexability == IndexabilityStatus.NOINDEX
    assert "noindex" in result2.x_robots_tag_directives
    assert "nosnippet" in result2.x_robots_tag_directives


def test_none_directive_triggers_noindex():
    """10. 'none' directive in meta or header triggers NOINDEX."""
    html = '<html><head><meta name="robots" content="none"></head><body>None Directive</body></html>'
    rec = CrawlRecord(
        url="https://example.com/none-directive",
        normalized_url="https://example.com/none-directive",
        identity_url="https://example.com/none-directive",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.NOINDEX
    assert "none" in result.meta_robots_directives


# ---------------------------------------------------------------------------
# 3. Canonicalization Signal Tests
# ---------------------------------------------------------------------------

def test_missing_canonical():
    """11. Missing canonical tag evaluates to MISSING signal."""
    html = '<html><head><title>No Canonical</title></head><body>No tag</body></html>'
    rec = CrawlRecord(
        url="https://example.com/no-canonical",
        normalized_url="https://example.com/no-canonical",
        identity_url="https://example.com/no-canonical",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.canonicalization == CanonicalizationSignal.MISSING
    assert result.canonical_target is None


def test_self_referencing_canonical():
    """12. Canonical pointing to current URL evaluates to SELF_REFERENCING."""
    html = '<html><head><link rel="canonical" href="https://example.com/about/"></head><body>About</body></html>'
    rec = CrawlRecord(
        url="https://example.com/about",
        normalized_url="https://example.com/about",
        identity_url="https://example.com/about",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.canonicalization == CanonicalizationSignal.SELF_REFERENCING
    assert result.canonical_target == "https://example.com/about/"


def test_canonical_elsewhere_coexists_with_indexable():
    """13. CRITICAL RULE: Canonical elsewhere + HTTP 200 = INDEXABLE + CANONICALIZED_ELSEWHERE."""
    html = '<html><head><link rel="canonical" href="https://example.com/services"></head><body>Service Duplicate</body></html>'
    rec = CrawlRecord(
        url="https://example.com/services-duplicate",
        normalized_url="https://example.com/services-duplicate",
        identity_url="https://example.com/services-duplicate",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    # Both must coexist simultaneously
    assert result.indexability == IndexabilityStatus.INDEXABLE
    assert result.canonicalization == CanonicalizationSignal.CANONICALIZED_ELSEWHERE
    assert result.canonical_target == "https://example.com/services"


def test_cross_domain_canonical():
    """14. Canonical pointing to external domain evaluates to CROSS_DOMAIN."""
    html = '<html><head><link rel="canonical" href="https://partner-syndication.org/article-1"></head><body>Syndicated</body></html>'
    rec = CrawlRecord(
        url="https://example.com/article-syndicated",
        normalized_url="https://example.com/article-syndicated",
        identity_url="https://example.com/article-syndicated",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.canonicalization == CanonicalizationSignal.CROSS_DOMAIN
    assert result.canonical_target == "https://partner-syndication.org/article-1"


def test_invalid_known_canonical_target():
    """15. Canonical target known to be 404/500 in dataset evaluates to INVALID_TARGET."""
    html = '<html><head><link rel="canonical" href="https://example.com/broken-target"></head><body>Source</body></html>'
    rec_source = CrawlRecord(
        url="https://example.com/source",
        normalized_url="https://example.com/source",
        identity_url="https://example.com/source",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    rec_target_404 = CrawlRecord(
        url="https://example.com/broken-target",
        normalized_url="https://example.com/broken-target",
        identity_url="https://example.com/broken-target",
        crawl_status=CrawlStatus.FAILED,
        depth=2,
        status_code=404,
    )
    crawl_dataset = {
        "https://example.com/broken-target": rec_target_404
    }

    result = IndexabilityEngine.evaluate_record(rec_source, crawl_records_by_url=crawl_dataset)
    assert result.canonicalization == CanonicalizationSignal.INVALID_TARGET
    assert any("known invalid" in note for note in result.evaluation_notes)


def test_uncrawled_canonical_target_unverified_not_marked_invalid():
    """Uncrawled canonical target is NOT assumed invalid; marks unverified."""
    html = '<html><head><link rel="canonical" href="https://example.com/uncrawled-page"></head><body>Source</body></html>'
    rec_source = CrawlRecord(
        url="https://example.com/source",
        normalized_url="https://example.com/source",
        identity_url="https://example.com/source",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec_source, crawl_records_by_url={})
    assert result.canonicalization == CanonicalizationSignal.CANONICALIZED_ELSEWHERE
    assert any("validity unverified" in note for note in result.evaluation_notes)


# ---------------------------------------------------------------------------
# 4. Crawlability & Index Confirmation Rules
# ---------------------------------------------------------------------------

def test_robots_blocked_does_not_equal_noindex():
    """16. robots BLOCKED means crawl blocked, NOT automatically NOINDEX."""
    rec = CrawlRecord(
        url="https://example.com/admin/dashboard",
        normalized_url="https://example.com/admin/dashboard",
        identity_url="https://example.com/admin/dashboard",
        crawl_status=CrawlStatus.BLOCKED,
        failure_reason="Disallowed by robots.txt",
        depth=1,
        status_code=0,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.crawlability == CrawlabilityStatus.BLOCKED
    # Crawlability is BLOCKED, but indexability is not arbitrarily converted to NOINDEX
    assert result.indexability != IndexabilityStatus.NOINDEX


def test_index_confirmation_defaults_strictly_to_unknown():
    """17. Confirmation strictly defaults to UNKNOWN. Never inferred from HTTP 200 or robots."""
    rec = CrawlRecord(
        url="https://example.com/popular-post",
        normalized_url="https://example.com/popular-post",
        identity_url="https://example.com/popular-post",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body>High Traffic Content</body></html>",
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.confirmation == IndexConfirmationStatus.UNKNOWN
    assert any("Index confirmation unavailable" in note for note in result.evaluation_notes)


def test_relative_canonical_resolution():
    """18. Relative canonical URLs (e.g. /category/item) are resolved to absolute URLs."""
    html = '<html><head><link rel="canonical" href="/products/item-42"></head><body>Product</body></html>'
    rec = CrawlRecord(
        url="https://example.com/products/item-42?utm_source=test",
        normalized_url="https://example.com/products/item-42",
        identity_url="https://example.com/products/item-42",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.canonical_target == "https://example.com/products/item-42"
    assert result.canonicalization == CanonicalizationSignal.SELF_REFERENCING


def test_malformed_canonical_handling():
    """19. Malformed canonical target (e.g. javascript: or empty) is safely handled as INVALID_TARGET."""
    html = '<html><head><link rel="canonical" href="javascript:alert(1)"></head><body>Bad Canonical</body></html>'
    rec = CrawlRecord(
        url="https://example.com/bad-canonical",
        normalized_url="https://example.com/bad-canonical",
        identity_url="https://example.com/bad-canonical",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.canonicalization == CanonicalizationSignal.INVALID_TARGET
    assert any("Malformed" in note for note in result.evaluation_notes)


def test_evaluation_notes_are_populated_and_explainable():
    """20. Explainable notes are populated across all 5 evaluation dimensions."""
    html = """<html>
        <head>
            <meta name="robots" content="index, follow">
            <link rel="canonical" href="https://example.com/landing">
        </head>
        <body>Landing Page</body>
    </html>"""
    rec = CrawlRecord(
        url="https://example.com/landing",
        normalized_url="https://example.com/landing",
        identity_url="https://example.com/landing",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert len(result.evaluation_notes) >= 4
    notes_str = " ".join(result.evaluation_notes)
    assert "robots.txt" in notes_str
    assert "HTTP 200" in notes_str
    assert "Self-referencing" in notes_str
    assert "Index confirmation" in notes_str


# ---------------------------------------------------------------------------
# 5. Combinations & Edge Cases
# ---------------------------------------------------------------------------

def test_combination_robots_blocked_plus_http_200():
    """Combination: robots BLOCKED + HTTP 200 response (e.g. if fetched bypassing robots)."""
    rec = CrawlRecord(
        url="https://example.com/hidden-api",
        normalized_url="https://example.com/hidden-api",
        identity_url="https://example.com/hidden-api",
        crawl_status=CrawlStatus.BLOCKED,
        failure_reason="Disallowed by robots.txt",
        depth=1,
        status_code=200,
        raw_html="<html><body>API Info</body></html>",
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.crawlability == CrawlabilityStatus.BLOCKED
    assert result.indexability == IndexabilityStatus.INDEXABLE
    assert result.confirmation == IndexConfirmationStatus.UNKNOWN


def test_combination_http_200_noindex_canonical_elsewhere():
    """Combination: HTTP 200 + noindex + canonical elsewhere."""
    html = """<html>
        <head>
            <meta name="robots" content="noindex">
            <link rel="canonical" href="https://example.com/master-page">
        </head>
        <body>Noindex with Canonical</body>
    </html>"""
    rec = CrawlRecord(
        url="https://example.com/variant-page",
        normalized_url="https://example.com/variant-page",
        identity_url="https://example.com/variant-page",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.NOINDEX
    assert result.canonicalization == CanonicalizationSignal.CANONICALIZED_ELSEWHERE
    assert result.canonical_target == "https://example.com/master-page"


def test_combination_http_200_canonical_elsewhere_confirmation_unknown():
    """Combination: HTTP 200 + canonical elsewhere + confirmation UNKNOWN."""
    html = '<html><head><link rel="canonical" href="https://example.com/target"></head><body>Test</body></html>'
    rec = CrawlRecord(
        url="https://example.com/source",
        normalized_url="https://example.com/source",
        identity_url="https://example.com/source",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.INDEXABLE
    assert result.canonicalization == CanonicalizationSignal.CANONICALIZED_ELSEWHERE
    assert result.confirmation == IndexConfirmationStatus.UNKNOWN


def test_combination_http_200_xrobots_noindex():
    """Combination: HTTP 200 HTML without meta tag, but X-Robots-Tag: noindex in header."""
    rec = CrawlRecord(
        url="https://example.com/pdf-or-page",
        normalized_url="https://example.com/pdf-or-page",
        identity_url="https://example.com/pdf-or-page",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body>Clean HTML without meta tags</body></html>",
        response_headers={"x-robots-tag": "noindex"},
    )
    result = IndexabilityEngine.evaluate_record(rec)
    assert result.indexability == IndexabilityStatus.NOINDEX
    assert result.http_status == 200


# ---------------------------------------------------------------------------
# 6. Site-Wide Multi-Page Evaluation & Inbound Links Tallying
# ---------------------------------------------------------------------------

def test_evaluate_site_inbound_links_and_sitemap():
    """Site-wide evaluation calculates inbound links and sitemap flags across all records."""
    rec_home = CrawlRecord(
        url="https://example.com",
        normalized_url="https://example.com",
        identity_url="https://example.com",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><head><title>Home</title></head><body><a href='/about'>About</a><a href='/services'>Services</a></body></html>",
        discovered_links=["https://example.com/about", "https://example.com/services"],
    )
    rec_about = CrawlRecord(
        url="https://example.com/about",
        normalized_url="https://example.com/about",
        identity_url="https://example.com/about",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><head><title>About</title></head><body><a href='/services'>Services</a></body></html>",
        discovered_links=["https://example.com/services"],
    )
    rec_services = CrawlRecord(
        url="https://example.com/services",
        normalized_url="https://example.com/services",
        identity_url="https://example.com/services",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><head><title>Services</title></head><body><a href='/'>Home</a></body></html>",
        discovered_links=["https://example.com"],
    )

    site_crawl = SiteCrawlResult(
        pages_crawled=3,
        crawl_depth=1,
        crawl_records=[rec_home, rec_about, rec_services],
    )

    sitemaps = {"https://example.com", "https://example.com/about"}

    results = IndexabilityEngine.evaluate_site(
        site_crawl=site_crawl,
        sitemap_urls=sitemaps,
    )

    assert len(results) == 3
    # /services is linked from / and from /about -> inbound count = 2
    assert results["https://example.com/services"].inbound_links_count == 2
    # /about is linked from / -> inbound count = 1
    assert results["https://example.com/about"].inbound_links_count == 1
    # Check sitemap inclusion
    assert results["https://example.com"].in_sitemap is True
    assert results["https://example.com/about"].in_sitemap is True
    assert results["https://example.com/services"].in_sitemap is False
    # Verified attached to site_crawl
    assert site_crawl.search_eligibility == results


def test_authenticated_telemetry_extension_point():
    """Authenticated GSC/Bing telemetry sets CONFIRMED_INDEXED / CONFIRMED_NOT_INDEXED."""
    # Indexed
    status_idx, note_idx = IndexabilityEngine.evaluate_confirmation({"status": "INDEXED"})
    assert status_idx == IndexConfirmationStatus.CONFIRMED_INDEXED
    assert "Confirmed indexed" in note_idx

    # Not Indexed
    status_not, note_not = IndexabilityEngine.evaluate_confirmation({"status": "NOT_INDEXED"})
    assert status_not == IndexConfirmationStatus.CONFIRMED_NOT_INDEXED
    assert "Confirmed not indexed" in note_not

    # None / Unauthenticated defaults strictly to UNKNOWN
    status_unk, note_unk = IndexabilityEngine.evaluate_confirmation(None)
    assert status_unk == IndexConfirmationStatus.UNKNOWN


def test_canonical_target_is_redirect_marked_invalid():
    """Canonical target known to be a redirect in dataset evaluates to INVALID_TARGET."""
    html = '<html><head><link rel="canonical" href="https://example.com/redirecting-target"></head></html>'
    rec_source = CrawlRecord(
        url="https://example.com/source",
        normalized_url="https://example.com/source",
        identity_url="https://example.com/source",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=html,
    )
    rec_target_redirect = CrawlRecord(
        url="https://example.com/redirecting-target",
        normalized_url="https://example.com/redirecting-target",
        identity_url="https://example.com/redirecting-target",
        crawl_status=CrawlStatus.REDIRECTED,
        depth=2,
        status_code=301,
    )
    crawl_dataset = {
        "https://example.com/redirecting-target": rec_target_redirect
    }

    result = IndexabilityEngine.evaluate_record(rec_source, crawl_records_by_url=crawl_dataset)
    assert result.canonicalization == CanonicalizationSignal.INVALID_TARGET
    assert any("redirect target" in note for note in result.evaluation_notes)


def test_robots_parser_in_memory_allowed_and_blocked():
    """In-memory robots parser correctly marks ALLOWED or BLOCKED."""
    from urllib.robotparser import RobotFileParser
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /admin", "Allow: /public"])

    allowed_st, allowed_note = IndexabilityEngine.evaluate_crawlability(
        "https://example.com/public", robots_parser=rp
    )
    assert allowed_st == CrawlabilityStatus.ALLOWED
    assert "allows crawling" in allowed_note

    blocked_st, blocked_note = IndexabilityEngine.evaluate_crawlability(
        "https://example.com/admin", robots_parser=rp
    )
    assert blocked_st == CrawlabilityStatus.BLOCKED
    assert "disallows crawling" in blocked_note


def test_queued_and_blocked_records_evaluate_to_unknown_indexability():
    """Queued and robots-blocked records must evaluate to UNKNOWN indexability, not ERROR."""
    rec_queued = CrawlRecord(
        url="https://example.com/queued-page",
        normalized_url="https://example.com/queued-page",
        identity_url="https://example.com/queued-page",
        crawl_status=CrawlStatus.QUEUED,
        depth=2,
        status_code=0,
    )
    res_queued = IndexabilityEngine.evaluate_record(rec_queued)
    assert res_queued.indexability == IndexabilityStatus.UNKNOWN
    assert any("not crawled" in n for n in res_queued.evaluation_notes)

    rec_blocked = CrawlRecord(
        url="https://example.com/blocked-page",
        normalized_url="https://example.com/blocked-page",
        identity_url="https://example.com/blocked-page",
        crawl_status=CrawlStatus.BLOCKED,
        depth=1,
        status_code=0,
    )
    res_blocked = IndexabilityEngine.evaluate_record(rec_blocked)
    assert res_blocked.crawlability == CrawlabilityStatus.BLOCKED
    assert res_blocked.indexability == IndexabilityStatus.UNKNOWN
    assert any("blocked by robots.txt" in n for n in res_blocked.evaluation_notes)


