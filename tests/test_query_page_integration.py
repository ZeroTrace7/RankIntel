"""
Query-Page Mapping Integration & Regression Test Suite (Phase 9.3 - Layer A).
Verifies complete coexistence of QueryPageMappingEngine and SiteQueryPageAnalyzer through the full RankIntel pipeline:
crawl -> in-memory evidence collection -> site aggregation -> synthesis -> provenance -> reporting -> MCP.
Validates zero network requests, health-score formula invariance, neutral POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP,
bounded collections, and explicit partial crawl coverage disclaimers.
"""
import pytest
from unittest.mock import MagicMock, patch

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.engines.query_page_mapping_engine import QueryPageMappingEngine
from rankintel.analyzers.query_page_analyzer import SiteQueryPageAnalyzer
from rankintel.analyzers.search_signal_analyzer import SiteSearchSignalAnalyzer
from rankintel.analyzers.topic_analyzer import SiteTopicAnalyzer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.mcp.server import rankintel_audit
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
    SearchSignalItem,
    SearchSignalLocation,
    SearchSignalConfidence,
    PageTopicIntelligence,
    TopicEvidence,
    TopicTermMembership,
    SiteTopicIntelligence,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    SiteQueryPageIntelligence,
    EngineResult,
)


HTML_PAGE_1 = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Precision Calibration Services | Acme Labs</title>
    <meta name="description" content="Certified precision calibration and industrial measurement services for aerospace manufacturing." />
</head>
<body>
    <main>
        <h1>Precision Calibration Laboratories</h1>
        <p>Acme Labs provides certified calibration standards and precision calibration solutions.</p>
        <h2>Traceable Calibration Standards</h2>
        <p>Our instruments deliver national traceability under ISO certification.</p>
    </main>
</body>
</html>
"""

HTML_PAGE_2 = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Calibration Equipment & Standards | Acme Labs</title>
    <meta name="description" content="Explore advanced precision calibration instruments and optical measurement benches." />
</head>
<body>
    <main>
        <h1>Precision Calibration Equipment Catalog</h1>
        <p>Discover our accredited precision calibration instruments engineered for high-throughput testing.</p>
        <h2>Spectrometer Calibration Benchmarks</h2>
        <p>High sensitivity optical emission equipment for metallurgical purity verification.</p>
    </main>
</body>
</html>
"""


def test_site_query_page_analyzer_multi_page_and_overlap():
    """
    Verify SiteQueryPageAnalyzer builds inverse mapping and neutrally identifies
    POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP when multiple pages provide strong evidence.
    """
    rec1 = CrawlRecord(
        url="https://example.com/services",
        depth=1,
        status_code=200,
        status=CrawlStatus.SUCCESS,
        raw_html=HTML_PAGE_1,
        title="Precision Calibration Services | Acme Labs",
    )
    rec2 = CrawlRecord(
        url="https://example.com/products",
        depth=1,
        status_code=200,
        status=CrawlStatus.SUCCESS,
        raw_html=HTML_PAGE_2,
        title="Calibration Equipment & Standards | Acme Labs",
    )

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=2,
        crawl_records=[rec1, rec2],
    )

    # Populate search signal and topic intelligence
    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)

    # Run SiteQueryPageAnalyzer
    intel = SiteQueryPageAnalyzer.analyze_site(site_crawl)

    assert isinstance(intel, SiteQueryPageIntelligence)
    assert intel.status == "success"
    assert intel.total_pages_evaluated == 2
    assert intel.is_partial_crawl is False
    assert "complete crawl graph" in intel.completeness_disclaimer.lower()
    assert intel.total_concepts_mapped >= 1

    # Verify inverse mapping
    rel_map = {r.normalized_concept: r for r in intel.concept_relationships}
    assert len(rel_map) > 0

    # Verify that multi-page overlap is labeled POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP
    # and strictly NOT 'cannibalization'
    for rel in intel.concept_relationships:
        if rel.overlap_status:
            assert rel.overlap_status == "POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP"
            assert "cannibalization" not in rel.overlap_status.lower()
            assert rel.overlap_rationale is not None
            assert len(rel.page_urls) >= 2
            # Verify bounded supporting pages (<= 10)
            assert len(rel.supporting_pages) <= 10


def test_partial_crawl_completeness_disclaimer():
    """Verify that partial crawls receive explicit disclaimer without treating absence as proof."""
    rec = CrawlRecord(
        url="https://example.com/page1",
        depth=1,
        status_code=200,
        status=CrawlStatus.SUCCESS,
        raw_html=HTML_PAGE_1,
    )
    # Simulate a partial crawl with remaining frontier
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_PARTIAL",
        remaining_frontier=45,
        pages_skipped=5,
        pages_crawled=1,
        crawl_records=[rec],
    )

    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)
    intel = SiteQueryPageAnalyzer.analyze_site(site_crawl)

    assert intel.is_partial_crawl is True
    assert "Observed query-page mappings reflect crawled pages only" in intel.completeness_disclaimer
    assert "absence of a page/concept mapping in partial crawls does not indicate lack of coverage" in intel.completeness_disclaimer


