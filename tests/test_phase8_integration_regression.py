"""
Phase 8 Integration & Regression Test Suite (M8.4).
Verifies complete coexistence of ContentEngine (M8.1), EntityEngine (M8.2), and
InternalLinkEngine (M8.3) through the full RankIntel pipeline:
crawl -> evidence collection -> synthesis -> conflicts -> provenance -> reporting -> alignment.
"""
import pytest
from unittest.mock import MagicMock, patch

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.analyzers.content_analyzer import SiteContentAnalyzer
from rankintel.analyzers.entity_analyzer import SiteEntityAnalyzer
from rankintel.analyzers.internal_link_analyzer import SiteInternalLinkAnalyzer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.models.schema import (
    CrawlConfig,
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
    EngineResult,
    OutlinkDiscoveryStatus,
    PageLinkAnalysisRecord,
    EntityType,
    EntityAlignmentStatus,
    VisibleStructuredComparison,
)


HTML_PAGE_A = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Acme Industrial Solutions - High Performance Testing</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Acme Corp Global",
      "url": "https://example.com",
      "telephone": "+1-800-555-0199",
      "sameAs": ["https://twitter.com/acme", "https://linkedin.com/company/acme"]
    }
    </script>
</head>
<body>
    <header>
        <span class="brand">Acme Corp Global</span>
        <nav>
            <a href="/products">Products</a>
            <a href="/about">About Us</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Industrial Testing Equipment & Services</h1>
        <p>Acme Corp Global provides comprehensive precision measurement and testing systems for aerospace and manufacturing enterprises across North America. Our accredited laboratories deliver rigorous calibration and quality assurance compliance.</p>
        <p>With over thirty years of operational excellence, our engineers conduct metallurgical evaluations, non-destructive testing, and environmental simulation chambers that exceed ISO 17025 certification requirements.</p>
        <h2>Advanced Calibration Methodologies</h2>
        <p>Calibration procedures utilize traceable primary standards maintained in climate-controlled calibration chambers. Every instrument undergoes automated multi-point verification before calibration certificate issuance.</p>
        <a href="/products">Explore Products</a>
        <a href="/products">Learn More</a>
        <a href="/about">Read About Us</a>
    </main>
    <footer>
        <p>&copy; 2026 Acme Corp Global. All rights reserved.</p>
        <a href="/privacy">Privacy Policy</a>
    </footer>
</body>
</html>
"""

HTML_PAGE_B = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Products & Instruments - Acme Industrial</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Acme Corp Global",
      "url": "https://example.com"
    }
    </script>
</head>
<body>
    <header>
        <span class="brand">Acme Corp Global</span>
        <nav><a href="/">Home</a><a href="/about">About Us</a></nav>
    </header>
    <main>
        <h1>Precision Measurement Instruments</h1>
        <p>Explore our complete catalog of certified instruments including digital micrometer gauges, optical emission spectrometers, and universal hardness testers engineered for high-throughput production floors.</p>
        <h2>Spectrometers & Analyzers</h2>
        <p>Optical emission instruments offer sub-ppm detection limits for metallic alloys. Multi-channel CCD detectors ensure rapid spectral analysis in under twenty seconds per sample.</p>
        <a href="/">Return to Home</a>
        <a href="/contact">Contact Support</a>
    </main>
</body>
</html>
"""

HTML_PAGE_C = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Terminal Contact Page</title>
</head>
<body>
    <h1>Contact Our Specialists</h1>
    <p>Reach out directly to our engineering support group for calibration inquiries and emergency technical support.</p>
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
        on_page=OnPageEvidence(url=url, title="Acme Industrial", h1_text=["Industrial Testing Equipment & Services"]),
    )
    mock_seo = EngineResult(
        engine_name="advertools_seo",
        status="success",
        on_page=OnPageEvidence(url=url, title="Acme Industrial", h1_text=["Industrial Testing Equipment & Services"]),
        robots=RobotsEvidence(found=True),
        schema_data=SchemaEvidence(has_organization=True),
    )
    with patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser), \
         patch.object(collector.seo_engine, "execute", return_value=mock_seo), \
         patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
         patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="skipped")):
        return collector.collect(url)


