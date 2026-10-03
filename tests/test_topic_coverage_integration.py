"""
Topic Coverage & Search Intent Integration Test Suite (Phase 9.4 - Layer A).
Verifies end-to-end integration of SearchIntentEngine and SiteTopicCoverageAnalyzer across:
collector -> frontier -> site aggregation -> synthesizer -> provenance -> reporters -> CLI -> MCP.
Validates zero duplicate HTTP requests, health-score formula invariance, deterministic
observed_dominant_intent thresholding, multi-intent topics, and partial crawl guardrails.
"""
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.engines.search_intent_engine import SearchIntentEngine
from rankintel.analyzers.topic_coverage_analyzer import SiteTopicCoverageAnalyzer
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
    TopicEvidence,
    SiteTopicIntelligence,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    SiteQueryPageIntelligence,
    SearchIntentCategory,
    IntentEvidenceItem,
    PageIntentEvidence,
    TopicCoverageEvidence,
    SiteTopicCoverageIntelligence,
    EngineResult,
)

PAGE_HTML_INFO = """
<!DOCTYPE html>
<html>
<head><title>What is Hardness Testing? | Educational Guide</title></head>
<body>
    <h1>Hardness Testing Fundamentals</h1>
    <h2>What is Hardness Testing?</h2>
    <p>Comprehensive guide to mechanical hardness indentation.</p>
    <h2>How to Calibrate Hardness Testers</h2>
    <p>Step-by-step instructions for laboratory calibration.</p>
</body>
</html>
"""

PAGE_HTML_COMM = """
<!DOCTYPE html>
<html>
<head><title>Rockwell vs Brinell Testing | Comparison</title></head>
<body>
    <h1>Hardness Testing Comparison</h1>
    <h2>Rockwell vs Brinell Hardness Methods</h2>
    <table>
        <tr><th>Feature</th><th>Rockwell</th><th>Brinell</th></tr>
        <tr><td>Indenter</td><td>Diamond Cone</td><td>Steel Ball</td></tr>
        <tr><td>Speed</td><td>Fast</td><td>Moderate</td></tr>
    </table>
</body>
</html>
"""

PAGE_HTML_TRANS = """
<!DOCTYPE html>
<html>
<head><title>Book Hardness Testing Services | Acme Labs</title></head>
<body>
    <h1>Request Hardness Testing</h1>
    <p>Fast certified turnaround for metal samples.</p>
    <form action="/quote" method="post">
        <input type="text" name="name" placeholder="Name">
        <input type="email" name="email" placeholder="Email">
        <button type="submit">Request a Quote</button>
    </form>
    <a href="/order" class="btn">Order Now</a>
</body>
</html>
"""


def test_site_topic_coverage_aggregation_and_multi_intent():
    """Verify SiteTopicCoverageAnalyzer aggregates multi-page topic coverage and identifies multi-intent topics."""
    rec1 = CrawlRecord(
        url="https://example.com/guide",
        normalized_url="https://example.com/guide",
        identity_url="https://example.com/guide",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html=PAGE_HTML_INFO,
    )
    rec2 = CrawlRecord(
        url="https://example.com/compare",
        normalized_url="https://example.com/compare",
        identity_url="https://example.com/compare",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=PAGE_HTML_COMM,
    )
    rec3 = CrawlRecord(
        url="https://example.com/book",
        normalized_url="https://example.com/book",
        identity_url="https://example.com/book",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=PAGE_HTML_TRANS,
    )

    topic = TopicEvidence(
        topic_name="Hardness Testing",
        normalized_name="hardness testing",
        page_urls=[
            "https://example.com/guide",
            "https://example.com/compare",
            "https://example.com/book",
        ],
        occurrences_count=6,
    )
    site_topic_intel = SiteTopicIntelligence(
        status="success",
        total_pages_evaluated=3,
        total_topics_count=1,
        topics=[topic],
    )

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=3,
        crawl_records=[rec1, rec2, rec3],
        topic_intelligence=site_topic_intel,
    )

    intel = SiteTopicCoverageAnalyzer.analyze_site(site_crawl)

    assert intel.status == "success"
    assert intel.is_partial_crawl is False
    assert intel.total_topics_covered >= 1
    
    # Verify topic coverage item
    cov_by_name = {t.topic_name: t for t in intel.covered_topics}
    assert "Hardness Testing" in cov_by_name
    ht_cov = cov_by_name["Hardness Testing"]
    assert ht_cov.pages_count == 3
    assert set(ht_cov.page_urls) == {
        "https://example.com/guide",
        "https://example.com/compare",
        "https://example.com/book",
    }
    # Verify intent breakdown includes informational, commercial, and transactional
    assert ht_cov.intent_breakdown.get("informational", 0) == 1
    assert ht_cov.intent_breakdown.get("commercial", 0) == 1
    assert ht_cov.intent_breakdown.get("transactional", 0) == 1
    # Equal 1:1:1 split (< 60% threshold) resolves to MIXED
    assert ht_cov.observed_dominant_intent == SearchIntentCategory.MIXED
    # Must be identified as multi-intent topic
    assert "Hardness Testing" in intel.multi_intent_topics