def test_evidence_collector_integration():
    """Verify EvidenceCollector properly coordinates QueryPageMappingEngine without duplicate HTTP."""
    collector = EvidenceCollector()
    
    # Mock seo and browser engines to avoid actual network requests
    on_page = OnPageEvidence(
        url="https://example.com/test",
        title="Precision Calibration Systems",
        h1_text=["Precision Calibration Systems"],
        h2_text=["Accredited Metrology"],
    )
    collector.seo_engine.execute = MagicMock(return_value=EngineResult(
        engine_name="advertools_seo",
        status="success",
        on_page=on_page,
    ))
    collector.browser_engine.execute_sync = MagicMock(return_value=EngineResult(
        engine_name="browser_engine",
        status="success",
        raw_html=HTML_PAGE_1,
    ))
    collector.performance_engine.execute = MagicMock(return_value=EngineResult(
        engine_name="performance_engine",
        status="skipped",
    ))

    results = collector.collect("https://example.com/test")

    assert "query_page_mapping_engine" in results
    qp_res = results["query_page_mapping_engine"]
    assert qp_res.status == "success"
    assert qp_res.query_page is not None
    assert qp_res.query_page.total_concepts_mapped >= 1
    assert qp_res.query_page.direct_concepts_count >= 1


def test_health_score_formula_invariance():
    """Verify that Query-Page Mapping does not alter the 3-engine, 4-engine, or 5-engine health score formulas."""
    collector = EvidenceCollector()
    on_page = OnPageEvidence(
        url="https://example.com/test",
        title="Industrial Calibration Testing",
        h1_text=["Industrial Calibration Testing"],
    )
    mock_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=on_page,
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["Organization"]),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(overall_citability_score=75),
        ),
        "performance_engine": EngineResult(
            engine_name="performance_engine",
            status="success",
            performance=PerformanceEvidence(overall_performance_score=85, source="pagespeed_crux_field"),
        ),
    }

    synth = IntelligenceSynthesizer()

    # 1. Synthesize without query_page_mapping_engine
    report_baseline = synth.synthesize("https://example.com/test", mock_results)
    baseline_score = report_baseline.overall_health_score
    baseline_mode = report_baseline.score_formula_mode

    # 2. Add query_page_mapping_engine
    mock_results_with_qp = dict(mock_results)
    qp_ev = QueryPageMappingEngine.evaluate(
        url="https://example.com/test",
        on_page=on_page,
    )
    mock_results_with_qp["query_page_mapping_engine"] = EngineResult(
        engine_name="query_page_mapping_engine",
        status="success",
        query_page=qp_ev,
    )

    report_with_qp = synth.synthesize("https://example.com/test", mock_results_with_qp)

    # Verify strict mathematical formula invariance
    assert report_with_qp.overall_health_score == baseline_score
    assert report_with_qp.technical_health_score == report_baseline.technical_health_score
    assert report_with_qp.geo_readiness_score == report_baseline.geo_readiness_score
    assert report_with_qp.trust_score == report_baseline.trust_score
    assert report_with_qp.performance_score == report_baseline.performance_score
    assert report_with_qp.score_formula_mode == baseline_mode
    assert report_with_qp.unified_query_page is not None


def test_provenance_tagging():
    """Verify ProvenanceTagger tags QueryPageMappingEngine findings."""
    on_page = OnPageEvidence(
        url="https://example.com/test",
        title="Calibration Standards",
        h1_text=["Calibration Standards"],
    )
    qp_ev = QueryPageEvidence(
        concept="Calibration Standards",
        normalized_concept="calibration standards",
        url="https://example.com/test",
        evidence_strength=SearchSignalConfidence.DIRECT,
        evidence_locations=["TITLE", "H1"],
        occurrences_count=2,
        has_title_or_h1=True,
    )
    page_qp = PageQueryEvidence(
        url="https://example.com/test",
        status="success",
        total_concepts_mapped=1,
        direct_concepts_count=1,
        mapped_concepts=[qp_ev],
        primary_concepts=["Calibration Standards"],
        analyses=["1 direct primary concepts"],
    )
    mock_results = {
        "query_page_mapping_engine": EngineResult(
            engine_name="query_page_mapping_engine",
            status="success",
            query_page=page_qp,
        )
    }

    tags = ProvenanceTagger.tag(mock_results)
    qp_tags = [t for t in tags if t.engine == "query_page_mapping_engine"]
    assert len(qp_tags) >= 1
    assert any("Query-Page Mapping" in t.finding for t in qp_tags)
    assert any("Calibration Standards" in t.evidence_snippet for t in qp_tags)


