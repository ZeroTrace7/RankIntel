"""
Phase 9 Integration & Regression Test Suite (M9.6).
Verifies complete end-to-end integration of Phase 9 Search Intelligence:
- M9.1 Search Signal Intelligence
- M9.2 Keyword & Topic Intelligence
- M9.3 Query–Page Mapping
- M9.4 Search Intent & Topic Coverage
- M9.5 Cannibalization & Search Gaps

Validates:
1. End-to-end single-page and multi-page pipeline execution.
2. Correct dependency data flow ordering (M9.1 -> M9.2 -> M9.3 -> M9.4 -> M9.5).
3. Provenance retention through ProvenanceTagger.
4. Partial crawl boundary and disclaimer preservation.
5. Strict FACT vs ANALYSIS vs RECOMMENDATION separation.
6. Layer A terminology and zero external search assumptions.
7. Health-score formula invariance across 3_engine, 4_engine, and 5_engine modes.
8. Zero duplicate HTTP requests (100% in-memory DOM reuse).
9. Full serialization and reporting parity across Markdown, JSON, CLI, and FastMCP.
"""
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.cli import main
from rankintel.mcp.server import rankintel_audit

from rankintel.engines.search_signal_engine import SearchSignalEngine
from rankintel.engines.topic_intelligence_engine import TopicIntelligenceEngine
from rankintel.engines.query_page_mapping_engine import QueryPageMappingEngine
from rankintel.engines.search_intent_engine import SearchIntentEngine
from rankintel.analyzers.search_signal_analyzer import SiteSearchSignalAnalyzer
from rankintel.analyzers.topic_analyzer import SiteTopicAnalyzer
from rankintel.analyzers.query_page_analyzer import SiteQueryPageAnalyzer
from rankintel.analyzers.topic_coverage_analyzer import SiteTopicCoverageAnalyzer
from rankintel.analyzers.cannibalization_analyzer import CannibalizationAnalyzer
from rankintel.analyzers.search_gap_analyzer import SearchGapAnalyzer

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
    CloudIntelligenceEvidence,
    EngineResult,
    SearchSignalConfidence,
    SearchIntentCategory,
    CannibalizationSignalType,
    TopicGapType,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    PageIntentEvidence,
    IntentEvidenceItem,
    SiteTopicCoverageIntelligence,
    PageCannibalizationEvidence,
    PotentialCannibalizationItem,
    ObservableTopicGapItem,
)


PAGE_A_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Precision Calibration Services - Industrial Measurement Lab</title>
    <meta name="description" content="ISO 17025 accredited precision calibration services for torque, pressure, and temperature gauges.">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Precision Calibration Lab",
      "url": "https://calibration-example.com"
    }
    </script>
</head>
<body>
    <header><nav><a href="/">Home</a><a href="/services">Services</a></nav></header>
    <main>
        <h1>Precision Calibration Services</h1>
        <p>Our accredited laboratory delivers certified precision calibration services for aerospace and automotive instrumentation.</p>
        <h2>Pressure Gauge Calibration</h2>
        <p>Comprehensive calibration of digital and analog pressure transducers and deadweight testers.</p>
        <h2>Temperature Sensor Calibration</h2>
        <p>High accuracy thermal calibration from cryogenic levels up to 1200 degrees Celsius.</p>
        <div class="pricing">
            <h3>Calibration Pricing</h3>
            <p>Request a customized quotation for standard and expedited turnaround times.</p>
            <a href="/quote" class="cta-button">Request Quote</a>
        </div>
    </main>
</body>
</html>
"""

PAGE_B_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Pressure Calibration Services - Precision Calibration Lab</title>
    <meta name="description" content="Dedicated pressure calibration and gauge inspection services with traceable ISO certification.">
</head>
<body>
    <header><nav><a href="/">Home</a><a href="/quote">Request Quote</a></nav></header>
    <main>
        <h1>Pressure Calibration Services</h1>
        <p>Specialized pressure calibration protocols meeting strict industrial compliance standards.</p>
        <h2>Pressure Gauge Calibration</h2>
        <p>Laboratory calibration of differential, absolute, and hydrostatic pressure sensors.</p>
        <form action="/submit-quote" method="post">
            <input type="text" name="equipment" placeholder="Enter gauge model">
            <button type="submit">Submit for Quote</button>
        </form>
    </main>
</body>
</html>
"""


