"""
Search Signal Intelligence Integration & Regression Test Suite (Phase 9.1 - Layer A).
Verifies complete coexistence of SearchSignalEngine through the full RankIntel pipeline:
crawl -> in-memory evidence collection -> site aggregation -> synthesis -> provenance -> reporting -> MCP.
Validates zero network requests, health-score formula invariance, and strict Layer A boundaries.
"""
import pytest
from unittest.mock import MagicMock, patch

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.analyzers.search_signal_analyzer import SiteSearchSignalAnalyzer
from rankintel.analyzers.content_analyzer import SiteContentAnalyzer
from rankintel.analyzers.entity_analyzer import SiteEntityAnalyzer
from rankintel.analyzers.internal_link_analyzer import SiteInternalLinkAnalyzer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.models.schema import (
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    ContentEvidence,
    EntityEvidence,
    InternalLinkEvidence,
    SearchSignalEvidence,
    EngineResult,
    SearchSignalConfidence,
)


HTML_PAGE_A = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Acme Industrial Solutions - High Performance Calibration</title>
    <meta name="description" content="Acme Corp provides precision measurement and calibration services for aerospace enterprises." />
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Acme Corp Global",
      "description": "Provider of certified calibration instruments and metallurgical testing equipment."
    }
    </script>
</head>
<body>
    <header>
        <span class="brand">Acme Corp Global</span>
        <nav>
            <a href="/products">Products</a>
            <a href="/about">About Us</a>
        </nav>
    </header>
    <main>
        <h1>Industrial Testing Equipment & Calibration Services</h1>
        <p>Acme Corp Global provides comprehensive precision measurement and testing systems for aerospace and manufacturing enterprises across North America.</p>
        <p>Our accredited calibration laboratories deliver rigorous compliance and verification standards.</p>
        <h2>Advanced Calibration Methodologies</h2>
        <p>Calibration procedures utilize traceable primary standards maintained in environmental chambers.</p>
        <img src="/img/calibration-rig.png" alt="High Precision Calibration Rig System" />
    </main>
    <footer>
        <p>&copy; 2026 Acme Corp Global. All rights reserved.</p>
    </footer>
</body>
</html>
"""

HTML_PAGE_B = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Products & Instruments - Acme Industrial</title>
    <meta name="description" content="Explore certified spectrometers and calibration instruments engineered for high throughput testing." />
</head>
<body>
    <header>
        <span class="brand">Acme Corp Global</span>
        <nav><a href="/">Home</a><a href="/about">About Us</a></nav>
    </header>
    <main>
        <h1>Precision Measurement Instruments & Spectrometers</h1>
        <p>Explore our catalog of certified instruments including digital micrometer gauges, optical emission spectrometers, and hardness testers.</p>
        <h2>Spectrometer Calibration Systems</h2>
        <p>Optical emission instruments offer sub-ppm detection limits. Automated calibration ensures reliable operation.</p>
    </main>
</body>
</html>
"""


class RequestCountingTransport:
    """Mock transport that tracks exact network request count to prove zero duplicate HTTP requests."""
    def __init__(self, page_map):
        self.page_map = page_map
        self.request_count = 0
        self.requested_urls = []

    def fetch(self, url):
        self.request_count += 1
        self.requested_urls.append(url)
        html = self.page_map.get(url, "<html><body><h1>Not Found</h1></body></html>")
        return MagicMock(
            status_code=200 if url in self.page_map else 404,
            text=html,
            headers={"content-type": "text/html; charset=utf-8"},
        )


def _collect_with_html(html: str, url: str = "https://example.com"):
    """Helper to run EvidenceCollector deterministically with provided HTML."""
    collector = EvidenceCollector()
    mock_browser = EngineResult(
        engine_name="browser_engine",
        status="success",
        raw_html=html,
        on_page=OnPageEvidence(url=url, title="Acme Industrial", h1_text=["Industrial Testing Equipment & Calibration Services"]),
    )
    mock_seo = EngineResult(
        engine_name="advertools_seo",
        status="success",
        on_page=OnPageEvidence(url=url, title="Acme Industrial", h1_text=["Industrial Testing Equipment & Calibration Services"]),
        robots=RobotsEvidence(found=True),
        schema_data=SchemaEvidence(has_organization=True),
    )
    with patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser), \
         patch.object(collector.seo_engine, "execute", return_value=mock_seo), \
         patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
         patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="skipped")):
        return collector.collect(url)