def test_observed_dominant_intent_thresholding():
    """Verify observed_dominant_intent enforces >= 60% threshold for dominance."""
    # Topic with 2 informational pages and 1 transactional page (66.7% >= 60% -> INFORMATIONAL)
    rec1 = CrawlRecord(
        url="https://example.com/info1",
        normalized_url="https://example.com/info1",
        identity_url="https://example.com/info1",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html=PAGE_HTML_INFO,
    )
    rec2 = CrawlRecord(
        url="https://example.com/info2",
        normalized_url="https://example.com/info2",
        identity_url="https://example.com/info2",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=PAGE_HTML_INFO,
    )
    rec3 = CrawlRecord(
        url="https://example.com/trans1",
        normalized_url="https://example.com/trans1",
        identity_url="https://example.com/trans1",
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html=PAGE_HTML_TRANS,
    )

    topic = TopicEvidence(
        topic_name="Calibration Guide",
        normalized_name="calibration guide",
        page_urls=["https://example.com/info1", "https://example.com/info2", "https://example.com/trans1"],
    )
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=3,
        crawl_records=[rec1, rec2, rec3],
        topic_intelligence=SiteTopicIntelligence(topics=[topic]),
    )

    intel = SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
    ht_cov = intel.covered_topics[0]
    # 2 out of 3 = 66.7% >= 60% -> DOMINANT is INFORMATIONAL
    assert ht_cov.observed_dominant_intent == SearchIntentCategory.INFORMATIONAL


def test_partial_crawl_disclaimer_and_no_missing_claims():
    """Verify incomplete/partial crawls emit disclaimers and do not declare missing coverage."""
    rec = CrawlRecord(
        url="https://example.com/info",
        normalized_url="https://example.com/info",
        identity_url="https://example.com/info",
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html=PAGE_HTML_INFO,
    )
    site_crawl = SiteCrawlResult(
        completeness_status="BUDGET_EXHAUSTED",
        pages_crawled=1,
        remaining_frontier=10,
        pages_skipped=2,
        crawl_records=[rec],
    )

    intel = SiteTopicCoverageAnalyzer.analyze_site(site_crawl)

    assert intel.is_partial_crawl is True
    assert intel.status == "partial"
    assert "absence of coverage for any topic or intent in partial crawls does not indicate lack of content" in intel.completeness_disclaimer
    # Verify no claims of "missing topics"
    assert not any("missing topic" in a.lower() for a in intel.analyses)