def _build_test_crawl_records():
    u1 = "https://calibration-example.com/"
    u2 = "https://calibration-example.com/pressure-calibration"
    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html=PAGE_A_HTML,
        title="Precision Calibration Services - Industrial Measurement Lab",
        h1_tags=["Precision Calibration Services"],
        h2_tags=["Pressure Gauge Calibration", "Temperature Sensor Calibration"],
        word_count=120,
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=PAGE_B_HTML,
        title="Pressure Calibration Services - Precision Calibration Lab",
        h1_tags=["Pressure Calibration Services"],
        h2_tags=["Pressure Gauge Calibration"],
        word_count=85,
    )
    return [rec1, rec2]


# ---------------------------------------------------------------------------
# 1. Single-Page End-to-End Pipeline & Integration
# ---------------------------------------------------------------------------
def test_single_page_phase9_pipeline():
    """Verify single-page collection executes M9.1 through M9.5 in order and reconciles in synthesizer."""
    collector = EvidenceCollector()

    with patch.object(collector.browser_engine, "execute_sync") as mock_browser, \
         patch.object(collector.seo_engine, "audit_static_page") as mock_seo:

        mock_browser.return_value = EngineResult(
            engine_name="crawl4ai_browser",
            status="success",
            raw_html=PAGE_A_HTML,
            on_page=OnPageEvidence(
                url="https://calibration-example.com/",
                status_code=200,
                title="Precision Calibration Services - Industrial Measurement Lab",
                title_length=58,
                meta_description="ISO 17025 accredited precision calibration services for torque, pressure, and temperature gauges.",
                meta_desc_length=95,
                h1_text=["Precision Calibration Services"],
                h1_count=1,
            ),
        )
        mock_seo.return_value = (
            OnPageEvidence(url="https://calibration-example.com/", status_code=200),
            SchemaEvidence(),
        )

        results = collector.collect("https://calibration-example.com/")

        # Verify all 5 Phase 9 engines were executed
        assert "search_signal_engine" in results
        assert "topic_intelligence_engine" in results
        assert "query_page_mapping_engine" in results
        assert "search_intent_engine" in results
        assert "cannibalization_analyzer" in results

        assert results["search_signal_engine"].status == "success"
        assert results["topic_intelligence_engine"].status == "success"
        assert results["query_page_mapping_engine"].status == "success"
        assert results["search_intent_engine"].status == "success"
        assert results["cannibalization_analyzer"].status == "success"

        # Verify Synthesis reconciliation
        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize("https://calibration-example.com/", results)

        assert report.unified_search_signal is not None
        assert report.unified_search_signal.total_signals_detected > 0
        assert report.unified_topic is not None
        assert report.unified_topic.total_topics_derived > 0
        assert report.unified_query_page is not None
        assert report.unified_query_page.total_concepts_mapped > 0
        assert report.unified_search_intent is not None
        assert report.unified_search_intent.primary_observed_intent_signal != SearchIntentCategory.UNSPECIFIED
        assert report.unified_cannibalization is not None