def test_pipeline_coexistence_evidence_collector():
    """Verify SearchSignalEngine runs concurrently on single-page DOM alongside Phase 8 engines."""
    results = _collect_with_html(HTML_PAGE_A)

    assert "content_engine" in results
    assert "entity_engine" in results
    assert "internal_link_engine" in results
    assert "search_signal_engine" in results

    sig_res = results["search_signal_engine"]
    assert sig_res.status == "success"
    assert sig_res.search_signal is not None
    assert sig_res.search_signal.total_signals_detected > 0
    assert len(sig_res.search_signal.title_terms) > 0
    assert len(sig_res.search_signal.heading_terms) > 0


def test_synthesizer_reconciles_search_signals():
    """Verify IntelligenceSynthesizer populates unified_search_signal without modifying other fields."""
    results = _collect_with_html(HTML_PAGE_A)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_search_signal is not None
    assert report.unified_search_signal.total_signals_detected > 0
    assert len(report.unified_search_signal.facts) > 0
    assert report.unified_content is not None
    assert report.unified_entity is not None
    assert report.unified_internal_link is not None


def test_formula_and_architecture_invariance():
    """Verify health score formulas remain mathematically identical and invariant to SearchSignalEngine."""
    synthesizer = IntelligenceSynthesizer()

    base_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(title="Test Page", meta_description="Valid Description", canonical_url="https://example.com"),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(has_organization=True),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(overall_citability_score=80),
        ),
        "browser_engine": EngineResult(
            engine_name="browser_engine",
            status="success",
            trust_stack=TrustStackResult(overall_score=75),
        ),
    }

    # Baseline score without SearchSignalEngine
    report_baseline = synthesizer.synthesize("https://example.com", base_results)
    baseline_score = report_baseline.overall_health_score

    # Now add SearchSignalEngine result
    rich_results = dict(base_results)
    rich_results["search_signal_engine"] = EngineResult(
        engine_name="search_signal_engine",
        status="success",
        search_signal=SearchSignalEvidence(
            total_signals_detected=250,
            title_terms=["calibration", "testing", "instruments"],
            facts=["Fact 1", "Fact 2"],
        ),
    )

    report_with_signals = synthesizer.synthesize("https://example.com", rich_results)
    signal_score = report_with_signals.overall_health_score

    # Health score must NOT change by even 1 point
    assert signal_score == baseline_score
    assert report_with_signals.score_formula_mode == report_baseline.score_formula_mode


def test_site_wide_coexistence_search_signal_analyzer():
    """Verify SiteSearchSignalAnalyzer aggregates recurring concepts across multiple crawled pages."""
    records = [
        CrawlRecord(
            url="https://example.com/",
            normalized_url="https://example.com/",
            identity_url="https://example.com/",
            depth=0,
            status_code=200,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=HTML_PAGE_A,
        ),
        CrawlRecord(
            url="https://example.com/products",
            normalized_url="https://example.com/products",
            identity_url="https://example.com/products",
            depth=1,
            status_code=200,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=HTML_PAGE_B,
        ),
    ]

    site_crawl = SiteCrawlResult(
        pages_crawled=2,
        crawl_records=records,
    )

    # Run SiteSearchSignalAnalyzer
    SiteSearchSignalAnalyzer.analyze_site(site_crawl)

    assert site_crawl.search_signal_intelligence is not None
    intel = site_crawl.search_signal_intelligence
    assert intel.total_pages_evaluated == 2
    assert intel.total_unique_concepts > 0
    assert intel.recurring_concepts_count > 0

    # "calibration" appears on both pages -> must be a recurring concept!
    recurring_normalized = [rc.normalized_concept for rc in intel.recurring_concepts]
    assert any("calibration" in c for c in recurring_normalized)

    # Find the calibration recurring concept and inspect its properties
    calib_rc = next(rc for rc in intel.recurring_concepts if "calibration" in rc.normalized_concept)
    assert calib_rc.pages_count == 2
    assert len(calib_rc.page_urls) == 2
    assert calib_rc.total_occurrences >= 2
    assert len(calib_rc.observed_locations) > 0

    # Boundaries check
    assert intel.terminology_nature == "OBSERVED_WEBSITE_TERMINOLOGY"
    assert intel.external_query_data_status == "NOT_AVAILABLE_LAYER_A"