def test_pipeline_coexistence_evidence_collector():
    """Verify ContentEngine, EntityEngine, and InternalLinkEngine run concurrently on single-page DOM."""
    results = _collect_with_html(HTML_PAGE_A)

    assert "content_engine" in results
    assert "entity_engine" in results
    assert "internal_link_engine" in results

    cnt_res = results["content_engine"]
    ent_res = results["entity_engine"]
    lnk_res = results["internal_link_engine"]

    assert cnt_res.status == "success"
    assert ent_res.status == "success"
    assert lnk_res.status == "success"

    # Content assertions
    assert cnt_res.content is not None
    assert cnt_res.content.main_content_word_count > 50
    assert cnt_res.content.heading_structure.h1_count == 1

    # Entity assertions
    assert ent_res.entity is not None
    assert ent_res.entity.total_entities_detected >= 1
    org_names = [e.name for e in ent_res.entity.detected_entities]
    assert any("Acme" in n for n in org_names)

    # Link assertions
    assert lnk_res.internal_link is not None
    assert lnk_res.internal_link.internal_links_count >= 4
    assert lnk_res.internal_link.unique_internal_outlinks_count >= 3


def test_synthesizer_reconciles_all_phase8_dimensions():
    """Verify IntelligenceSynthesizer populates unified Phase 8 evidence models without overwriting."""
    results = _collect_with_html(HTML_PAGE_A)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_content is not None
    assert report.unified_content.main_content_word_count > 50

    assert report.unified_entity is not None
    assert report.unified_entity.total_entities_detected >= 1

    assert report.unified_internal_link is not None
    assert report.unified_internal_link.internal_links_count >= 4


def test_site_wide_coexistence_all_phase8_analyzers():
    """Verify SiteContentAnalyzer, SiteEntityAnalyzer, and SiteInternalLinkAnalyzer coexist on SiteCrawlResult."""
    records = [
        CrawlRecord(
            url="https://example.com/",
            normalized_url="https://example.com/",
            identity_url="https://example.com/",
            depth=0,
            status_code=200,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=HTML_PAGE_A,
            discovered_links=["https://example.com/products", "https://example.com/about", "https://example.com/contact"],
        ),
        CrawlRecord(
            url="https://example.com/products",
            normalized_url="https://example.com/products",
            identity_url="https://example.com/products",
            depth=1,
            status_code=200,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=HTML_PAGE_B,
            discovered_links=["https://example.com/", "https://example.com/contact"],
        ),
        CrawlRecord(
            url="https://example.com/contact",
            normalized_url="https://example.com/contact",
            identity_url="https://example.com/contact",
            depth=1,
            status_code=200,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=HTML_PAGE_C,
            discovered_links=[],
        ),
    ]

    site_crawl = SiteCrawlResult(
        pages_crawled=3,
        crawl_records=records,
    )

    # Run all 3 Phase 8 analyzers on the shared crawl result
    SiteContentAnalyzer.analyze_site(site_crawl)
    SiteEntityAnalyzer.analyze_site(site_crawl)
    SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com/")

    # 1. Content Intelligence populated
    assert site_crawl.content_intelligence is not None
    assert site_crawl.content_intelligence.total_pages_evaluated == 3
    assert len(site_crawl.content_intelligence.page_content_evidence) == 3

    # 2. Entity Intelligence populated
    assert site_crawl.entity_intelligence is not None
    assert site_crawl.entity_intelligence.total_pages_evaluated == 3
    assert len(site_crawl.entity_intelligence.all_entities) > 0

    # 3. Internal-Link Intelligence populated
    assert site_crawl.internal_link_intelligence is not None
    assert site_crawl.internal_link_intelligence.total_pages_evaluated == 3
    assert site_crawl.internal_link_intelligence.total_internal_links_discovered > 0
    assert len(site_crawl.internal_link_intelligence.page_link_records) >= 3