# ---------------------------------------------------------------------------
# 2. Multi-Page Crawl Pipeline & Dependency Ordering
# ---------------------------------------------------------------------------
def test_multi_page_phase9_pipeline_data_flow():
    """Verify complete M9.1 -> M9.2 -> M9.3 -> M9.4 -> M9.5 data flow through multi-page crawl."""
    records = _build_test_crawl_records()
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=2,
        crawl_records=records,
    )

    # 1. M9.1 Search Signal Intelligence
    sig_intel = SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    assert site_crawl.search_signal_intelligence is not None
    assert sig_intel.recurring_concepts_count > 0
    assert len(sig_intel.page_signal_evidence) == 2

    # 2. M9.2 Topic Intelligence (Consumes M9.1 page_signal_evidence)
    top_intel = SiteTopicAnalyzer.analyze_site(site_crawl)
    assert site_crawl.topic_intelligence is not None
    assert top_intel.total_topics_count > 0
    assert len(top_intel.page_topic_intelligence) == 2

    # 3. M9.3 Query-Page Mapping (Consumes M9.1 signals + M9.2 topics)
    qp_intel = SiteQueryPageAnalyzer.analyze_site(site_crawl)
    assert site_crawl.query_page_intelligence is not None
    assert qp_intel.total_concepts_mapped > 0
    assert len(qp_intel.page_query_evidence) == 2

    # 4. M9.4 Search Intent & Topic Coverage (Consumes M9.1 signals, M9.2 topics, M9.3 queries)
    cov_intel = SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
    assert site_crawl.topic_coverage_intelligence is not None
    assert cov_intel.total_topics_covered > 0
    assert len(cov_intel.page_intent_evidence) == 2

    # 5. M9.5 Cannibalization & Search Gaps (Consumes M9.3 query relationships + M9.4 intent evidence)
    cann_intel = CannibalizationAnalyzer.analyze_site(site_crawl)
    gap_intel = SearchGapAnalyzer.analyze_site(site_crawl)
    assert site_crawl.cannibalization_intelligence is not None
    assert cann_intel.competing_topics_count >= 0
    assert gap_intel.total_gaps_identified >= 0


# ---------------------------------------------------------------------------
# 3. Provenance Chain Preservation
# ---------------------------------------------------------------------------
def test_provenance_preserves_all_phase9_engines():
    """Verify EvidenceProvenanceTag records are created for all 5 Phase 9 engines."""
    records = _build_test_crawl_records()
    sig_ev = SearchSignalEngine.evaluate(raw_html=PAGE_A_HTML, url=records[0].url)
    top_ev = TopicIntelligenceEngine.evaluate(search_signal_ev=sig_ev, url=records[0].url)
    qp_ev = QueryPageMappingEngine.evaluate(url=records[0].url, search_signal_ev=sig_ev, topic_intel_ev=top_ev)
    intent_ev = SearchIntentEngine.evaluate(url=records[0].url, raw_html=PAGE_A_HTML, search_signal_ev=sig_ev, topic_intel_ev=top_ev, query_page_ev=qp_ev)
    cann_ev = CannibalizationAnalyzer.evaluate_page(url=records[0].url, query_page_ev=qp_ev, intent_ev=intent_ev)

    engine_results = {
        "search_signal_engine": EngineResult(engine_name="search_signal_engine", status="success", search_signal=sig_ev),
        "topic_intelligence_engine": EngineResult(engine_name="topic_intelligence_engine", status="success", topic_intelligence=top_ev),
        "query_page_mapping_engine": EngineResult(engine_name="query_page_mapping_engine", status="success", query_page=qp_ev),
        "search_intent_engine": EngineResult(engine_name="search_intent_engine", status="success", search_intent=intent_ev),
        "cannibalization_analyzer": EngineResult(engine_name="cannibalization_analyzer", status="success", cannibalization=cann_ev),
    }

    tags = ProvenanceTagger.tag(engine_results)
    engines_in_tags = {t.engine for t in tags}

    assert "search_signal_engine" in engines_in_tags
    assert "topic_intelligence_engine" in engines_in_tags
    assert "query_page_mapping_engine" in engines_in_tags
    assert "search_intent_engine" in engines_in_tags
    assert "cannibalization_analyzer" in engines_in_tags


