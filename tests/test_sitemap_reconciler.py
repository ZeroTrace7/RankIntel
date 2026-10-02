"""
Deterministic unit and integration tests for RankIntel Milestone M6.5:
Sitemap Reconciliation & Cross-Signal Conflict Triangulation Layer.
Offline execution — zero live HTTP requests.
"""
import pytest

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    CrawlabilityStatus,
    IndexabilityStatus,
    CanonicalizationSignal,
    SearchEligibilityRecord,
    CanonicalChainRecord,
    CanonicalChainStatus,
    NodeOrphanStatus,
    NodeCrawlState,
    ReachabilityInGraph,
    LinkGraphNode,
    InternalLinkGraphSummary,
    SitemapDocumentRecord,
    SitemapUrlRecord,
    SitemapFetchStatus,
    SitemapFormat,
    CrossSignalConflictType,
    CrossSignalConflictSeverity,
    EvidenceNature,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.analyzers.sitemap_reconciler import SitemapReconciler


# ---------------------------------------------------------------------------
# Helpers for synthetic record generation
# ---------------------------------------------------------------------------

def make_record(
    url: str,
    status_code: int = 200,
    crawl_status: CrawlStatus = CrawlStatus.FETCHED,
    raw_html: str = "",
    redirect_url: str = None,
    failure_reason: str = None,
    discovered_links: list = None,
) -> CrawlRecord:
    clean_url = url.strip()
    return CrawlRecord(
        url=clean_url,
        normalized_url=UrlNormalizer.normalize_for_crawl(clean_url),
        identity_url=UrlNormalizer.get_url_identity(clean_url),
        crawl_status=crawl_status,
        depth=1,
        status_code=status_code,
        raw_html=raw_html,
        redirect_url=redirect_url,
        failure_reason=failure_reason,
        discovered_links=discovered_links or [],
    )


def make_sitemap_url(loc: str, source: str = "https://example.com/sitemap.xml") -> SitemapUrlRecord:
    return SitemapUrlRecord(
        loc=loc,
        identity_url=UrlNormalizer.get_url_identity(loc),
        source_sitemap=source,
    )


# ===========================================================================
# 1. CROSS-SIGNAL CONFLICT TESTS (A THROUGH J)
# ===========================================================================

def test_conflict_a_sitemap_robots_blocked():
    """Conflict A: URL in sitemap is blocked by robots.txt."""
    rec = make_record(
        "https://example.com/secret",
        status_code=0,
        crawl_status=CrawlStatus.BLOCKED,
        failure_reason="Disallowed by robots.txt",
    )
    site_crawl = SiteCrawlResult(crawl_records=[rec])
    s_url = make_sitemap_url("https://example.com/secret")

    summary = SitemapReconciler.reconcile(
        site_crawl=site_crawl,
        sitemap_urls=[s_url],
    )

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_ROBOTS_BLOCKED), None)
    assert conflict is not None
    assert conflict.url == "https://example.com/secret"
    assert conflict.severity == CrossSignalConflictSeverity.HIGH
    assert conflict.evidence_nature == EvidenceNature.OBSERVED
    assert conflict.signal_a_state == "included_in_sitemap"
    assert conflict.signal_b_state == "BLOCKED"


def test_conflict_b_sitemap_noindex():
    """Conflict B: URL in sitemap specifies noindex directive."""
    raw_html = '<html><head><meta name="robots" content="noindex, follow"></head><body>Page</body></html>'
    rec = make_record("https://example.com/noindex-page", status_code=200, raw_html=raw_html)
    elig = SearchEligibilityRecord(
        url="https://example.com/noindex-page",
        crawlability=CrawlabilityStatus.ALLOWED,
        indexability=IndexabilityStatus.NOINDEX,
        canonicalization=CanonicalizationSignal.SELF_REFERENCING,
        http_status=200,
        meta_robots_directives=["noindex", "follow"],
    )
    site_crawl = SiteCrawlResult(
        crawl_records=[rec],
        search_eligibility={"https://example.com/noindex-page": elig},
    )
    s_url = make_sitemap_url("https://example.com/noindex-page")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_NOINDEX_CONFLICT), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.HIGH
    assert "noindex" in conflict.summary


def test_conflict_c_sitemap_redirect():
    """Conflict C: URL in sitemap returns HTTP 3xx redirect."""
    rec = make_record(
        "https://example.com/old",
        status_code=301,
        crawl_status=CrawlStatus.REDIRECTED,
        redirect_url="https://example.com/new",
    )
    site_crawl = SiteCrawlResult(crawl_records=[rec])
    s_url = make_sitemap_url("https://example.com/old")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_REDIRECT_CONFLICT), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.MEDIUM
    assert "HTTP 301" in conflict.signal_b_state


def test_conflict_d_sitemap_error():
    """Conflict D: URL in sitemap returns HTTP 4xx or 5xx."""
    rec = make_record("https://example.com/broken", status_code=404)
    site_crawl = SiteCrawlResult(crawl_records=[rec])
    s_url = make_sitemap_url("https://example.com/broken")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_ERROR_CONFLICT), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.HIGH
    assert "HTTP 404" in conflict.signal_b_state


def test_conflict_e_sitemap_canonical_elsewhere():
    """Conflict E: URL in sitemap canonicalizes elsewhere."""
    raw_html = '<html><head><link rel="canonical" href="https://example.com/master"></head></html>'
    rec = make_record("https://example.com/duplicate", status_code=200, raw_html=raw_html)
    elig = SearchEligibilityRecord(
        url="https://example.com/duplicate",
        crawlability=CrawlabilityStatus.ALLOWED,
        indexability=IndexabilityStatus.INDEXABLE,
        canonicalization=CanonicalizationSignal.CANONICALIZED_ELSEWHERE,
        canonical_target="https://example.com/master",
        http_status=200,
    )
    site_crawl = SiteCrawlResult(
        crawl_records=[rec],
        search_eligibility={"https://example.com/duplicate": elig},
    )
    s_url = make_sitemap_url("https://example.com/duplicate")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_CANONICAL_ELSEWHERE), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.MEDIUM
    assert "https://example.com/master" in conflict.summary