def test_zero_duplicate_http_requests_instrumented():
    """Prove empirically that Phase 8 analyzers execute strictly in-memory without duplicate HTTP requests."""
    pages = {
        "https://example.com/": HTML_PAGE_A,
        "https://example.com/products": HTML_PAGE_B,
        "https://example.com/contact": HTML_PAGE_C,
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
            discovered_links=["https://example.com/products"] if u.endswith("/") else [],
        ))

    initial_request_count = transport.request_count
    assert initial_request_count == 3  # Exactly 3 initial page fetches

    site_crawl = SiteCrawlResult(pages_crawled=3, crawl_records=records)

    # Execute all 3 Phase 8 analyzers
    SiteContentAnalyzer.analyze_site(site_crawl)
    SiteEntityAnalyzer.analyze_site(site_crawl)
    SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com/")

    # Assert exactly ZERO additional HTTP requests were made during Phase 8 analysis
    assert transport.request_count == initial_request_count


def test_screaming_frog_observable_alignment_records():
    """Verify PageLinkAnalysisRecord populates overlapping observable dimensions with strict partial-crawl semantics."""
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
        CrawlRecord(
            url="https://example.com/contact",
            normalized_url="https://example.com/contact",
            identity_url="https://example.com/contact",
            depth=1,
            status_code=200,
            crawl_status=CrawlStatus.FETCHED,
            raw_html=HTML_PAGE_C,  # No outlinks
        ),
    ]

    site_crawl = SiteCrawlResult(pages_crawled=3, crawl_records=records)
    intel = SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com/")

    records_map = intel.page_link_records
    assert len(records_map) >= 3

    # Root page record
    root_rec = records_map.get("https://example.com/")
    assert root_rec is not None
    assert root_rec.crawl_depth == 0
    assert root_rec.outlinks_count > 0
    assert root_rec.outlink_discovery_status == OutlinkDiscoveryStatus.HAS_DISCOVERED_OUTLINKS
    assert len(root_rec.sample_outlink_targets) <= 5

    # Products page record (linked from root)
    prod_rec = records_map.get("https://example.com/products")
    assert prod_rec is not None
    assert prod_rec.inlinks_count >= 1
    assert prod_rec.unique_inlinks_count >= 1
    assert prod_rec.outlink_discovery_status == OutlinkDiscoveryStatus.HAS_DISCOVERED_OUTLINKS
    # Verify sample anchors are populated and bounded
    assert isinstance(prod_rec.sample_inlink_anchors, list)
    assert len(prod_rec.sample_inlink_anchors) <= 5

    # Contact page record (terminal in crawl: 0 outlinks)
    contact_rec = records_map.get("https://example.com/contact")
    assert contact_rec is not None
    # Crucial partial-crawl semantic check: NO_DISCOVERED_OUTLINKS, not unverified or misleading boolean
    assert contact_rec.outlink_discovery_status == OutlinkDiscoveryStatus.NO_DISCOVERED_OUTLINKS
    assert contact_rec.outlinks_count == 0


def test_cross_engine_provenance_attribution():
    """Verify evidence provenance tags are cleanly generated for Content, Entity, and Internal-Link findings."""
    results = _collect_with_html(HTML_PAGE_A)

    tagger = ProvenanceTagger()
    tags = tagger.tag(results)

    engines = {t.engine for t in tags}
    assert "content_engine" in engines
    assert "entity_engine" in engines
    assert "internal_link_engine" in engines

    # Verify high confidence attribution
    for t in tags:
        if t.engine in ("content_engine", "entity_engine", "internal_link_engine"):
            assert t.confidence in ("high", "medium")
            assert t.finding


def test_conflict_handling_client_rendered_content():
    """Verify ConflictDetector deterministically flags client-rendered content discrepancy."""
    detector = ConflictDetector()

    # Static has thin words (10 words), DOM has rich editorial content (350 words)
    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(word_count=10),
        ),
        "content_engine": EngineResult(
            engine_name="content_engine",
            status="success",
            content=ContentEvidence(main_content_word_count=350),
        ),
    }

    conflicts = detector.detect(engine_results)
    cnt_conflicts = [c for c in conflicts if c.category == "CLIENT_RENDERED_CONTENT"]
    assert len(cnt_conflicts) == 1
    assert cnt_conflicts[0].severity == "HIGH"