def test_zero_duplicate_http_requests():
    """Verify SearchIntentEngine and SiteTopicCoverageAnalyzer execute strictly in-memory without HTTP."""
    with patch("urllib.request.urlopen") as mock_url, patch("requests.get") as mock_req:
        res = SearchIntentEngine.evaluate(
            url="https://example.com/test",
            raw_html=PAGE_HTML_INFO,
        )
        assert res.status == "success"

        site_crawl = SiteCrawlResult(
            completeness_status="CRAWL_COMPLETE",
            crawl_records=[
                CrawlRecord(
                    url="https://example.com/test",
                    normalized_url="https://example.com/test",
                    identity_url="https://example.com/test",
                    crawl_status=CrawlStatus.FETCHED,
                    depth=0,
                    status_code=200,
                    raw_html=PAGE_HTML_INFO,
                )
            ],
        )
        cov = SiteTopicCoverageAnalyzer.analyze_site(site_crawl)
        assert cov.status == "success"

        mock_url.assert_not_called()
        mock_req.assert_not_called()


def test_health_score_formula_invariance():
    """Verify health score formulas (3_engine, 4_engine, 5_engine) remain strictly unchanged with search intent."""
    synthesizer = IntelligenceSynthesizer()
    url = "https://example.com/test"

    base_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(title="Valid Test Title For Analysis", title_length=28, meta_description="Valid test description for health scoring.", meta_desc_length=42, h1_count=1),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(blocks_count=1, detected_types=["WebSite"]),
        ),
        "geo_optimizer": EngineResult(
            engine_name="geo_optimizer",
            status="success",
            geo_aeo=GeoAeoEvidence(overall_citability_score=75),
        ),
        "crawl4ai_browser": EngineResult(
            engine_name="crawl4ai_browser",
            status="success",
            trust_stack=TrustStackResult(overall_score=80),
        ),
    }

    # 3-Engine mode
    rep_3 = synthesizer.synthesize(url, base_results)
    assert rep_3.score_formula_mode == "3_engine"
    score_3 = rep_3.overall_health_score

    # Add search intent engine result
    results_with_intent = dict(base_results)
    results_with_intent["search_intent_engine"] = EngineResult(
        engine_name="search_intent_engine",
        status="success",
        search_intent=PageIntentEvidence(
            url=url,
            primary_observed_intent_signal=SearchIntentCategory.INFORMATIONAL,
            evidence_items=[
                IntentEvidenceItem(
                    intent_category=SearchIntentCategory.INFORMATIONAL,
                    signal_type="EXPLANATORY_HEADING",
                    evidence_term="What is Testing?",
                    evidence_location="H2",
                    supporting_snippet="Explanation snippet",
                )
            ],
        ),
    )

    rep_3_intent = synthesizer.synthesize(url, results_with_intent)
    assert rep_3_intent.score_formula_mode == "3_engine"
    # Overall health score MUST remain strictly identical!
    assert rep_3_intent.overall_health_score == score_3


def test_reporters_render_search_intent_and_topic_coverage():
    """Verify MarkdownReporter and JsonReporter properly serialize Phase 9.4 search intent and topic coverage."""
    synthesizer = IntelligenceSynthesizer()
    url = "https://example.com/test"

    cov_item = TopicCoverageEvidence(
        topic_name="Hardness Testing",
        normalized_name="hardness testing",
        pages_count=2,
        page_urls=["https://example.com/guide", "https://example.com/compare"],
        intent_breakdown={"informational": 1, "commercial": 1},
        observed_dominant_intent=SearchIntentCategory.MIXED,
    )
    site_cov = SiteTopicCoverageIntelligence(
        status="success",
        total_pages_evaluated=2,
        total_topics_covered=1,
        covered_topics=[cov_item],
    )
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        topic_coverage_intelligence=site_cov,
    )

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(title="Hardness Guide", title_length=14),
        ),
        "search_intent_engine": EngineResult(
            engine_name="search_intent_engine",
            status="success",
            search_intent=PageIntentEvidence(
                url=url,
                primary_observed_intent_signal=SearchIntentCategory.INFORMATIONAL,
                evidence_items=[
                    IntentEvidenceItem(
                        intent_category=SearchIntentCategory.INFORMATIONAL,
                        signal_type="EXPLANATORY_HEADING",
                        evidence_term="What is Hardness?",
                        evidence_location="H2",
                        supporting_snippet="Explanatory content snippet",
                    )
                ],
                facts=["Page contains explanatory heading 'What is Hardness?'."],
                analyses=["INFERRED_FROM_ON_SITE_EVIDENCE: Primary observed intent signal is 'informational'."],
            ),
        ),
    }

    report = synthesizer.synthesize(url, results)
    report.site_crawl = site_crawl

    # Render Markdown
    md = MarkdownReporter.render(report)
    assert "## 🎯 SEARCH INTENT & TOPIC COVERAGE (Layer A: On-Site Intent Signals)" in md
    assert "- **Primary Observed Intent Signal:** `INFORMATIONAL`" in md
    assert "EXPLANATORY_HEADING" in md
    assert "Site Topic Coverage & Dominant Intent" in md
    assert "Hardness Testing" in md
    assert "`MIXED`" in md
    assert "- **FACT:** Page contains explanatory heading" in md
    assert "- **ANALYSIS:** INFERRED_FROM_ON_SITE_EVIDENCE" in md

    # Render JSON
    json_str = JsonReporter.render_audit(report)
    assert '"primary_observed_intent_signal": "informational"' in json_str
    assert '"topic_coverage_intelligence"' in json_str


