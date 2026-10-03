"""
Integration tests for Content Intelligence Engine (Phase 8.1).
Validates EvidenceCollector, IntelligenceSynthesizer, MarkdownReporter,
ConflictDetector, ProvenanceTagger, and CrawlFrontier pipeline integration.
"""
import pytest
from unittest.mock import MagicMock, patch

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.crawler.frontier import CrawlFrontier
from rankintel.models.schema import (
    EngineResult,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    SecurityEvidence,
    ImageSEOEvidence,
    AccessibilityEvidence,
    ContentEvidence,
    WordCountTier,
    CrawlConfig,
    SiteCrawlResult,
)


def test_evidence_collector_content_integration():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Integration Lab</title></head>
    <body>
        <main>
            <h1>ISO Testing Calibration Lab</h1>
            <p>Our ISO accredited laboratory certifies precision measurement instrumentation for aerospace systems.
            We maintain NIST traceable reference standards and primary frequency standards.</p>
        </main>
    </body>
    </html>
    """
    collector = EvidenceCollector()

    # Mock browser and seo engines to avoid live HTTP
    mock_browser_res = EngineResult(
        engine_name="browser_engine",
        status="success",
        raw_html=sample_html,
        on_page=OnPageEvidence(url="https://example.com", title="Integration Lab", h1_text=["ISO Testing Calibration Lab"]),
    )
    mock_seo_res = EngineResult(
        engine_name="advertools_seo",
        status="success",
        on_page=OnPageEvidence(url="https://example.com", title="Integration Lab", h1_text=["ISO Testing Calibration Lab"]),
    )

    with patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser_res), \
         patch.object(collector.seo_engine, "execute", return_value=mock_seo_res), \
         patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
         patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="skipped")):
        
        results = collector.collect("https://example.com")

    assert "content_engine" in results
    content_res = results["content_engine"]
    assert content_res.status == "success"
    assert content_res.content is not None
    assert content_res.content.main_content_word_count > 15
    assert content_res.content.exact_content_hash != ""
    assert content_res.content.simhash != ""


def test_intelligence_synthesizer_content_and_formula_invariance():
    html = """
    <html>
    <head><title>Enterprise SEO Platform</title></head>
    <body>
        <main>
            <h1>Enterprise SEO Platform</h1>
            <p>Comprehensive search engine intelligence and automated technical auditing across engines.</p>
        </main>
    </body>
    </html>
    """
    collector = EvidenceCollector()
    content_ev = collector.content_engine.evaluate(html, url="https://example.com")

    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(url="https://example.com", status_code=200, title="Enterprise SEO Platform", h1_text=["Enterprise SEO Platform"]),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(overall_citability_score=75),
        ),
        "content_engine": EngineResult(
            engine_name="content_engine",
            status="success",
            content=content_ev,
        ),
    }

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", engine_results)

    # 1. Unified content attached
    assert report.unified_content is not None
    assert report.unified_content.main_content_word_count > 5
    assert report.unified_content.exact_content_hash != ""

    # 2. Formula Invariance: 3-engine formula remains intact
    assert report.score_formula_mode == "3_engine"
    assert report.overall_health_score > 0


def test_conflict_detector_client_rendered_content():
    # Static saw 10 words, browser saw 400 words
    html_rendered = "<html><body><main><h1>App</h1><p>" + " ".join(["editorial"] * 350) + "</p></main></body></html>"
    collector = EvidenceCollector()
    content_ev = collector.content_engine.evaluate(html_rendered, url="https://example.com/app")

    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(url="https://example.com/app", status_code=200, word_count=15),
        ),
        "content_engine": EngineResult(
            engine_name="content_engine",
            status="success",
            content=content_ev,
        ),
    }

    detector = ConflictDetector()
    conflicts = detector.detect(engine_results)

    content_conflicts = [c for c in conflicts if c.category == "CLIENT_RENDERED_CONTENT"]
    assert len(content_conflicts) == 1
    assert "JavaScript-Rendered Main Content" in content_conflicts[0].feature
    assert content_conflicts[0].severity == "HIGH"


def test_provenance_tagger_content_tags():
    html = "<html><body><main><h1>Verified Testing</h1><p>Precise content verification.</p></main></body></html>"
    collector = EvidenceCollector()
    content_ev = collector.content_engine.evaluate(html, url="https://example.com/test")

    engine_results = {
        "content_engine": EngineResult(
            engine_name="content_engine",
            status="success",
            content=content_ev,
        )
    }

    tags = ProvenanceTagger.tag(engine_results)
    content_tags = [t for t in tags if t.engine == "content_engine"]
    assert len(content_tags) >= 1
    assert any("Main Content Extraction" in t.finding for t in content_tags)


def test_markdown_and_json_reporters_render_content_sections():
    html = """
    <html>
    <head><title>Acoustics Calibration</title></head>
    <body>
        <main>
            <h1>Acoustics Calibration Facility</h1>
            <p>Our sound measurement lab conducts reverberation testing and microphone frequency response checks.</p>
            <h2>Anechoic Chamber Specs</h2>
            <p>Background noise levels remain below 15 dB(A) for precision sound power measurements.</p>
        </main>
    </body>
    </html>
    """
    collector = EvidenceCollector()
    content_ev = collector.content_engine.evaluate(html, url="https://example.com/acoustics")

    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(url="https://example.com/acoustics", status_code=200, title="Acoustics Calibration", h1_text=["Acoustics Calibration Facility"]),
            robots=RobotsEvidence(found=True),
        ),
        "content_engine": EngineResult(
            engine_name="content_engine",
            status="success",
            content=content_ev,
        ),
    }

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com/acoustics", engine_results)

    # 1. Render Markdown
    md_output = MarkdownReporter.render(report)
    assert "## 📑 CONTENT INTELLIGENCE & STRUCTURE" in md_output
    assert "Main Editorial Content:" in md_output
    assert "Exact Main-Content SHA-256:" in md_output
    assert "Deterministic SimHash (64-bit):" in md_output
    assert "Title ↔ H1 ↔ Content Relationship" in md_output
    assert "Heading Hierarchy & Content Outline" in md_output

    # 2. Render JSON
    json_output = JsonReporter.render_audit(report)
    assert "exact_content_hash" in json_output
    assert "simhash" in json_output
    assert "main_content_word_count" in json_output


def test_crawl_frontier_build_result_runs_content_analyzer():
    frontier = CrawlFrontier(base_url="https://example.com", config=CrawlConfig(max_pages=5))
    html_a = "<html><body><main><h1>Product Title</h1><p>Shared product description for duplicate test.</p></main></body></html>"
    html_b = "<html><body><main><h1>Product Title</h1><p>Shared product description for duplicate test.</p></main></body></html>"

    frontier.add_url("https://example.com/a", depth=0, parent_url=None)
    frontier.add_url("https://example.com/b", depth=1, parent_url="https://example.com/a")
    frontier.mark_fetched("https://example.com/a", 200, "text/html", 100, 0.1, [], raw_html=html_a)
    frontier.mark_fetched("https://example.com/b", 200, "text/html", 100, 0.1, [], raw_html=html_b)

    crawl_res = frontier.build_result(0.5)

    assert crawl_res.content_intelligence is not None
    ci = crawl_res.content_intelligence
    assert ci.total_pages_evaluated == 2
    assert ci.exact_duplicate_clusters_count == 1
    assert len(ci.exact_duplicate_clusters[0].urls) == 2