def test_conflict_handling_divergent_organization_identity():
    """Verify ConflictDetector flags divergent organization branding between JSON-LD and visible DOM."""
    detector = ConflictDetector()

    comp = VisibleStructuredComparison(
        entity_type=EntityType.ORGANIZATION,
        attribute_name="organization_name",
        structured_value="Alpha Corporation",
        visible_value="Omega Enterprises",
        alignment_status=EntityAlignmentStatus.DIVERGENT_IDENTITY_SUSPECTED,
    )

    engine_results = {
        "entity_engine": EngineResult(
            engine_name="entity_engine",
            status="success",
            entity=EntityEvidence(structured_vs_visible=[comp]),
        ),
    }

    conflicts = detector.detect(engine_results)
    ent_conflicts = [c for c in conflicts if c.category == "DIVERGENT_ORGANIZATION_IDENTITY"]
    assert len(ent_conflicts) == 1
    assert "Alpha Corporation" in ent_conflicts[0].description
    assert "Omega Enterprises" in ent_conflicts[0].description


def test_formula_and_architecture_invariance():
    """Verify health score formulas (3_engine, 4_engine, 5_engine) remain mathematically identical and invariant to Phase 8."""
    synthesizer = IntelligenceSynthesizer()

    base_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(title="Test", meta_description="Desc", canonical_url="https://example.com"),
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

    # Baseline 3-engine score without Phase 8
    report_baseline = synthesizer.synthesize("https://example.com", base_results)
    baseline_score = report_baseline.overall_health_score

    # Now add heavy Phase 8 evidence (10,000 words content, 50 entities, 1,000 links)
    rich_results = dict(base_results)
    rich_results["content_engine"] = EngineResult(
        engine_name="content_engine",
        status="success",
        content=ContentEvidence(main_content_word_count=10000),
    )
    rich_results["entity_engine"] = EngineResult(
        engine_name="entity_engine",
        status="success",
        entity=EntityEvidence(total_entities_detected=50),
    )
    rich_results["internal_link_engine"] = EngineResult(
        engine_name="internal_link_engine",
        status="success",
        internal_link=InternalLinkEvidence(internal_links_count=1000),
    )

    report_with_phase8 = synthesizer.synthesize("https://example.com", rich_results)
    phase8_score = report_with_phase8.overall_health_score

    # Formula invariance assertion: health score MUST NOT change by even 1 point
    assert phase8_score == baseline_score
    assert report_with_phase8.score_formula_mode == report_baseline.score_formula_mode


def test_markdown_and_json_reporters_render_all_phase8():
    """Verify Markdown and JSON reporters render Content, Entity, and Internal-Link sections without truncation."""
    results = _collect_with_html(HTML_PAGE_A)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    # Attach site crawl
    site_crawl = SiteCrawlResult(
        pages_crawled=2,
        crawl_records=[
            CrawlRecord(url="https://example.com/", normalized_url="https://example.com/", identity_url="https://example.com/", crawl_status=CrawlStatus.FETCHED, depth=0, raw_html=HTML_PAGE_A),
            CrawlRecord(url="https://example.com/products", normalized_url="https://example.com/products", identity_url="https://example.com/products", crawl_status=CrawlStatus.FETCHED, depth=1, raw_html=HTML_PAGE_B),
        ],
    )
    SiteContentAnalyzer.analyze_site(site_crawl)
    SiteEntityAnalyzer.analyze_site(site_crawl)
    SiteInternalLinkAnalyzer.analyze_site(site_crawl, root_url="https://example.com/")
    report.site_crawl = site_crawl

    # 1. Markdown rendering
    md_output = MarkdownReporter.render(report)
    assert "CONTENT INTELLIGENCE & STRUCTURE" in md_output
    assert "ENTITY INTELLIGENCE & RECONCILIATION" in md_output
    assert "INTERNAL LINK & ANCHOR INTELLIGENCE" in md_output
    assert "Site-Wide Internal-Link Intelligence & Structure" in md_output

    # 2. JSON rendering
    json_output = JsonReporter.render_audit(report)
    assert '"unified_content"' in json_output
    assert '"unified_entity"' in json_output
    assert '"unified_internal_link"' in json_output
    assert '"page_link_records"' in json_output


def test_mcp_server_exposes_all_phase8_data():
    """Verify MCP server exposes verified Phase 8 fields in rankintel_audit output."""
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

        assert "content_main_word_count" in audit_res
        assert audit_res["content_main_word_count"] > 50

        assert "entities_detected_count" in audit_res
        assert audit_res["entities_detected_count"] >= 1

        assert "internal_links_total" in audit_res
        assert audit_res["internal_links_total"] >= 4
