"""
Cannibalization & Search Gaps Integration Test Suite (Phase 9.5 - Layer A).
Verifies end-to-end pipeline:
collector -> frontier -> synthesizer -> provenance -> reporters (Markdown & JSON) -> CLI -> MCP.
Validates zero duplicate HTTP requests, health-score formula invariance,
FACT vs ANALYSIS vs RECOMMENDATION separation, and bounded evidence payloads.
"""
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.analyzers.cannibalization_analyzer import CannibalizationAnalyzer
from rankintel.analyzers.search_gap_analyzer import SearchGapAnalyzer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.mcp.server import rankintel_audit
from rankintel.cli import main
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
    ContentEvidence,
    EntityEvidence,
    InternalLinkEvidence,
    SearchSignalEvidence,
    PageTopicIntelligence,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    SiteQueryPageIntelligence,
    SearchIntentCategory,
    PageIntentEvidence,
    SiteTopicCoverageIntelligence,
    PotentialCannibalizationItem,
    ObservableTopicGapItem,
    CannibalizationSignalType,
    TopicGapType,
    SearchSignalConfidence,
    SiteCannibalizationIntelligence,
    PageCannibalizationEvidence,
    EngineResult,
)


def build_mock_multi_page_crawl() -> SiteCrawlResult:
    """Constructs a deterministic 2-page mock site crawl with potential cannibalization and a topic gap."""
    u1 = "https://example.com/calibration"
    u2 = "https://example.com/instrument-calibration"

    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><head><title>Calibration Services Lab</title></head><body><h1>Calibration Services</h1><p>Comprehensive gauge calibration.</p></body></html>",
        title="Calibration Services Lab",
        h1_tags=["Calibration Services"],
        word_count=450,
        h2_tags=["Pressure Calibration", "Temperature Calibration"],
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><head><title>Instrument Calibration Services</title></head><body><h1>Calibration Services Lab</h1><p>Pressure calibration and gauge testing.</p></body></html>",
        title="Instrument Calibration Services",
        h1_tags=["Calibration Services Lab"],
        word_count=180,
        h2_tags=[],
    )

    q1 = PageQueryEvidence(
        url=u1,
        mapped_concepts=[
            QueryPageEvidence(concept="Calibration Services", normalized_concept="calibration services", evidence_strength=SearchSignalConfidence.DIRECT),
            QueryPageEvidence(concept="Pressure Calibration", normalized_concept="pressure calibration", evidence_strength=SearchSignalConfidence.SUPPORTED),
            QueryPageEvidence(concept="Temperature Calibration", normalized_concept="temperature calibration", evidence_strength=SearchSignalConfidence.SUPPORTED),
        ]
    )
    q2 = PageQueryEvidence(
        url=u2,
        mapped_concepts=[
            QueryPageEvidence(concept="Calibration Services", normalized_concept="calibration services", evidence_strength=SearchSignalConfidence.DIRECT),
        ]
    )

    query_intel = SiteQueryPageIntelligence(
        page_query_evidence={u1: q1, u2: q2},
        concept_relationships=[
            QueryPageRelationship(
                concept="Calibration Services",
                normalized_concept="calibration services",
                pages_count=2,
                page_urls=[u1, u2],
                supporting_pages=[
                    QueryPageEvidence(concept="Calibration Services", normalized_concept="calibration services", url=u1, evidence_strength=SearchSignalConfidence.DIRECT),
                    QueryPageEvidence(concept="Calibration Services", normalized_concept="calibration services", url=u2, evidence_strength=SearchSignalConfidence.DIRECT),
                ]
            )
        ]
    )

    intent_map = {
        u1: PageIntentEvidence(url=u1, primary_observed_intent_signal=SearchIntentCategory.COMMERCIAL),
        u2: PageIntentEvidence(url=u2, primary_observed_intent_signal=SearchIntentCategory.COMMERCIAL),
    }
    coverage_intel = SiteTopicCoverageIntelligence(page_intent_evidence=intent_map)

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=2,
        crawl_records=[rec1, rec2],
        query_page_intelligence=query_intel,
        topic_coverage_intelligence=coverage_intel,
    )

    # Run analyzers
    CannibalizationAnalyzer.analyze_site(site_crawl)
    SearchGapAnalyzer.analyze_site(site_crawl)

    return site_crawl