# ---------------------------------------------------------------------------
# 4. Partial Crawl Disclaimers & Boundary Preservation
# ---------------------------------------------------------------------------
def test_partial_crawl_disclaimers_preserved():
    """Verify partial crawl statuses generate explicit disclaimers without false gap claims."""
    records = _build_test_crawl_records()[:1]
    site_crawl = SiteCrawlResult(
        completeness_status="BUDGET_EXHAUSTED",
        pages_crawled=1,
        remaining_frontier=15,
        pages_skipped=3,
        crawl_records=records,
    )

    SiteTopicAnalyzer.analyze_site(site_crawl)
    SiteQueryPageAnalyzer.analyze_site(site_crawl)
    SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
    SearchGapAnalyzer.analyze_site(site_crawl)

    assert site_crawl.topic_intelligence.is_partial_crawl is True
    assert "absence of a topic in partial crawls does not indicate lack of coverage" in site_crawl.topic_intelligence.completeness_disclaimer

    assert site_crawl.query_page_intelligence.is_partial_crawl is True
    assert "absence of a page/concept mapping in partial crawls does not indicate lack of coverage" in site_crawl.query_page_intelligence.completeness_disclaimer

    assert site_crawl.topic_coverage_intelligence.is_partial_crawl is True
    assert "absence of coverage for any topic or intent in partial crawls does not indicate lack of content" in site_crawl.topic_coverage_intelligence.completeness_disclaimer

    assert site_crawl.cannibalization_intelligence.is_partial_crawl is True
    assert "partial crawls" in site_crawl.cannibalization_intelligence.completeness_disclaimer


# ---------------------------------------------------------------------------
# 5. Separation of FACT, ANALYSIS, and RECOMMENDATION
# ---------------------------------------------------------------------------
def test_fact_analysis_recommendation_separation():
    """Verify FACT, ANALYSIS, and RECOMMENDATION statements are strictly separated with Layer A tags."""
    records = _build_test_crawl_records()
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=2,
        crawl_records=records,
    )

    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)
    SiteQueryPageAnalyzer.analyze_site(site_crawl)
    SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
    CannibalizationAnalyzer.analyze_site(site_crawl)
    SearchGapAnalyzer.analyze_site(site_crawl)

    cann = site_crawl.cannibalization_intelligence

    # Facts, analyses, recommendations must be distinct lists
    assert isinstance(cann.facts, list)
    assert isinstance(cann.analyses, list)
    assert isinstance(cann.recommendations, list)

    for rec in cann.recommendations:
        assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in rec

    for signal in cann.potential_cannibalization_signals:
        assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in signal.recommendation

    for gap in cann.observable_topic_gaps:
        assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in gap.recommendation