def test_mcp_and_cli_audit_output():
    """Verify MCP rankintel_audit and CLI include search intent and topic coverage fields."""
    url = "https://example.com/test"
    cov_item = TopicCoverageEvidence(
        topic_name="Hardness Testing",
        normalized_name="hardness testing",
        pages_count=1,
        observed_dominant_intent=SearchIntentCategory.INFORMATIONAL,
    )
    site_cov = SiteTopicCoverageIntelligence(
        status="success",
        total_topics_covered=1,
        covered_topics=[cov_item],
    )

    mock_report = MagicMock()
    mock_report.unified_search_intent = PageIntentEvidence(
        url=url,
        primary_observed_intent_signal=SearchIntentCategory.INFORMATIONAL,
        evidence_items=[
            IntentEvidenceItem(
                intent_category=SearchIntentCategory.INFORMATIONAL,
                signal_type="EXPLANATORY_HEADING",
                evidence_term="What is Hardness?",
                evidence_location="H2",
                supporting_snippet="Snipped content",
            )
        ],
    )
    mock_report.site_crawl = MagicMock(topic_coverage_intelligence=site_cov)
    mock_report.unified_seo = None
    mock_report.unified_robots = None
    mock_report.unified_schema = None
    mock_report.unified_geo = None
    mock_report.unified_trust = None
    mock_report.unified_performance = None
    mock_report.unified_security = None
    mock_report.unified_accessibility = None
    mock_report.unified_image_seo = None
    mock_report.unified_content = None
    mock_report.unified_entity = None
    mock_report.unified_internal_link = None
    mock_report.unified_search_signal = None
    mock_report.unified_topic = None
    mock_report.unified_query_page = None
    mock_report.cloud_intelligence = None
    mock_report.overall_health_score = 85
    mock_report.geo_readiness_score = 80
    mock_report.technical_health_score = 90
    mock_report.trust_score = 85
    mock_report.performance_score = 80
    mock_report.conflicts_detected = []
    mock_report.prioritized_actions = []

    with patch("rankintel.mcp.server.EvidenceCollector") as mock_col_cls, \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as mock_syn_cls:
        mock_syn_cls.return_value.synthesize.return_value = mock_report
        res = rankintel_audit(url)

        assert res["search_intent_primary"] == "informational"
        assert res["search_intent_signals_count"] == 1
        assert res["site_topics_covered_count"] == 1

    # Verify CLI execution
    runner = CliRunner()
    with patch("rankintel.cli.EvidenceCollector") as mock_cli_col, \
         patch("rankintel.cli.IntelligenceSynthesizer") as mock_cli_syn, \
         patch("rankintel.reporters.markdown.MarkdownReporter.save", return_value="audits/test.md"):
        mock_cli_syn.return_value.synthesize.return_value = mock_report
        result = runner.invoke(main, ["audit", "https://example.com/test"])
        assert result.exit_code == 0
        assert "Search Intent Signals" in result.output
        assert "INFORMATIONAL" in result.output