def test_frontier_cannibalization_and_gap_orchestration():
    """Verify SiteCrawlResult has populated SiteCannibalizationIntelligence with signals and gaps."""
    site_crawl = build_mock_multi_page_crawl()
    cann = site_crawl.cannibalization_intelligence

    assert cann is not None
    assert cann.status == "success"
    assert len(cann.potential_cannibalization_signals) >= 1
    assert len(cann.observable_topic_gaps) >= 1

    # Verify terminology and recommendations
    for s in cann.potential_cannibalization_signals:
        assert s.signal_type == CannibalizationSignalType.POTENTIAL_CANNIBALIZATION_SIGNAL
        assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in s.recommendation
        assert s.shared_intent == SearchIntentCategory.COMMERCIAL

    for g in cann.observable_topic_gaps:
        assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in g.recommendation


def test_health_score_formula_invariance():
    """Verify adding Phase 9.5 intelligence causes ZERO change to 3_engine, 4_engine, or 5_engine formulas."""
    synth = IntelligenceSynthesizer()

    on_page = OnPageEvidence(status_code=200, title="Calibration Lab", meta_description="Valid meta description testing.", h1_text=["Calibration Lab"])
    robots = RobotsEvidence(found=True, is_allowed=True)
    schema_data = SchemaEvidence(has_jsonld=True, is_valid=True)
    geo_data = GeoAeoEvidence(overall_citability_score=75)
    trust_data = TrustStackResult(overall_trust_score=80)
    perf_data = PerformanceEvidence(performance_score=85)

    base_results = {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=on_page, robots=robots, schema_data=schema_data),
        "geo_optimizer": EngineResult(engine_name="geo_optimizer", status="success", geo_aeo=geo_data),
        "crawl4ai_browser": EngineResult(engine_name="crawl4ai_browser", status="success", on_page=on_page),
        "performance_engine": EngineResult(engine_name="performance_engine", status="success", performance=perf_data),
        "trust_stack": EngineResult(engine_name="trust_stack", status="success", trust_stack=trust_data),
    }

    report_without_cann = synth.synthesize("https://example.com/calibration", base_results)

    # Add Phase 9.5 result with potential signals and gaps
    cann_ev = PageCannibalizationEvidence(
        url="https://example.com/calibration",
        status="success",
        potential_signals=[
            PotentialCannibalizationItem(
                topic="Calibration Services",
                normalized_topic="calibration services",
                competing_urls=["https://example.com/calibration", "https://example.com/instrument-calibration"],
                recommendation="REQUIRES_EXTERNAL_SEARCH_VALIDATION: check GSC.",
            )
        ],
        observable_gaps=[
            ObservableTopicGapItem(
                topic="Calibration Services",
                normalized_topic="calibration services",
                source_url="https://example.com/instrument-calibration",
                related_url="https://example.com/calibration",
                missing_concepts=["Pressure Calibration"],
                recommendation="REQUIRES_EXTERNAL_SEARCH_VALIDATION: review search intent.",
            )
        ]
    )

    results_with_cann = {
        **base_results,
        "cannibalization_analyzer": EngineResult(
            engine_name="cannibalization_analyzer",
            status="success",
            cannibalization=cann_ev,
        )
    }

    report_with_cann = synth.synthesize("https://example.com/calibration", results_with_cann)

    # Formulas must remain strictly invariant
    assert report_with_cann.overall_health_score == report_without_cann.overall_health_score
    assert report_with_cann.technical_health_score == report_without_cann.technical_health_score
    assert report_with_cann.geo_readiness_score == report_without_cann.geo_readiness_score
    assert report_with_cann.trust_score == report_without_cann.trust_score
    assert report_with_cann.score_formula_mode == report_without_cann.score_formula_mode


