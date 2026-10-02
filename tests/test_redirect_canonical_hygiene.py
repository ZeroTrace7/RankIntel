"""
Deterministic unit and integration tests for RankIntel Milestone M6.3:
Redirect Chains, Canonical Chains, and URL Hygiene Analysis Engine.
Offline execution — zero live HTTP requests.
"""
import pytest
from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    RedirectHop,
    RedirectChainStatus,
    RedirectChainRecord,
    CanonicalChainStatus,
    CanonicalChainRecord,
    HygieneAnomalyType,
    HygieneEvidenceType,
    HygieneAnomaly,
    IndexabilityStatus,
    CanonicalizationSignal,
)
from rankintel.analyzers.record_lookup import RecordLookupIndex
from rankintel.analyzers.redirect_resolver import RedirectResolver
from rankintel.analyzers.canonical_resolver import CanonicalResolver
from rankintel.analyzers.hygiene_detector import UrlHygieneDetector
from rankintel.analyzers.hygiene_engine import UrlHygieneEngine
from rankintel.analyzers.indexability_engine import IndexabilityEngine


# ---------------------------------------------------------------------------
# Helpers for synthetic record generation
# ---------------------------------------------------------------------------

def make_record(
    url: str,
    status_code: int = 200,
    crawl_status: CrawlStatus = CrawlStatus.FETCHED,
    raw_html: str = "",
    redirect_url: str = None,
    location_header: str = None,
    fetch_time_sec: float = 0.05,
    discovered_links: list = None,
) -> CrawlRecord:
    headers = {}
    if location_header:
        headers["location"] = location_header
    elif redirect_url:
        headers["location"] = redirect_url

    failure_reason = None
    if redirect_url:
        failure_reason = f"Redirected to {redirect_url}"
    elif status_code >= 400:
        failure_reason = f"HTTP {status_code}"

    from rankintel.crawler.normalizer import UrlNormalizer
    return CrawlRecord(
        url=url,
        normalized_url=UrlNormalizer.normalize_for_crawl(url),
        identity_url=UrlNormalizer.get_url_identity(url),
        crawl_status=crawl_status,
        depth=1,
        status_code=status_code,
        raw_html=raw_html,
        redirect_url=redirect_url,
        response_headers=headers,
        fetch_time_sec=fetch_time_sec,
        failure_reason=failure_reason,
        discovered_links=discovered_links or [],
    )


# ===========================================================================
# 1. REDIRECT CHAIN RESOLUTION TESTS
# ===========================================================================