def test_conflict_f_canonical_target_redirect_reuses_m6_3():
    """Conflict F: Directly consumes M6.3 CanonicalChainRecord when canonical points to redirect."""
    chain = CanonicalChainRecord(
        source_url="https://example.com/page",
        declared_canonical="https://example.com/redirector",
        points_to_redirect=True,
        status=CanonicalChainStatus.POINTS_TO_REDIRECT,
    )
    site_crawl = SiteCrawlResult(canonical_chains={"https://example.com/page": chain})

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.CANONICAL_TARGET_REDIRECT), None)
    assert conflict is not None
    assert conflict.url == "https://example.com/page"
    assert conflict.severity == CrossSignalConflictSeverity.HIGH
    assert conflict.signal_b_source == "redirect_resolver"


def test_conflict_g_canonical_target_dead_reuses_m6_3():
    """Conflict G: Directly consumes M6.3 CanonicalChainRecord when canonical points to dead URL."""
    chain = CanonicalChainRecord(
        source_url="https://example.com/page",
        declared_canonical="https://example.com/dead",
        points_to_dead_url=True,
        status=CanonicalChainStatus.POINTS_TO_DEAD_URL,
    )
    site_crawl = SiteCrawlResult(canonical_chains={"https://example.com/page": chain})

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.CANONICAL_TARGET_DEAD), None)
    assert conflict is not None
    assert conflict.url == "https://example.com/page"
    assert conflict.severity == CrossSignalConflictSeverity.HIGH
    assert "returns 4xx/5xx" in conflict.summary


def test_conflict_h_sitemap_orphan_candidate_reuses_m6_4():
    """Conflict H: Directly consumes M6.4 link_graph node when crawled sitemap URL has 0 inbound links."""
    rec = make_record("https://example.com/orphan", status_code=200)
    node = LinkGraphNode(
        url="https://example.com/orphan",
        identity_url=UrlNormalizer.get_url_identity("https://example.com/orphan"),
        crawl_state=NodeCrawlState.CRAWLED,
        orphan_status=NodeOrphanStatus.POTENTIAL_ORPHAN,
        inbound_internal_count=0,
        outbound_internal_count=1,
    )
    lg = InternalLinkGraphSummary(
        root_url="https://example.com",
        nodes={"https://example.com/orphan": node},
    )
    site_crawl = SiteCrawlResult(crawl_records=[rec], link_graph=lg)
    s_url = make_sitemap_url("https://example.com/orphan")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_ORPHAN_CANDIDATE), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.LOW
    assert "zero_observed_inbound_internal_links" in conflict.signal_b_state


def test_conflict_i_sitemap_url_uncrawled():
    """Conflict I: Sitemap URL was not crawled; evidence remains UNAVAILABLE."""
    site_crawl = SiteCrawlResult(crawl_records=[])
    s_url = make_sitemap_url("https://example.com/uncrawled-product")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.SITEMAP_URL_UNCRAWLED), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.INFO
    assert conflict.evidence_nature == EvidenceNature.UNAVAILABLE
    assert "https://example.com/uncrawled-product" in summary.uncrawled_sitemap_urls


def test_conflict_j_internal_url_not_in_sitemap_coverage_discrepancy():
    """Conflict J: Crawled indexable self-canonical 200 URL is omitted from sitemap."""
    rec = make_record("https://example.com/services/calibration", status_code=200)
    elig = SearchEligibilityRecord(
        url="https://example.com/services/calibration",
        crawlability=CrawlabilityStatus.ALLOWED,
        indexability=IndexabilityStatus.INDEXABLE,
        canonicalization=CanonicalizationSignal.SELF_REFERENCING,
        http_status=200,
    )
    site_crawl = SiteCrawlResult(
        crawl_records=[rec],
        search_eligibility={"https://example.com/services/calibration": elig},
    )
    # Sitemap only contains homepage
    s_url = make_sitemap_url("https://example.com/")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    conflict = next((c for c in summary.conflicts if c.conflict_type == CrossSignalConflictType.INTERNAL_URL_NOT_IN_SITEMAP), None)
    assert conflict is not None
    assert conflict.severity == CrossSignalConflictSeverity.LOW
    assert "coverage discrepancy" in conflict.summary.lower()
    assert "https://example.com/services/calibration" in summary.internal_urls_missing_from_sitemap


# ===========================================================================
# 2. IN_SITEMAP FLAG & SUMMARY INTEGRATION
# ===========================================================================

def test_reconciliation_updates_search_eligibility_in_sitemap_flag():
    """Verifies that SearchEligibilityRecord.in_sitemap gets toggled to True for sitemap URLs."""
    rec = make_record("https://example.com/about", status_code=200)
    elig = SearchEligibilityRecord(
        url="https://example.com/about",
        in_sitemap=False,
        http_status=200,
    )
    site_crawl = SiteCrawlResult(
        crawl_records=[rec],
        search_eligibility={"https://example.com/about": elig},
    )
    s_url = make_sitemap_url("https://example.com/about")

    summary = SitemapReconciler.reconcile(site_crawl, sitemap_urls=[s_url])

    assert elig.in_sitemap is True
    assert summary.crawled_sitemap_urls_count == 1
    assert summary.total_unique_sitemap_urls == 1
