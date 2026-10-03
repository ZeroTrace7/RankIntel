"""
Integration tests for Phase 8.3 Internal-Link Intelligence pipeline.
Tests EvidenceCollector -> IntelligenceSynthesizer -> Reporters -> SiteCrawlResult.
Offline execution — zero live HTTP requests.
"""
import pytest
from unittest.mock import patch, MagicMock

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.models.schema import (
    EngineResult,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    InternalLinkEvidence,
    EvidenceNature,
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
)
from rankintel.analyzers.internal_link_analyzer import SiteInternalLinkAnalyzer


def test_collector_runs_internal_link_engine():
    """EvidenceCollector invokes InternalLinkEngine and records EngineResult."""
    collector = EvidenceCollector()

    mock_browser_res = EngineResult(
        engine_name="browser_engine",
        status="success",
        raw_html="""
        <html><body>
            <a href="/about">About Us</a>
            <a href="/contact">Contact</a>
            <a href="/sub"></a>
            <a href="https://external.com">External</a>
        </body></html>
        """,
        on_page=OnPageEvidence(url="https://example.com", title="Test Page", status_code=200),
    )

    with patch.object(collector.seo_engine, "execute", return_value=EngineResult(engine_name="advertools_seo", status="success")), \
         patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser_res), \
         patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
         patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="success")), \
         patch.object(collector.mcp_engine, "execute", return_value=EngineResult(engine_name="mcp_cloud", status="skipped")):

        results = collector.collect("https://example.com")

    assert "internal_link_engine" in results
    lnk_res = results["internal_link_engine"]
    assert lnk_res.status == "success"
    assert lnk_res.internal_link is not None
    assert lnk_res.internal_link.internal_links_count == 3
    assert lnk_res.internal_link.external_links_count == 1
    assert lnk_res.internal_link.empty_anchor_count == 1


def test_synthesizer_reconciles_internal_link_evidence():
    """Synthesizer reconciles unified_internal_link and creates evidence-gated prioritized actions."""
    synthesizer = IntelligenceSynthesizer()

    link_evidence = InternalLinkEvidence(
        url="https://example.com",
        status=EvidenceNature.OBSERVED,
        total_links_found=15,
        internal_links_count=10,
        external_links_count=5,
        empty_anchor_count=2,
        generic_anchor_count=6,
        facts=["Observed 10 internal links."],
    )

    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(url="https://example.com", title="Example Domain Title Test", title_length=25, status_code=200),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["WebSite"]),
        ),
        "internal_link_engine": EngineResult(
            engine_name="internal_link_engine",
            status="success",
            internal_link=link_evidence,
        ),
    }

    report = synthesizer.synthesize("https://example.com", engine_results)

    assert report.unified_internal_link.internal_links_count == 10
    assert report.unified_internal_link.empty_anchor_count == 2
    assert report.unified_internal_link.generic_anchor_count == 6

    # Verify prioritized action was generated for empty anchors
    action_titles = [a.title for a in report.prioritized_actions]
    assert "Descriptive Anchor Text Opportunity" in action_titles

    # Verify provenance tag was generated
    provenance_engines = [p.engine for p in report.provenance]
    assert "internal_link_engine" in provenance_engines


def test_markdown_and_json_reporters_render_internal_links():
    """MarkdownReporter and JsonReporter properly serialize internal-link intelligence."""
    synthesizer = IntelligenceSynthesizer()

    link_evidence = InternalLinkEvidence(
        url="https://example.com",
        status=EvidenceNature.OBSERVED,
        total_links_found=5,
        internal_links_count=4,
        external_links_count=1,
        unique_internal_outlinks_count=3,
        facts=["Observed 4 internal links."],
    )

    report = synthesizer.synthesize("https://example.com", {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=OnPageEvidence(url="https://example.com", title="Title", status_code=200)),
        "internal_link_engine": EngineResult(engine_name="internal_link_engine", status="success", internal_link=link_evidence),
    })

    # Add a mock site crawl with internal link intelligence
    report.site_crawl = SiteCrawlResult(
        crawl_records=[
            CrawlRecord(
                url="https://example.com",
                normalized_url="https://example.com",
                identity_url="https://example.com",
                crawl_status=CrawlStatus.FETCHED,
                depth=0,
                status_code=200,
                raw_html='<a href="/p1">Page 1</a>',
            ),
            CrawlRecord(
                url="https://example.com/p1",
                normalized_url="https://example.com/p1",
                identity_url="https://example.com/p1",
                crawl_status=CrawlStatus.FETCHED,
                depth=1,
                status_code=200,
                raw_html='<a href="/">Home</a>',
            ),
        ]
    )
    SiteInternalLinkAnalyzer.analyze_site(report.site_crawl, root_url="https://example.com")

    # Render Markdown
    md_content = MarkdownReporter.render(report)
    assert "## 🔗 INTERNAL LINK & ANCHOR INTELLIGENCE" in md_content
    assert "### 🔗 Site-Wide Internal-Link Intelligence & Structure" in md_content
    assert "Internal Hyperlinks Discovered" in md_content

    # Render JSON
    json_str = JsonReporter.render_audit(report)
    assert '"unified_internal_link"' in json_str
    assert '"internal_link_intelligence"' in json_str