def test_r01_single_hop_redirect():
    """R-01: 301 -> 200 OK resolves to 1-hop RESOLVED."""
    rec_a = make_record("https://example.com/old", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/new")
    rec_b = make_record("https://example.com/new", status_code=200, crawl_status=CrawlStatus.FETCHED)

    chain = RedirectResolver.resolve_chain("https://example.com/old", [rec_a, rec_b])
    assert chain.status == RedirectChainStatus.RESOLVED
    assert chain.total_hops == 1
    assert chain.final_url == "https://example.com/new"
    assert not chain.has_loop
    assert len(chain.hops) == 1
    assert chain.hops[0].status_code == 301
    assert chain.hops[0].location == "https://example.com/new"


def test_r02_multi_hop_redirect():
    """R-02: 301 -> 301 -> 200 OK resolves to MULTI_HOP with total_hops=2."""
    rec_a = make_record("https://example.com/a", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/b")
    rec_b = make_record("https://example.com/b", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/c")
    rec_c = make_record("https://example.com/c", status_code=200, crawl_status=CrawlStatus.FETCHED)

    chain = RedirectResolver.resolve_chain("https://example.com/a", [rec_a, rec_b, rec_c])
    assert chain.status == RedirectChainStatus.MULTI_HOP
    assert chain.total_hops == 2
    assert chain.final_url == "https://example.com/c"
    assert not chain.has_loop
    assert chain.hops[0].location == "https://example.com/b"
    assert chain.hops[1].location == "https://example.com/c"


def test_r03_mixed_3xx_chain():
    """R-03: 302 -> 301 -> 200 OK resolves to MULTI_HOP."""
    rec_a = make_record("https://example.com/temp", status_code=302, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/perm")
    rec_b = make_record("https://example.com/perm", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/final")
    rec_c = make_record("https://example.com/final", status_code=200)

    chain = RedirectResolver.resolve_chain("https://example.com/temp", [rec_a, rec_b, rec_c])
    assert chain.status == RedirectChainStatus.MULTI_HOP
    assert chain.total_hops == 2
    assert chain.hops[0].status_code == 302
    assert chain.hops[1].status_code == 301
    assert chain.final_url == "https://example.com/final"


def test_r04_direct_redirect_loop():
    """R-04: Direct circular loop A -> B -> A detected."""
    rec_a = make_record("https://example.com/a", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/b")
    rec_b = make_record("https://example.com/b", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/a")

    chain = RedirectResolver.resolve_chain("https://example.com/a", [rec_a, rec_b])
    assert chain.status == RedirectChainStatus.LOOP
    assert chain.has_loop is True
    assert chain.total_hops == 2
    assert any("loop detected" in note.lower() for note in chain.notes)


def test_r05_multi_node_redirect_loop():
    """R-05: Multi-node circular loop A -> B -> C -> B detected."""
    rec_a = make_record("https://example.com/a", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/b")
    rec_b = make_record("https://example.com/b", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/c")
    rec_c = make_record("https://example.com/c", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/b")

    chain = RedirectResolver.resolve_chain("https://example.com/a", [rec_a, rec_b, rec_c])
    assert chain.status == RedirectChainStatus.LOOP
    assert chain.has_loop is True
    assert chain.total_hops == 3


def test_r06_exceeding_hop_limit():
    """R-06: Chain exceeding max_hops halts safely with EXCEEDED_MAX_HOPS."""
    # Generate 15 distinct hops
    records = []
    for i in range(15):
        records.append(
            make_record(
                f"https://example.com/step{i}",
                status_code=301,
                crawl_status=CrawlStatus.REDIRECTED,
                redirect_url=f"https://example.com/step{i+1}",
            )
        )
    records.append(make_record("https://example.com/step15", status_code=200))

    chain = RedirectResolver.resolve_chain("https://example.com/step0", records, max_hops=10)
    assert chain.status == RedirectChainStatus.EXCEEDED_MAX_HOPS
    assert chain.total_hops == 10
    assert len(chain.hops) == 10
    assert not chain.has_loop


def test_r07_broken_redirect_target_404():
    """R-07: Redirect target returning 404 marked BROKEN_TARGET."""
    rec_a = make_record("https://example.com/old", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/dead")
    rec_b = make_record("https://example.com/dead", status_code=404, crawl_status=CrawlStatus.FAILED)

    chain = RedirectResolver.resolve_chain("https://example.com/old", [rec_a, rec_b])
    assert chain.status == RedirectChainStatus.BROKEN_TARGET
    assert chain.total_hops == 1
    assert chain.final_url == "https://example.com/dead"


def test_r08_broken_redirect_target_500():
    """R-08: Redirect target returning 500 marked BROKEN_TARGET."""
    rec_a = make_record("https://example.com/old", status_code=302, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/server-error")
    rec_b = make_record("https://example.com/server-error", status_code=500, crawl_status=CrawlStatus.FAILED)

    chain = RedirectResolver.resolve_chain("https://example.com/old", [rec_a, rec_b])
    assert chain.status == RedirectChainStatus.BROKEN_TARGET
    assert chain.final_url == "https://example.com/server-error"


def test_r09_missing_location_header():
    """R-09: 3xx redirect missing Location header evaluates to MISSING_LOCATION."""
    rec = CrawlRecord(
        url="https://example.com/no-loc",
        normalized_url="https://example.com/no-loc",
        identity_url="https://example.com/no-loc",
        crawl_status=CrawlStatus.REDIRECTED,
        depth=1,
        status_code=301,
        response_headers={},
    )
    chain = RedirectResolver.resolve_chain("https://example.com/no-loc", [rec])
    assert chain.status == RedirectChainStatus.MISSING_LOCATION
    assert chain.total_hops == 0


def test_r10_relative_location_resolution():
    """R-10: Relative Location header is properly resolved to absolute URL."""
    rec_a = make_record("https://example.com/company/history", status_code=301, crawl_status=CrawlStatus.REDIRECTED, location_header="/about")
    rec_b = make_record("https://example.com/about", status_code=200)

    chain = RedirectResolver.resolve_chain("https://example.com/company/history", [rec_a, rec_b])
    assert chain.status == RedirectChainStatus.RESOLVED
    assert chain.hops[0].location == "https://example.com/about"
    assert chain.final_url == "https://example.com/about"


def test_r11_absolute_location_resolution():
    """R-11: Absolute Location header resolved correctly."""
    rec_a = make_record("https://example.com/start", status_code=301, crawl_status=CrawlStatus.REDIRECTED, location_header="https://example.com/target")
    rec_b = make_record("https://example.com/target", status_code=200)

    chain = RedirectResolver.resolve_chain("https://example.com/start", [rec_a, rec_b])
    assert chain.status == RedirectChainStatus.RESOLVED
    assert chain.final_url == "https://example.com/target"


def test_r12_cross_domain_location():
    """R-12: Cross-domain Location header resolved properly."""
    rec_a = make_record("https://example.com/external", status_code=301, crawl_status=CrawlStatus.REDIRECTED, location_header="https://partner.org/landing")
    # Partner is outside crawl boundary, so unverified in dataset
    chain = RedirectResolver.resolve_chain("https://example.com/external", [rec_a])
    assert chain.status == RedirectChainStatus.UNVERIFIED_TARGET
    assert chain.total_hops == 1
    assert chain.hops[0].location == "https://partner.org/landing"


def test_r13_redirect_latency_capture():
    """R-13: Redirect hop latencies and total latency captured."""
    rec_a = make_record("https://example.com/a", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/b", fetch_time_sec=0.045)
    rec_b = make_record("https://example.com/b", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/c", fetch_time_sec=0.055)
    rec_c = make_record("https://example.com/c", status_code=200)

    chain = RedirectResolver.resolve_chain("https://example.com/a", [rec_a, rec_b, rec_c])
    assert chain.hops[0].latency_ms == pytest.approx(45.0, 0.1)
    assert chain.hops[1].latency_ms == pytest.approx(55.0, 0.1)
    assert chain.total_latency_ms == pytest.approx(100.0, 0.1)


def test_r14_uncrawled_redirect_target():
    """R-14: Redirect target outside crawl dataset is UNVERIFIED_TARGET (never assumed dead)."""
    rec_a = make_record("https://example.com/old", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/unvisited")
    # rec_b is NOT in dataset
    chain = RedirectResolver.resolve_chain("https://example.com/old", [rec_a])
    assert chain.status == RedirectChainStatus.UNVERIFIED_TARGET
    assert chain.total_hops == 1
    assert chain.final_url == "https://example.com/unvisited"
    assert any("could not be verified" in note for note in chain.notes)


# ===========================================================================
# 2. CANONICAL CHAIN ANALYSIS TESTS
# ===========================================================================

def test_c01_direct_canonical_a_to_b():
    """C-01: Direct canonical A -> B where B is 200 with self-canonical."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/target"></head></html>'
    html_b = '<html><head><link rel="canonical" href="https://example.com/target"></head></html>'
    rec_a = make_record("https://example.com/source", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/target", status_code=200, raw_html=html_b)

    chain = CanonicalResolver.resolve_chain("https://example.com/source", [rec_a, rec_b])
    assert chain.status == CanonicalChainStatus.RESOLVED
    assert chain.total_hops == 1
    assert chain.declared_canonical == "https://example.com/target"
    assert chain.final_canonical == "https://example.com/target"
    assert not chain.has_loop
    assert not chain.points_to_redirect
    assert not chain.points_to_dead_url


def test_c02_canonical_chain_a_b_c():
    """C-02: Canonical chain A -> B -> C where B declares C and C is self-canonical."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/b"></head></html>'
    html_b = '<html><head><link rel="canonical" href="https://example.com/c"></head></html>'
    html_c = '<html><head><link rel="canonical" href="https://example.com/c"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/b", status_code=200, raw_html=html_b)
    rec_c = make_record("https://example.com/c", status_code=200, raw_html=html_c)

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a, rec_b, rec_c])
    assert chain.status == CanonicalChainStatus.CHAIN
    assert chain.total_hops == 2
    assert chain.declared_canonical == "https://example.com/b"
    assert chain.final_canonical == "https://example.com/c"
    assert chain.hops == ["https://example.com/a", "https://example.com/b", "https://example.com/c"]


def test_c03_canonical_loop_a_b_a():
    """C-03: Canonical loop A -> B -> A detected."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/b"></head></html>'
    html_b = '<html><head><link rel="canonical" href="https://example.com/a"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/b", status_code=200, raw_html=html_b)

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a, rec_b])
    assert chain.status == CanonicalChainStatus.LOOP
    assert chain.has_loop is True
    assert chain.declared_canonical == "https://example.com/b"


def test_c04_multi_node_canonical_loop():
    """C-04: Multi-node canonical loop A -> B -> C -> B detected."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/b"></head></html>'
    html_b = '<html><head><link rel="canonical" href="https://example.com/c"></head></html>'
    html_c = '<html><head><link rel="canonical" href="https://example.com/b"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/b", status_code=200, raw_html=html_b)
    rec_c = make_record("https://example.com/c", status_code=200, raw_html=html_c)

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a, rec_b, rec_c])
    assert chain.status == CanonicalChainStatus.LOOP
    assert chain.has_loop is True


def test_c05_canonical_target_redirects_preserves_relationship():
    """
    C-05 / Correction 3 Rule:
    A (canonical) -> B
    B (301) -> C
    Preserves:
    - declared_canonical: B
    - points_to_redirect: True
    - final_canonical: C
    Does not collapse to A -> C.
    """
    html_a = '<html><head><link rel="canonical" href="https://example.com/b"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/b", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/c")
    rec_c = make_record("https://example.com/c", status_code=200, raw_html='<html><head><link rel="canonical" href="https://example.com/c"></head></html>')

    redirect_index = RedirectResolver.resolve_site(SiteCrawlResult(crawl_records=[rec_a, rec_b, rec_c]))

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a, rec_b, rec_c], redirect_chains=redirect_index)
    assert chain.status == CanonicalChainStatus.POINTS_TO_REDIRECT
    assert chain.points_to_redirect is True
    assert chain.declared_canonical == "https://example.com/b"
    assert chain.final_canonical == "https://example.com/c"
    assert chain.hops == ["https://example.com/a", "https://example.com/b"]


def test_c06_canonical_target_404():
    """C-06: Canonical target returning 404 marked POINTS_TO_DEAD_URL."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/dead"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/dead", status_code=404, crawl_status=CrawlStatus.FAILED)

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a, rec_b])
    assert chain.status == CanonicalChainStatus.POINTS_TO_DEAD_URL
    assert chain.points_to_dead_url is True
    assert chain.declared_canonical == "https://example.com/dead"


def test_c07_canonical_target_500():
    """C-07: Canonical target returning 500 marked POINTS_TO_DEAD_URL."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/err"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/err", status_code=500, crawl_status=CrawlStatus.FAILED)

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a, rec_b])
    assert chain.status == CanonicalChainStatus.POINTS_TO_DEAD_URL
    assert chain.points_to_dead_url is True


def test_c08_canonical_target_absent_from_crawl():
    """C-08: Canonical target not crawled is UNVERIFIED_TARGET (never assumed dead)."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/uncrawled"></head></html>'
    rec_a = make_record("https://example.com/a", status_code=200, raw_html=html_a)

    chain = CanonicalResolver.resolve_chain("https://example.com/a", [rec_a])
    assert chain.status == CanonicalChainStatus.UNVERIFIED_TARGET
    assert chain.declared_canonical == "https://example.com/uncrawled"
    assert not chain.points_to_dead_url
    assert any("validity unverified" in note for note in chain.notes)


def test_c09_self_referencing_canonical():
    """C-09: Canonical pointing to self evaluates to SELF_REFERENCING with total_hops=0."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/self"></head></html>'
    rec_a = make_record("https://example.com/self", status_code=200, raw_html=html_a)

    chain = CanonicalResolver.resolve_chain("https://example.com/self", [rec_a])
    assert chain.status == CanonicalChainStatus.SELF_REFERENCING
    assert chain.total_hops == 0
    assert chain.declared_canonical == "https://example.com/self"
    assert chain.final_canonical == "https://example.com/self"


def test_c10_missing_canonical_tag():
    """C-10: Missing canonical tag evaluates to MISSING with total_hops=0."""
    html_a = '<html><head><title>No Tag</title></head></html>'
    rec_a = make_record("https://example.com/clean", status_code=200, raw_html=html_a)

    chain = CanonicalResolver.resolve_chain("https://example.com/clean", [rec_a])
    assert chain.status == CanonicalChainStatus.MISSING
    assert chain.declared_canonical is None
    assert chain.final_canonical is None
    assert chain.total_hops == 0


def test_c11_canonical_does_not_alter_indexability():
    """C-11: Canonical pointing elsewhere coexists with HTTP 200 indexability."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/primary"></head></html>'
    rec_a = make_record("https://example.com/variant", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/primary", status_code=200, raw_html='<html><head><link rel="canonical" href="https://example.com/primary"></head></html>')

    # Indexability evaluation
    eligibility = IndexabilityEngine.evaluate_record(rec_a, crawl_records_by_url={"https://example.com/primary": rec_b})
    assert eligibility.indexability == IndexabilityStatus.INDEXABLE
    assert eligibility.canonicalization == CanonicalizationSignal.CANONICALIZED_ELSEWHERE

    # Canonical chain evaluation
    chain = CanonicalResolver.resolve_chain("https://example.com/variant", [rec_a, rec_b])
    assert chain.status == CanonicalChainStatus.RESOLVED
    assert chain.declared_canonical == "https://example.com/primary"


# ===========================================================================
# 3. URL HYGIENE ANALYSIS TESTS
# ===========================================================================

def test_h01_trailing_slash_identical_extracted_text():
    """H-01 / Correction 2: /about and /about/ both 200 with identical text -> IDENTICAL_EXTRACTED_TEXT."""
    html = '<html><head><title>About</title></head><body><h1>About Us</h1><p>Company history and team.</p></body></html>'
    rec_a = make_record("https://example.com/about", status_code=200, raw_html=html)
    rec_b = make_record("https://example.com/about/", status_code=200, raw_html=html)

    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/about", "https://example.com/about/", rec_a=rec_a, rec_b=rec_b)
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.TRAILING_SLASH
    assert anomaly.evidence_type == HygieneEvidenceType.IDENTICAL_EXTRACTED_TEXT
    assert any("full-document equivalence not established" in note for note in anomaly.evidence_notes)


def test_h02_trailing_slash_redirect_equivalent():
    """H-02: /about 301 redirects to /about/ -> REDIRECT_EQUIVALENT."""
    rec_a = make_record("https://example.com/about", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/about/")
    rec_b = make_record("https://example.com/about/", status_code=200, raw_html="<html><body>About</body></html>")

    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/about", "https://example.com/about/", rec_a=rec_a, rec_b=rec_b)
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.TRAILING_SLASH
    assert anomaly.evidence_type == HygieneEvidenceType.REDIRECT_EQUIVALENT
    assert anomaly.primary_url == "https://example.com/about/"
    assert anomaly.duplicate_url == "https://example.com/about"


def test_h03_trailing_slash_canonical_equivalent():
    """H-03: /about declares /about/ as canonical -> CANONICAL_EQUIVALENT."""
    html_a = '<html><head><link rel="canonical" href="https://example.com/about/"></head><body>About</body></html>'
    html_b = '<html><head><link rel="canonical" href="https://example.com/about/"></head><body>About</body></html>'
    rec_a = make_record("https://example.com/about", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/about/", status_code=200, raw_html=html_b)

    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/about", "https://example.com/about/", rec_a=rec_a, rec_b=rec_b)
    assert anomaly is not None
    assert anomaly.evidence_type == HygieneEvidenceType.CANONICAL_EQUIVALENT
    assert anomaly.primary_url == "https://example.com/about/"
    assert anomaly.duplicate_url == "https://example.com/about"


def test_h04_trailing_slash_unverified():
    """H-04 / Correction 4: Uncrawled representations are POTENTIAL_DUPLICATE_REPRESENTATION (heuristic only)."""
    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/about", "https://example.com/about/", rec_a=None, rec_b=None)
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.TRAILING_SLASH
    assert anomaly.evidence_type == HygieneEvidenceType.POTENTIAL_DUPLICATE_REPRESENTATION
    assert any("could not be verified" in note for note in anomaly.evidence_notes)


def test_h05_trailing_slash_distinct_content():
    """H-05: /about and /about/ both 200 but have different content -> DISTINCT_CONTENT_VARIANT."""
    html_a = '<html><body><h1>About Page A</h1><p>Specific text for page A</p></body></html>'
    html_b = '<html><body><h1>About Page B</h1><p>Completely different text for page B</p></body></html>'
    rec_a = make_record("https://example.com/about", status_code=200, raw_html=html_a)
    rec_b = make_record("https://example.com/about/", status_code=200, raw_html=html_b)

    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/about", "https://example.com/about/", rec_a=rec_a, rec_b=rec_b)
    assert anomaly is not None
    assert anomaly.evidence_type == HygieneEvidenceType.DISTINCT_CONTENT_VARIANT
    assert any("extracted body text differs" in note for note in anomaly.evidence_notes)


def test_h06_protocol_http_vs_https():
    """H-06: http:// vs https:// evaluates to PROTOCOL_HTTP_HTTPS with HTTPS as primary."""
    anomaly = UrlHygieneDetector.analyze_pair("http://example.com/contact", "https://example.com/contact")
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.PROTOCOL_HTTP_HTTPS
    assert anomaly.primary_url == "https://example.com/contact"
    assert anomaly.duplicate_url == "http://example.com/contact"


def test_h07_www_vs_non_www():
    """H-07: www vs non-www evaluates to WWW_SUBDOMAIN with non-www as default primary."""
    anomaly = UrlHygieneDetector.analyze_pair("https://www.example.com/team", "https://example.com/team")
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.WWW_SUBDOMAIN
    assert anomaly.primary_url == "https://example.com/team"
    assert anomaly.duplicate_url == "https://www.example.com/team"


def test_h08_path_casing_variation():
    """H-08: /Products vs /products evaluates to PATH_CASING with lowercase as primary."""
    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/Products", "https://example.com/products")
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.PATH_CASING
    assert anomaly.primary_url == "https://example.com/products"
    assert anomaly.duplicate_url == "https://example.com/Products"


def test_h09_query_param_ordering():
    """H-09: ?b=2&a=1 vs ?a=1&b=2 evaluates to QUERY_PARAM_ORDER with sorted query as primary."""
    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/filter?b=2&a=1", "https://example.com/filter?a=1&b=2")
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.QUERY_PARAM_ORDER
    assert anomaly.primary_url == "https://example.com/filter?a=1&b=2"
    assert anomaly.duplicate_url == "https://example.com/filter?b=2&a=1"


def test_h10_marketing_tracking_params():
    """H-10: /article?utm_source=twitter vs /article evaluates to TRACKING_PARAMETERS."""
    anomaly = UrlHygieneDetector.analyze_pair("https://example.com/article?utm_source=twitter", "https://example.com/article")
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.TRACKING_PARAMETERS
    assert anomaly.primary_url == "https://example.com/article"
    assert anomaly.duplicate_url == "https://example.com/article?utm_source=twitter"


def test_h11_distinct_parameters_not_flagged_as_duplicate():
    """H-11: Content-defining query parameters (?cat=shoes vs ?cat=shirts) MUST NOT be grouped."""
    key_shoes = UrlHygieneDetector.get_hygiene_key("https://example.com/shop?cat=shoes")
    key_shirts = UrlHygieneDetector.get_hygiene_key("https://example.com/shop?cat=shirts")
    assert key_shoes != key_shirts

    # Site crawl detection must never pair them
    rec_shoes = make_record("https://example.com/shop?cat=shoes")
    rec_shirts = make_record("https://example.com/shop?cat=shirts")
    sc = SiteCrawlResult(crawl_records=[rec_shoes, rec_shirts])
    anomalies = UrlHygieneDetector.detect_site_hygiene(sc)
    assert len(anomalies) == 0


def test_h12_distinct_paths_not_flagged_as_duplicate():
    """H-12: Distinct paths (/page/1 vs /page/2) MUST NOT be grouped."""
    key1 = UrlHygieneDetector.get_hygiene_key("https://example.com/page/1")
    key2 = UrlHygieneDetector.get_hygiene_key("https://example.com/page/2")
    assert key1 != key2

    rec1 = make_record("https://example.com/page/1")
    rec2 = make_record("https://example.com/page/2")
    sc = SiteCrawlResult(crawl_records=[rec1, rec2])
    anomalies = UrlHygieneDetector.detect_site_hygiene(sc)
    assert len(anomalies) == 0


def test_h13_multiple_slashes():
    """H-13: Multiple slashes //services vs /services evaluates to MULTIPLE_SLASHES."""
    anomaly = UrlHygieneDetector.analyze_pair("https://example.com//services", "https://example.com/services")
    assert anomaly is not None
    assert anomaly.anomaly_type == HygieneAnomalyType.MULTIPLE_SLASHES
    assert anomaly.primary_url == "https://example.com/services"


def test_h14_record_lookup_prevents_param_collapse():
    """H-14 / Correction 1: ?id=1 and ?id=2 MUST NOT collapse to the same CrawlRecord in RecordLookupIndex."""
    rec_1 = make_record("https://example.com/item?id=1", status_code=200, raw_html="<html><body>Item 1</body></html>")
    rec_2 = make_record("https://example.com/item?id=2", status_code=200, raw_html="<html><body>Item 2</body></html>")

    index = RecordLookupIndex([rec_1, rec_2])

    looked_up_1 = index.lookup("https://example.com/item?id=1")
    looked_up_2 = index.lookup("https://example.com/item?id=2")

    assert looked_up_1 is not None
    assert looked_up_2 is not None
    assert looked_up_1.url == "https://example.com/item?id=1"
    assert looked_up_2.url == "https://example.com/item?id=2"
    assert looked_up_1 is not looked_up_2


# ===========================================================================
# 4. PIPELINE ORCHESTRATION & SERIALIZATION TESTS
# ===========================================================================

def test_p01_full_pipeline_orchestration():
    """P-01: UrlHygieneEngine.evaluate_site runs crawler -> redirect -> canonical -> hygiene."""
    rec_home = make_record("https://example.com", status_code=200, raw_html='<html><head><link rel="canonical" href="https://example.com"></head></html>')
    rec_redir = make_record("https://example.com/old", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/new")
    rec_new = make_record("https://example.com/new", status_code=200, raw_html='<html><head><link rel="canonical" href="https://example.com/new"></head><body>New Page Content</body></html>')
    rec_dup = make_record("https://example.com/new/", status_code=200, raw_html='<html><head><link rel="canonical" href="https://example.com/new"></head><body>New Page Content</body></html>')

    sc = SiteCrawlResult(
        pages_crawled=4,
        crawl_records=[rec_home, rec_redir, rec_new, rec_dup],
    )

    result = UrlHygieneEngine.evaluate_site(sc)

    # 1. Redirect chains populated
    assert "https://example.com/old" in result.redirect_chains
    assert result.redirect_chains["https://example.com/old"].status == RedirectChainStatus.RESOLVED

    # 2. Canonical chains populated
    assert "https://example.com/new" in result.canonical_chains
    assert result.canonical_chains["https://example.com/new"].status == CanonicalChainStatus.SELF_REFERENCING

    # 3. Hygiene anomalies populated
    assert len(result.hygiene_anomalies) >= 1
    anomaly_types = [a.anomaly_type for a in result.hygiene_anomalies]
    assert HygieneAnomalyType.TRAILING_SLASH in anomaly_types


def test_p02_site_crawl_result_serialization():
    """P-02: SiteCrawlResult JSON serialization roundtrip preserves all M6.3 models."""
    rec_redir = make_record("https://example.com/old", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/new")
    rec_new = make_record("https://example.com/new", status_code=200)

    sc = SiteCrawlResult(pages_crawled=2, crawl_records=[rec_redir, rec_new])
    UrlHygieneEngine.evaluate_site(sc)

    json_str = sc.model_dump_json()
    assert "redirect_chains" in json_str
    assert "canonical_chains" in json_str
    assert "hygiene_anomalies" in json_str

    deserialized = SiteCrawlResult.model_validate_json(json_str)
    assert len(deserialized.redirect_chains) == len(sc.redirect_chains)
    assert deserialized.redirect_chains["https://example.com/old"].final_url == "https://example.com/new"


def test_p03_markdown_reporter_rendering():
    """P-03: Markdown reporter renders redirect chains, canonical chains, and hygiene anomalies."""
    from rankintel.models.schema import SynthesisReport
    from rankintel.reporters.markdown import MarkdownReporter

    rec_a = make_record("https://example.com/old", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/mid")
    rec_b = make_record("https://example.com/mid", status_code=301, crawl_status=CrawlStatus.REDIRECTED, redirect_url="https://example.com/final")
    rec_c = make_record("https://example.com/final", status_code=200, raw_html='<html><head><link rel="canonical" href="https://example.com/final"></head></html>')

    sc = SiteCrawlResult(pages_crawled=3, crawl_records=[rec_a, rec_b, rec_c])
    UrlHygieneEngine.evaluate_site(sc)

    report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-10-02",
        site_crawl=sc,
    )

    md = MarkdownReporter.render(report)
    assert "Redirect Chains Tracked:" in md
    assert "Canonical Relationships:" in md


def test_fragment_only_links_do_not_produce_hygiene_anomalies():
    """In-page anchor fragments must not trigger false positive TRAILING_SLASH hygiene anomalies."""
    from rankintel.analyzers.hygiene_detector import UrlHygieneDetector

    # Test pair directly
    anomaly = UrlHygieneDetector.analyze_pair(
        "https://example.com/page#section1",
        "https://example.com/page"
    )
    assert anomaly is None

    # Test across crawl result
    rec1 = make_record("https://example.com/page", status_code=200, discovered_links=[
        "https://example.com/page#overview",
        "https://example.com/page#pricing",
    ])
    sc = SiteCrawlResult(pages_crawled=1, crawl_records=[rec1])
    anomalies = UrlHygieneDetector.detect_site_hygiene(sc)
    assert len(anomalies) == 0