def test_markdown_and_json_reporters():
    """Verify MarkdownReporter and JsonReporter properly serialize query-page intelligence."""
    qp_ev = QueryPageEvidence(
        concept="Metallurgical Analysis",
        normalized_concept="metallurgical analysis",
        url="https://example.com/lab",
        evidence_strength=SearchSignalConfidence.DIRECT,
        evidence_locations=["TITLE", "H1"],
        occurrences_count=3,
        has_title_or_h1=True,
        supporting_snippets=["H1: 'Metallurgical Analysis Lab'"],
    )
    page_qp = PageQueryEvidence(
        url="https://example.com/lab",
        status="success",
        total_concepts_mapped=1,
        direct_concepts_count=1,
        mapped_concepts=[qp_ev],
        primary_concepts=["Metallurgical Analysis"],
        facts=["Mapped 1 observed concepts with on-page evidence."],
        analyses=["1 direct primary concepts."],
    )

    rec = CrawlRecord(
        url="https://example.com/lab",
        status_code=200,
        status=CrawlStatus.SUCCESS,
        raw_html=HTML_PAGE_1,
    )
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=1,
        crawl_records=[rec],
    )
    site_qp = SiteQueryPageIntelligence(
        status="success",
        total_pages_evaluated=1,
        total_concepts_mapped=1,
        multi_page_overlap_count=0,
        concept_relationships=[
            QueryPageRelationship(
                concept="Metallurgical Analysis",
                normalized_concept="metallurgical analysis",
                pages_count=1,
                page_urls=["https://example.com/lab"],
                direct_pages=["https://example.com/lab"],
                evidence_locations=["TITLE", "H1"],
                total_occurrences=3,
                title_or_h1_pages=["https://example.com/lab"],
            )
        ],
    )
    site_crawl.query_page_intelligence = site_qp

    mock_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(url="https://example.com/lab", title="Metallurgical Analysis"),
        ),
        "query_page_mapping_engine": EngineResult(
            engine_name="query_page_mapping_engine",
            status="success",
            query_page=page_qp,
        ),
    }

    synth = IntelligenceSynthesizer()
    report = synth.synthesize("https://example.com/lab", mock_results)
    report.site_crawl = site_crawl

    # Markdown rendering
    md_content = MarkdownReporter.render(report)
    assert "QUERY–PAGE CONCEPT MAPPING" in md_content
    assert "Metallurgical Analysis" in md_content
    assert "Site-Wide Query–Page Concept Mapping" in md_content

    # JSON rendering
    json_str = JsonReporter.render_audit(report)
    assert "unified_query_page" in json_str
    assert "query_page_intelligence" in json_str
    assert "metallurgical analysis" in json_str.lower()


def test_mcp_tool_query_page_fields():
    """Verify MCP server exposes query_page telemetry in rankintel_audit output."""
    with patch("rankintel.mcp.server.EvidenceCollector") as MockCollector, \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as MockSynthesizer, \
         patch("rankintel.mcp.server.MarkdownReporter") as MockMd, \
         patch("rankintel.mcp.server.JsonReporter") as MockJson:

        mock_report = MagicMock()
        mock_report.url = "https://example.com/test"
        mock_report.domain = "example.com"
        mock_report.overall_health_score = 80
        mock_report.geo_readiness_score = 75
        mock_report.technical_health_score = 85
        mock_report.trust_score = 80
        mock_report.performance_score = 90
        mock_report.keyword_score = 0
        mock_report.engines_executed = ["advertools_seo"]
        mock_report.conflicts_detected = []
        mock_report.prioritized_actions = []
        mock_report.unified_security = None
        mock_report.unified_accessibility = None
        mock_report.unified_image_seo = None
        mock_report.unified_content = None
        mock_report.unified_entity = None
        mock_report.unified_internal_link = None
        mock_report.unified_search_signal = None
        mock_report.unified_topic = None

        # Phase 9.3 query page mock
        mock_qp = MagicMock()
        mock_qp.total_concepts_mapped = 8
        mock_qp.direct_concepts_count = 3
        mock_report.unified_query_page = mock_qp

        mock_site_crawl = MagicMock()
        mock_site_crawl.query_page_intelligence.multi_page_overlap_count = 2
        mock_site_crawl.search_signal_intelligence.recurring_concepts_count = 5
        mock_site_crawl.topic_intelligence.recurring_topics_count = 4
        mock_report.site_crawl = mock_site_crawl

        MockSynthesizer.return_value.synthesize.return_value = mock_report
        MockMd.save.return_value = "audits/example.com-2026-10-04.md"
        MockJson.save_audit.return_value = "audits/example.com-2026-10-04.json"

        res = rankintel_audit("https://example.com/test")

        assert res["query_page_concepts_mapped_count"] == 8
        assert res["query_page_direct_concepts_count"] == 3
        assert res["site_multi_page_overlaps_count"] == 2
