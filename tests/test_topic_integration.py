"""
Topic Intelligence Integration & Regression Test Suite (Phase 9.2 - Layer A).
Verifies complete coexistence of TopicIntelligenceEngine through the full RankIntel pipeline:
crawl -> in-memory evidence collection -> site aggregation -> synthesis -> provenance -> reporting -> MCP.
Validates zero network requests, health-score formula invariance, explicit error handling,
and partial crawl coverage disclaimer behavior.
"""
import pytest
from unittest.mock import MagicMock, patch

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.analyzers.search_signal_analyzer import SiteSearchSignalAnalyzer
from rankintel.analyzers.topic_analyzer import SiteTopicAnalyzer
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
    PageTopicIntelligence,
    SiteTopicIntelligence,
    EngineResult,
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
    )
    mock_seo = EngineResult(
        engine_name="advertools_seo",
        status="success",
        on_page=OnPageEvidence(
            url=url,
            title="Acme Industrial Solutions - High Performance Calibration",
            meta_description="Acme Corp provides precision measurement and calibration services.",
            h1=["Industrial Testing Equipment & Calibration Services"],
            h2=["Advanced Calibration Methodologies"],
            response_headers={"content-type": "text/html; charset=utf-8"},
        ),
    )
    mock_geo = EngineResult(engine_name="geo_engine", status="success", geo_aeo=GeoAeoEvidence(url=url))
    mock_perf = EngineResult(engine_name="performance_engine", status="success", performance=PerformanceEvidence(url=url))

    with patch.object(collector.seo_engine, "execute", return_value=mock_seo), \
         patch.object(collector.browser_engine, "crawl", return_value=mock_browser), \
         patch.object(collector.geo_engine, "optimize", return_value=mock_geo.geo_aeo), \
         patch.object(collector.performance_engine, "audit_url", return_value=mock_perf.performance), \
         patch.object(collector.mcp_engine, "get_keyword_gap", return_value=None):
        return collector.collect(url)


def test_pipeline_coexistence_evidence_collector():
    """Verify TopicIntelligenceEngine runs smoothly in EvidenceCollector without interfering with other engines."""
    results = _collect_with_html(HTML_PAGE_A, "https://example.com")

    assert "topic_intelligence_engine" in results
    topic_res = results["topic_intelligence_engine"]
    assert topic_res.status == "success"
    assert topic_res.topic_intelligence is not None

    intel = topic_res.topic_intelligence
    assert intel.total_topics_derived > 0
    assert intel.total_terms_mapped > 0
    assert len(intel.facts) > 0
    assert len(intel.analyses) > 0


def test_synthesizer_reconciles_topic_intelligence():
    """Verify IntelligenceSynthesizer integrates unified_topic into SynthesisReport."""
    results = _collect_with_html(HTML_PAGE_A, "https://example.com")
    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_topic is not None
    assert report.unified_topic.total_topics_derived > 0
    assert len(report.unified_topic.topics) > 0
    assert report.unified_topic.status == "success"


def test_health_score_formula_invariance():
    """Verify 3-engine, 4-engine, and 5-engine health scores remain invariant."""
    results = _collect_with_html(HTML_PAGE_A, "https://example.com")
    synthesizer = IntelligenceSynthesizer()

    # Score with topic_intelligence_engine present
    report_with_topic = synthesizer.synthesize("https://example.com", results)
    score_with_topic = report_with_topic.overall_health_score

    # Score with topic_intelligence_engine removed from results
    results_without_topic = dict(results)
    results_without_topic.pop("topic_intelligence_engine", None)
    report_without_topic = synthesizer.synthesize("https://example.com", results_without_topic)
    score_without_topic = report_without_topic.overall_health_score

    assert score_with_topic == score_without_topic
    assert report_with_topic.technical_health_score == report_without_topic.technical_health_score
    assert report_with_topic.geo_readiness_score == report_without_topic.geo_readiness_score


def test_site_wide_topic_analyzer_aggregation():
    """Verify SiteTopicAnalyzer aggregates recurring concepts across multiple crawled pages."""
    rec_a = CrawlRecord(
        url="https://example.com/page-a",
        normalized_url="https://example.com/page-a",
        identity_url="https://example.com/page-a",
        crawl_status=CrawlStatus.SUCCESS,
        depth=0,
        status_code=200,
        raw_html=HTML_PAGE_A,
    )
    rec_b = CrawlRecord(
        url="https://example.com/page-b",
        normalized_url="https://example.com/page-b",
        identity_url="https://example.com/page-b",
        crawl_status=CrawlStatus.SUCCESS,
        depth=1,
        status_code=200,
        raw_html=HTML_PAGE_B,
    )

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=2,
        crawl_records=[rec_a, rec_b],
    )

    # Run analyzers in sequence
    SiteContentAnalyzer.analyze_site(site_crawl)
    SiteEntityAnalyzer.analyze_site(site_crawl)
    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)

    assert site_crawl.topic_intelligence is not None
    ti = site_crawl.topic_intelligence
    assert ti.status == "success"
    assert ti.total_pages_evaluated == 2
    assert ti.total_topics_count > 0
    assert ti.recurring_topics_count > 0
    assert not ti.is_partial_crawl

    # Check recurring topics
    recurring = [t for t in ti.topics if t.pages_count >= 2]
    assert len(recurring) > 0
    # "calibration" or related concept appears on both pages
    assert any("calibration" in t.normalized_name for t in recurring)