# ---------------------------------------------------------------------------
# 6. Formula Invariance (3_engine, 4_engine, 5_engine)
# ---------------------------------------------------------------------------
def test_formula_invariance_across_all_modes():
    """Verify Phase 9 evidence produces exactly 0 point change across 3_engine, 4_engine, and 5_engine formulas."""
    synthesizer = IntelligenceSynthesizer()
    url = "https://calibration-example.com/"

    base_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url=url,
                title="Precision Calibration Services",
                title_length=30,
                meta_description="Accredited calibration services.",
                meta_desc_length=32,
                h1_count=1,
            ),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["Organization"]),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(overall_citability_score=80, answer_first_ratio=0.5),
        ),
        "crawl4ai_browser": EngineResult(
            engine_name="crawl4ai_browser",
            status="success",
            trust_stack=TrustStackResult(overall_trust_score=75),
        ),
    }

    # 1. 3_engine mode baseline
    rep_3_base = synthesizer.synthesize(url, base_results)
    assert rep_3_base.score_formula_mode == "3_engine"
    score_3_base = rep_3_base.overall_health_score

    # Add all Phase 9 results
    records = _build_test_crawl_records()
    sig_ev = SearchSignalEngine.evaluate(raw_html=PAGE_A_HTML, url=url)
    top_ev = TopicIntelligenceEngine.evaluate(search_signal_ev=sig_ev, url=url)
    qp_ev = QueryPageMappingEngine.evaluate(url=url, search_signal_ev=sig_ev, topic_intel_ev=top_ev)
    intent_ev = SearchIntentEngine.evaluate(url=url, raw_html=PAGE_A_HTML, search_signal_ev=sig_ev, topic_intel_ev=top_ev, query_page_ev=qp_ev)
    cann_ev = CannibalizationAnalyzer.evaluate_page(url=url, query_page_ev=qp_ev, intent_ev=intent_ev)

    results_p9 = dict(base_results)
    results_p9["search_signal_engine"] = EngineResult(engine_name="search_signal_engine", status="success", search_signal=sig_ev)
    results_p9["topic_intelligence_engine"] = EngineResult(engine_name="topic_intelligence_engine", status="success", topic_intelligence=top_ev)
    results_p9["query_page_mapping_engine"] = EngineResult(engine_name="query_page_mapping_engine", status="success", query_page=qp_ev)
    results_p9["search_intent_engine"] = EngineResult(engine_name="search_intent_engine", status="success", search_intent=intent_ev)
    results_p9["cannibalization_analyzer"] = EngineResult(engine_name="cannibalization_analyzer", status="success", cannibalization=cann_ev)

    rep_3_p9 = synthesizer.synthesize(url, results_p9)
    assert rep_3_p9.score_formula_mode == "3_engine"
    assert rep_3_p9.overall_health_score == score_3_base

    # 2. 4_engine mode baseline (adds performance)
    results_4_base = dict(base_results)
    results_4_base["performance_engine"] = EngineResult(
        engine_name="performance_engine",
        status="success",
        performance=PerformanceEvidence(performance_score=90, ttfb_ms=250),
    )
    rep_4_base = synthesizer.synthesize(url, results_4_base)
    assert rep_4_base.score_formula_mode == "4_engine"
    score_4_base = rep_4_base.overall_health_score

    results_4_p9 = dict(results_p9)
    results_4_p9["performance_engine"] = results_4_base["performance_engine"]
    rep_4_p9 = synthesizer.synthesize(url, results_4_p9)
    assert rep_4_p9.score_formula_mode == "4_engine"
    assert rep_4_p9.overall_health_score == score_4_base

    # 3. 5_engine mode baseline (adds cloud keyword intelligence)
    from rankintel.models.schema import KeywordIntelligence
    results_5_base = dict(results_4_base)
    results_5_base["mcp_cloud"] = EngineResult(
        engine_name="mcp_cloud",
        status="success",
        cloud_intelligence=CloudIntelligenceEvidence(
            available=True,
            keywords=KeywordIntelligence(total_keywords=150, estimated_monthly_traffic=1200),
        ),
    )
    rep_5_base = synthesizer.synthesize(url, results_5_base)
    assert rep_5_base.score_formula_mode == "5_engine"
    score_5_base = rep_5_base.overall_health_score

    results_5_p9 = dict(results_4_p9)
    results_5_p9["mcp_cloud"] = results_5_base["mcp_cloud"]
    rep_5_p9 = synthesizer.synthesize(url, results_5_p9)
    assert rep_5_p9.score_formula_mode == "5_engine"
    assert rep_5_p9.overall_health_score == score_5_base


# ---------------------------------------------------------------------------
# 7. Zero Duplicate HTTP Requests
# ---------------------------------------------------------------------------
def test_zero_duplicate_http_requests():
    """Verify Phase 9 engines and analyzers perform zero HTTP requests, reusing in-memory evidence."""
    records = _build_test_crawl_records()
    site_crawl = SiteCrawlResult(pages_crawled=2, crawl_records=records)

    with patch("urllib.request.urlopen") as mock_url, \
         patch("requests.get") as mock_req, \
         patch("httpx.AsyncClient.get") as mock_httpx:

        # Single-page executions
        sig_ev = SearchSignalEngine.evaluate(raw_html=PAGE_A_HTML, url=records[0].url)
        top_ev = TopicIntelligenceEngine.evaluate(search_signal_ev=sig_ev, url=records[0].url)
        qp_ev = QueryPageMappingEngine.evaluate(url=records[0].url, search_signal_ev=sig_ev, topic_intel_ev=top_ev)
        intent_ev = SearchIntentEngine.evaluate(url=records[0].url, raw_html=PAGE_A_HTML, search_signal_ev=sig_ev, topic_intel_ev=top_ev, query_page_ev=qp_ev)
        cann_ev = CannibalizationAnalyzer.evaluate_page(url=records[0].url, query_page_ev=qp_ev, intent_ev=intent_ev)

        # Multi-page site analyzers
        SiteSearchSignalAnalyzer.analyze_site(site_crawl)
        SiteTopicAnalyzer.analyze_site(site_crawl)
        SiteQueryPageAnalyzer.analyze_site(site_crawl)
        SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
        CannibalizationAnalyzer.analyze_site(site_crawl)
        SearchGapAnalyzer.analyze_site(site_crawl)

        # Zero network calls allowed
        mock_url.assert_not_called()
        mock_req.assert_not_called()
        mock_httpx.assert_not_called()