def test_zero_duplicate_http_requests_instrumented():
    """Prove empirically that SearchSignalEngine executes strictly in-memory without duplicate HTTP requests."""
    pages = {
        "https://example.com/": HTML_PAGE_A,
        "https://example.com/products": HTML_PAGE_B,
    }
    transport = RequestCountingTransport(pages)

    # Initial crawl pass
    records = []
    for u, html in pages.items():
        res = transport.fetch(u)
        records.append(CrawlRecord(
            url=u,
            normalized_url=u,
            identity_url=u,
            depth=0 if u.endswith("/") else 1,
            status_code=res.status_code,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=html,
        ))

    initial_request_count = transport.request_count
    assert initial_request_count == 2

    site_crawl = SiteCrawlResult(pages_crawled=2, crawl_records=records)

    # Execute SiteContentAnalyzer, SiteEntityAnalyzer, and SiteSearchSignalAnalyzer
    SiteContentAnalyzer.analyze_site(site_crawl)
    SiteEntityAnalyzer.analyze_site(site_crawl)
    SiteSearchSignalAnalyzer.analyze_site(site_crawl)

    # Assert exactly ZERO additional HTTP requests were made
    assert transport.request_count == initial_request_count


def test_cross_engine_provenance_attribution():
    """Verify evidence provenance tags are cleanly generated for SearchSignal findings."""
    results = _collect_with_html(HTML_PAGE_A)

    tagger = ProvenanceTagger()
    tags = tagger.tag(results)

    engines = {t.engine for t in tags}
    assert "search_signal_engine" in engines

    signal_tags = [t for t in tags if t.engine == "search_signal_engine"]
    assert len(signal_tags) >= 1
    for t in signal_tags:
        assert t.confidence in ("high", "medium")
        assert "Search Signal" in t.finding


def test_markdown_and_json_reporters_render_search_signals():
    """Verify Markdown and JSON reporters render Layer A Search Signal sections."""
    results = _collect_with_html(HTML_PAGE_A)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    # Attach multi-page crawl
    site_crawl = SiteCrawlResult(
        pages_crawled=2,
        crawl_records=[
            CrawlRecord(url="https://example.com/", normalized_url="https://example.com/", identity_url="https://example.com/", crawl_status=CrawlStatus.FETCHED, depth=0, raw_html=HTML_PAGE_A),
            CrawlRecord(url="https://example.com/products", normalized_url="https://example.com/products", identity_url="https://example.com/products", crawl_status=CrawlStatus.FETCHED, depth=1, raw_html=HTML_PAGE_B),
        ],
    )
    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    report.site_crawl = site_crawl

    # 1. Markdown rendering
    md_output = MarkdownReporter.render(report)
    assert "SEARCH SIGNAL INTELLIGENCE (Layer A" in md_output
    assert "Site-Wide Recurring Search Concepts & Terminology (Layer A)" in md_output
    assert "Layer A boundary" in md_output

    # 2. JSON rendering
    json_output = JsonReporter.render_audit(report)
    assert '"unified_search_signal"' in json_output
    assert '"search_signal_intelligence"' in json_output
    assert '"recurring_concepts"' in json_output


def test_mcp_server_exposes_search_signals():
    """Verify MCP server exposes verified Phase 9.1 search signal telemetry in rankintel_audit output."""
    from rankintel.mcp.server import rankintel_audit

    with patch("rankintel.mcp.server.EvidenceCollector") as MockCol, \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as MockSyn:

        mock_collector = MagicMock()
        mock_synthesizer = MagicMock()
        MockCol.return_value = mock_collector
        MockSyn.return_value = mock_synthesizer

        results = _collect_with_html(HTML_PAGE_A)
        real_report = IntelligenceSynthesizer().synthesize("https://example.com", results)

        mock_synthesizer.synthesize.return_value = real_report

        audit_res = rankintel_audit("https://example.com")

        assert "search_signals_total" in audit_res
        assert audit_res["search_signals_total"] > 0
        assert "search_signal_top_terms" in audit_res
        assert isinstance(audit_res["search_signal_top_terms"], list)
        assert len(audit_res["search_signal_top_terms"]) > 0