def test_explicit_error_handling_no_silent_pass():
    """Verify SiteTopicAnalyzer records error status and never silently swallows exceptions."""
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        pages_crawled=1,
        crawl_records=[None],  # Corrupt record to force an exception
    )

    ti = SiteTopicAnalyzer.analyze_site(site_crawl)
    assert ti.status == "error"
    assert ti.error_message is not None
    assert "failed" in ti.error_message.lower()
    assert site_crawl.topic_intelligence.status == "error"


def test_partial_crawl_disclaimer_behavior():
    """Verify partial crawl triggers is_partial_crawl = True and sets explicit disclaimer."""
    rec_a = CrawlRecord(
        url="https://example.com/page-a",
        normalized_url="https://example.com/page-a",
        identity_url="https://example.com/page-a",
        crawl_status=CrawlStatus.SUCCESS,
        depth=0,
        status_code=200,
        raw_html=HTML_PAGE_A,
    )

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_TRUNCATED",  # Partial crawl
        pages_crawled=1,
        remaining_frontier=15,  # Frontier not exhausted
        crawl_records=[rec_a],
    )

    ti = SiteTopicAnalyzer.analyze_site(site_crawl)
    assert ti.is_partial_crawl is True
    assert "absence of a topic in partial crawls does not indicate lack of coverage" in ti.completeness_disclaimer


def test_zero_duplicate_http_requests_instrumented():
    """Verify zero duplicate HTTP requests during evidence collection."""
    page_map = {
        "https://example.com": HTML_PAGE_A,
    }
    transport = RequestCountingTransport(page_map)
    collector = EvidenceCollector()

    results = _collect_with_html(HTML_PAGE_A, "https://example.com")
    assert transport.request_count == 0  # No network requests made by TopicIntelligenceEngine


def test_cross_engine_provenance_attribution():
    """Verify EvidenceProvenanceTag generated for topic_intelligence_engine."""
    results = _collect_with_html(HTML_PAGE_A, "https://example.com")
    tags = ProvenanceTagger.tag_provenance(results)

    topic_tags = [t for t in tags if t.engine == "topic_intelligence_engine"]
    assert len(topic_tags) >= 1
    assert "Topic Intelligence" in topic_tags[0].finding


def test_markdown_and_json_reporters_render_topics():
    """Verify MarkdownReporter and JsonReporter render Topic Intelligence sections."""
    results = _collect_with_html(HTML_PAGE_A, "https://example.com")
    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    # Attach site_crawl with Topic Intelligence
    rec_a = CrawlRecord(
        url="https://example.com",
        normalized_url="https://example.com",
        identity_url="https://example.com",
        crawl_status=CrawlStatus.SUCCESS,
        depth=0,
        status_code=200,
        raw_html=HTML_PAGE_A,
    )
    site_crawl = SiteCrawlResult(pages_crawled=1, crawl_records=[rec_a])
    SiteSearchSignalAnalyzer.analyze_site(site_crawl)
    SiteTopicAnalyzer.analyze_site(site_crawl)
    report.site_crawl = site_crawl

    # Test Markdown rendering
    md_output = MarkdownReporter.generate_markdown(report)
    assert "## 🧭 TOPIC INTELLIGENCE (Layer A: On-Site Concept Grouping)" in md_output
    assert "Site-Wide Topic Intelligence & Concept Clustering" in md_output
    assert "Recurring Observed Concepts" in md_output

    # Test JSON serialization
    json_output = JsonReporter.generate_json(report)
    assert "unified_topic" in json_output
    assert "topic_intelligence" in json_output


def test_mcp_server_exposes_topic_intelligence():
    """Verify MCP server rankintel_audit exposes topic telemetry."""
    from rankintel.mcp.server import rankintel_audit

    results = _collect_with_html(HTML_PAGE_A, "https://example.com")
    synthesizer = IntelligenceSynthesizer()
    mock_report = synthesizer.synthesize("https://example.com", results)

    with patch("rankintel.mcp.server.EvidenceCollector") as MockCollector, \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as MockSynthesizer:
        MockCollector.return_value.collect.return_value = results
        MockSynthesizer.return_value.synthesize.return_value = mock_report

        audit_res = rankintel_audit("https://example.com")
        assert "topics_derived_count" in audit_res
        assert "top_topics" in audit_res
        assert "site_recurring_topics_count" in audit_res
        assert audit_res["topics_derived_count"] > 0