# ---------------------------------------------------------------------------
# 8. Markdown and JSON Reporters Serialization
# ---------------------------------------------------------------------------
def test_markdown_and_json_reporters_render_all_phase9_subsections():
    """Verify MarkdownReporter and JsonReporter format all Phase 9 sections cleanly without error."""
    records = _build_test_crawl_records()
    site_crawl = SiteCrawlResult(pages_crawled=2, crawl_records=records)

    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)
    SiteQueryPageAnalyzer.analyze_site(site_crawl)
    SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
    CannibalizationAnalyzer.analyze_site(site_crawl)
    SearchGapAnalyzer.analyze_site(site_crawl)

    url = records[0].url
    sig_ev = SearchSignalEngine.evaluate(raw_html=PAGE_A_HTML, url=url)
    top_ev = TopicIntelligenceEngine.evaluate(search_signal_ev=sig_ev, url=url)
    qp_ev = QueryPageMappingEngine.evaluate(url=url, search_signal_ev=sig_ev, topic_intel_ev=top_ev)
    intent_ev = SearchIntentEngine.evaluate(url=url, raw_html=PAGE_A_HTML, search_signal_ev=sig_ev, topic_intel_ev=top_ev, query_page_ev=qp_ev)
    cann_ev = CannibalizationAnalyzer.evaluate_page(url=url, query_page_ev=qp_ev, intent_ev=intent_ev)

    results = {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=OnPageEvidence(url=url, title="Calibration Lab", title_length=15)),
        "search_signal_engine": EngineResult(engine_name="search_signal_engine", status="success", search_signal=sig_ev),
        "topic_intelligence_engine": EngineResult(engine_name="topic_intelligence_engine", status="success", topic_intelligence=top_ev),
        "query_page_mapping_engine": EngineResult(engine_name="query_page_mapping_engine", status="success", query_page=qp_ev),
        "search_intent_engine": EngineResult(engine_name="search_intent_engine", status="success", search_intent=intent_ev),
        "cannibalization_analyzer": EngineResult(engine_name="cannibalization_analyzer", status="success", cannibalization=cann_ev),
    }

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize(url, results)
    report.site_crawl = site_crawl

    # 1. Markdown rendering
    md_output = MarkdownReporter.render(report)
    assert "## 📡 SEARCH SIGNAL INTELLIGENCE" in md_output
    assert "## 🧭 TOPIC INTELLIGENCE" in md_output
    assert "## 🗺️ QUERY–PAGE CONCEPT MAPPING" in md_output
    assert "## 🎯 SEARCH INTENT & TOPIC COVERAGE" in md_output
    assert "## 🔀 CANNIBALIZATION & SEARCH GAPS" in md_output

    # 2. JSON rendering
    json_output = JsonReporter.render_audit(report)
    assert '"unified_search_signal"' in json_output
    assert '"unified_topic"' in json_output
    assert '"unified_query_page"' in json_output
    assert '"unified_search_intent"' in json_output
    assert '"unified_cannibalization"' in json_output
    assert '"search_signal_intelligence"' in json_output
    assert '"topic_intelligence"' in json_output
    assert '"query_page_intelligence"' in json_output
    assert '"topic_coverage_intelligence"' in json_output
    assert '"cannibalization_intelligence"' in json_output