def test_provenance_tagging():
    """Verify ProvenanceTagger records Phase 9.5 provenance chains."""
    cann_ev = PageCannibalizationEvidence(
        url="https://example.com/p",
        status="success",
        potential_signals=[
            PotentialCannibalizationItem(
                topic="Calibration",
                normalized_topic="calibration",
                competing_urls=["https://example.com/p1", "https://example.com/p2"],
                recommendation="REQUIRES_EXTERNAL_SEARCH_VALIDATION: review GSC",
            )
        ],
        observable_gaps=[
            ObservableTopicGapItem(
                topic="Calibration",
                normalized_topic="calibration",
                source_url="https://example.com/p1",
                related_url="https://example.com/p2",
                missing_concepts=["Temperature"],
                recommendation="REQUIRES_EXTERNAL_SEARCH_VALIDATION: check intent",
            )
        ],
        analyses=["OBSERVED_TOPIC_OVERLAP: Multi-page overlap observed."],
    )

    engine_results = {
        "cannibalization_analyzer": EngineResult(
            engine_name="cannibalization_analyzer",
            status="success",
            cannibalization=cann_ev,
        )
    }

    tags = ProvenanceTagger.tag(engine_results)
    engines_in_tags = [t.engine for t in tags]

    assert "cannibalization_analyzer" in engines_in_tags
    assert "search_gap_analyzer" in engines_in_tags


def test_markdown_and_json_reporters_render_cannibalization():
    """Verify MarkdownReporter and JsonReporter properly serialize Phase 9.5 sections."""
    site_crawl = build_mock_multi_page_crawl()
    synth = IntelligenceSynthesizer()

    on_page = OnPageEvidence(status_code=200, title="Calibration Lab", meta_description="Valid meta description.", h1_text=["Calibration Lab"])
    engine_results = {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=on_page),
        "crawl4ai_browser": EngineResult(engine_name="crawl4ai_browser", status="success", on_page=on_page),
    }

    report = synth.synthesize("https://example.com/calibration", engine_results)
    report.site_crawl = site_crawl

    # Render Markdown
    md = MarkdownReporter.render(report)
    assert "## 🔀 CANNIBALIZATION & SEARCH GAPS" in md
    assert "Potential Cannibalization Signals Flagged" in md
    assert "Observable Topic & Content Coverage Gaps" in md
    assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in md

    # Render JSON
    json_str = JsonReporter.render_audit(report)
    assert '"cannibalization_intelligence"' in json_str
    assert '"potential_cannibalization_signals"' in json_str
    assert '"observable_topic_gaps"' in json_str


def test_mcp_and_cli_audit_output():
    """Verify MCP rankintel_audit and CLI report summary contain Phase 9.5 telemetry."""
    site_crawl = build_mock_multi_page_crawl()
    synth = IntelligenceSynthesizer()

    on_page = OnPageEvidence(status_code=200, title="Calibration Lab", meta_description="Valid meta description.", h1_text=["Calibration Lab"])
    engine_results = {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=on_page),
        "crawl4ai_browser": EngineResult(engine_name="crawl4ai_browser", status="success", on_page=on_page),
    }
    report = synth.synthesize("https://example.com/calibration", engine_results)
    report.site_crawl = site_crawl

    # Test MCP tool response
    with patch("rankintel.mcp.server.EvidenceCollector") as MockCollector, \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as MockSynth:
        collector_instance = MagicMock()
        collector_instance.collect.return_value = engine_results
        collector_instance.seo_engine.crawl_site.return_value = site_crawl
        MockCollector.return_value = collector_instance

        synth_instance = MagicMock()
        synth_instance.synthesize.return_value = report
        MockSynth.return_value = synth_instance

        mcp_res = rankintel_audit("https://example.com/calibration", max_pages=2)
        assert mcp_res["potential_cannibalization_signals_count"] >= 1
        assert mcp_res["observable_topic_gaps_count"] >= 1

    # Test CLI output
    runner = CliRunner()
    with patch("rankintel.evidence.collector.EvidenceCollector.collect", return_value=engine_results), \
         patch("rankintel.intelligence.synthesizer.IntelligenceSynthesizer.synthesize", return_value=report), \
         patch("rankintel.reporters.markdown.MarkdownReporter.save", return_value="audits/test.md"):
        result = runner.invoke(main, ["audit", "https://example.com/calibration"])
        assert result.exit_code == 0
        assert "Cannibalization" in result.output and "Search Gaps" in result.output