# ---------------------------------------------------------------------------
# 9. CLI and FastMCP Output Parity
# ---------------------------------------------------------------------------
def test_cli_and_mcp_output_expose_phase9_data():
    """Verify CLI scorecard and FastMCP rankintel_audit return all Phase 9 telemetry."""
    records = _build_test_crawl_records()
    site_crawl = SiteCrawlResult(pages_crawled=2, crawl_records=records)

    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)
    SiteQueryPageAnalyzer.analyze_site(site_crawl)
    SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
    CannibalizationAnalyzer.analyze_site(site_crawl)
    SearchGapAnalyzer.analyze_site(site_crawl)

    url = records[0].url
    sig_ev = SearchSignalEngine.evaluate(raw_html=PAGE_A_HTML, url=url)
    top_ev = TopicIntelligenceEngine.evaluate(search_signal_ev=sig_ev, url=url)
    qp_ev = QueryPageMappingEngine.evaluate(url=url, search_signal_ev=sig_ev, topic_intel_ev=top_ev)
    intent_ev = SearchIntentEngine.evaluate(url=url, raw_html=PAGE_A_HTML, search_signal_ev=sig_ev, topic_intel_ev=top_ev, query_page_ev=qp_ev)
    cann_ev = CannibalizationAnalyzer.evaluate_page(url=url, query_page_ev=qp_ev, intent_ev=intent_ev)

    results = {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=OnPageEvidence(url=url, title="Calibration Lab", title_length=15)),
        "search_signal_engine": EngineResult(engine_name="search_signal_engine", status="success", search_signal=sig_ev),
        "topic_intelligence_engine": EngineResult(engine_name="topic_intelligence_engine", status="success", topic_intelligence=top_ev),
        "query_page_mapping_engine": EngineResult(engine_name="query_page_mapping_engine", status="success", query_page=qp_ev),
        "search_intent_engine": EngineResult(engine_name="search_intent_engine", status="success", search_intent=intent_ev),
        "cannibalization_analyzer": EngineResult(engine_name="cannibalization_analyzer", status="success", cannibalization=cann_ev),
    }

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize(url, results)
    report.site_crawl = site_crawl

    # 1. MCP tool verification
    with patch("rankintel.mcp.server.EvidenceCollector") as MockCol, \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as MockSyn:
        mock_col = MagicMock()
        mock_col.collect.return_value = results
        mock_col.seo_engine.crawl_site.return_value = site_crawl
        MockCol.return_value = mock_col

        mock_syn = MagicMock()
        mock_syn.synthesize.return_value = report
        MockSyn.return_value = mock_syn

        mcp_res = rankintel_audit(url, deep_crawl=True)

        assert "search_signals_total" in mcp_res
        assert mcp_res["search_signals_total"] > 0
        assert "topics_derived_count" in mcp_res
        assert mcp_res["topics_derived_count"] > 0
        assert "query_page_concepts_mapped_count" in mcp_res
        assert mcp_res["query_page_concepts_mapped_count"] > 0
        assert "search_intent_primary" in mcp_res
        assert "potential_cannibalization_signals_count" in mcp_res
        assert "observable_topic_gaps_count" in mcp_res

    # 2. CLI scorecard verification
    runner = CliRunner()
    with patch("rankintel.evidence.collector.EvidenceCollector.collect", return_value=results), \
         patch("rankintel.intelligence.synthesizer.IntelligenceSynthesizer.synthesize", return_value=report), \
         patch("rankintel.reporters.markdown.MarkdownReporter.save", return_value="audits/test.md"):

        cli_res = runner.invoke(main, ["audit", url])
        assert cli_res.exit_code == 0
        assert "Search Signal" in cli_res.output
        assert "Topic Intelligence" in cli_res.output
        assert "Query" in cli_res.output and "Concept" in cli_res.output
        assert "Search Intent" in cli_res.output
        assert "Cannibalization" in cli_res.output and "Search Gaps" in cli_res.output
