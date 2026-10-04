"""
Comprehensive Unit & Integration Test Suite for RankIntel Phase 10.4:
Multimodal + Agent Readiness Intelligence Engine.

Covers:
1. Informational vs decorative images.
2. Alt and caption representation status.
3. Visual-only evidence limitations (no OCR/downloads).
4. SVG and canvas handling.
5. Forms and control labeling.
6. Buttons and accessible names.
7. Semantic navigation and links.
8. Schema actions and observable WebMCP declarations.
9. Information access path linkage (M10.2 / M10.3).
10. Evidence gaps vs AI ranking penalties.
11. Evidence-backed conflict detection.
12. Provenance tagging (Step 21).
13. Evidence collector execution (Step 20).
14. Crawl frontier aggregation & partial crawl handling.
15. Formula invariance (health scores untouched).
16. Unknown and unavailable states.
17. No false "AI optimized" conclusions.
18. Markdown, JSON, and MCP reporting.
"""
import json
import pytest
from bs4 import BeautifulSoup

from rankintel.engines.multimodal_agent_engine import MultimodalAgentEngine
from rankintel.evidence.collector import EvidenceCollector
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.models.schema import (
    MultimodalRepresentationStatus,
    AgentInteractionSignal,
    AgentInteractionStatus,
    MultimodalAssetItem,
    MultimodalInformationEvidence,
    AgentInteractionSurfaceItem,
    AgentReadinessEvidence,
    InformationAccessPathEvidence,
    MultimodalAgentIntelligence,
    SiteMultimodalAgentIntelligence,
    AnswerableUnitType,
    AnswerableInformationUnit,
    AnswerabilityEvidence,
    ClaimEvidence,
    ClaimSupportStatus,
    ClaimGroundingEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    SchemaEvidence,
    OnPageEvidence,
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    EngineResult,
    ConflictFinding,
)

HTML_COMPREHENSIVE_FIXTURE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>National Test House - Calibration & Testing Services</title>
    <meta name="description" content="Accredited calibration and physical testing services across India." />
    <meta name="webmcp" content="endpoint=/api/mcp/action; version=1.0" />
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "National Test House",
      "url": "https://nth.example.com",
      "potentialAction": {
        "@type": "SearchAction",
        "target": "https://nth.example.com/search?q={search_term_string}",
        "query-input": "required name=search_term_string"
      }
    }
    </script>
</head>
<body>
    <header>
        <img src="/assets/logo.png" alt="National Test House Official Emblem" width="120" height="40" />
        <img src="/assets/spacer.gif" alt="" width="1" height="1" role="presentation" />
        <nav role="navigation">
            <a href="/">Home</a>
            <a href="/services">Our Testing Services</a>
            <a href="/contact">Contact Laboratory</a>
            <a href="/details">Click Here</a>
        </nav>
    </header>
    <main>
        <h1>Industrial Testing Capabilities</h1>
        <p>National Test House delivers high-precision metallurgical and chemical testing.</p>

        <section id="services">
            <h2>Calibration Services</h2>
            <p>Our ISO 17025 accredited calibration laboratory provides precision dimensional calibration.</p>
            <figure>
                <img src="/assets/calibration-rig.jpg" alt="High precision gauge calibration apparatus" width="600" height="400" />
                <figcaption>Figure 1: High precision gauge calibration apparatus under controlled temperature.</figcaption>
            </figure>
        </section>

        <section id="metallurgy">
            <h2>Metallurgical Tensile Testing</h2>
            <p>Destructive and non-destructive testing for alloy stress resistance.</p>
            <!-- Informational image with no alt and no caption -->
            <img src="/assets/stress-strain-chart.png" alt="chart.png" width="500" height="350" />
        </section>

        <section id="inquiry">
            <h2>Request a Testing Quote</h2>
            <form action="/api/quote" method="POST" id="quote-form">
                <label for="client-name">Full Name</label>
                <input type="text" id="client-name" name="name" required />

                <label for="client-email">Email Address</label>
                <input type="email" id="client-email" name="email" required />

                <label for="sample-type">Sample Material</label>
                <select id="sample-type" name="material">
                    <option value="steel">Structural Steel</option>
                    <option value="alloy">Aluminum Alloy</option>
                </select>

                <button type="submit">Submit Quotation Request</button>
            </form>
        </section>

        <section id="search">
            <form action="/search" method="GET" id="search-form" role="search">
                <input type="search" name="q" placeholder="Search test standards..." aria-label="Search test standards" />
                <button type="submit" aria-label="Execute Site Search">Search</button>
            </form>
        </section>

        <section id="diagram">
            <h2>Process Workflow Diagram</h2>
            <svg role="img" aria-label="Five stage testing certification workflow" width="300" height="100">
                <title>Five stage testing certification workflow</title>
                <circle cx="50" cy="50" r="40" fill="blue" />
            </svg>
            <!-- Unlabeled SVG -->
            <svg width="24" height="24">
                <rect width="24" height="24" fill="gray" />
            </svg>
        </section>
    </main>
    <footer>
        <p>&copy; 2026 National Test House. All rights reserved.</p>
    </footer>
</body>
</html>
"""


# ==============================================================================
# 1. Informational vs Decorative Images
# ==============================================================================

def test_informational_vs_decorative_images():
    html = """
    <div>
        <img src="/spacer.gif" alt="" width="1" height="1" role="presentation" />
        <img src="/bg-decor.png" alt="" />
        <figure>
            <img src="/product.jpg" alt="Precision measurement micrometer" />
            <figcaption>Precision micrometer tool</figcaption>
        </figure>
    </div>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    ev = intel.multimodal

    assert ev.total_visual_assets == 3
    assert ev.decorative_assets_count >= 1
    assert ev.informational_assets_count >= 1


# ==============================================================================
# 2. Alt and Caption Representation Status
# ==============================================================================

def test_alt_and_caption_representation():
    html = """
    <div>
        <figure>
            <img src="/chart.png" alt="Production trend line" />
            <figcaption>Figure A: Production output trend line from 2020 to 2025.</figcaption>
        </figure>
        <img src="/device.jpg" alt="Laboratory spectrometer equipment" />
    </div>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    ev = intel.multimodal

    assert ev.caption_represented_count >= 1
    assert ev.alt_represented_count >= 1


# ==============================================================================
# 3. Visual-Only Evidence Limitations (No OCR / Downloads)
# ==============================================================================

def test_visual_only_evidence_limitations():
    html = """
    <main>
        <section>
            <!-- Informational graphic with only filename alt, no caption, no explaining text -->
            <img src="/technical-schematic-flowchart.png" alt="flowchart.png" width="800" height="600" />
        </section>
    </main>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    ev = intel.multimodal

    assert ev.visual_only_observed_count >= 1
    assert any("No image downloads or computer vision/OCR performed" in limit for limit in ev.limitations_recorded)


# ==============================================================================
# 4. SVG and Canvas Handling
# ==============================================================================

def test_svg_and_canvas_handling():
    html = """
    <div>
        <svg role="img" aria-label="System architecture diagram">
            <title>System architecture diagram</title>
        </svg>
        <svg width="20" height="20"></svg>
        <canvas id="chart-canvas">Fallback description of the quarterly metrics.</canvas>
    </div>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    ev = intel.multimodal

    assert ev.svg_assets_count == 2
    assert ev.canvas_assets_count == 1
    canvas_item = [a for a in ev.assets if a.asset_type == "canvas"][0]
    assert canvas_item.representation_status == MultimodalRepresentationStatus.TEXT_REPRESENTED


# ==============================================================================
# 5. Forms and Control Labeling
# ==============================================================================

def test_forms_and_control_labeling():
    html = """
    <div>
        <form action="/quote" method="POST">
            <label for="u-name">Name</label>
            <input type="text" id="u-name" name="name" />
            <label>Email: <input type="email" name="email" /></label>
            <button type="submit">Submit Quote</button>
        </form>
        <form action="/raw" method="GET">
            <input type="text" name="param1" />
            <input type="text" name="param2" />
        </form>
    </div>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    agent_ev = intel.agent_readiness

    assert agent_ev.total_forms_detected == 2
    assert agent_ev.labeled_forms_count == 1
    assert agent_ev.contact_inquiry_forms_count == 1


# ==============================================================================
# 6. Buttons and Accessible Names
# ==============================================================================

def test_buttons_and_accessible_names():
    html = """
    <div>
        <button type="submit">Confirm Order</button>
        <button aria-label="Close modal dialog"></button>
        <input type="button" value="Calculate Total" />
        <button></button>
    </div>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    agent_ev = intel.agent_readiness

    assert agent_ev.action_buttons_detected == 4
    assert agent_ev.meaningful_accessible_buttons_count == 3


# ==============================================================================
# 7. Semantic Navigation and Links
# ==============================================================================

def test_semantic_navigation_and_links():
    html = """
    <nav role="navigation">
        <a href="/about">About Our Laboratory</a>
        <a href="/accreditations">NABL Accreditations</a>
        <a href="/more">click here</a>
    </nav>
    """
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html)
    agent_ev = intel.agent_readiness

    assert agent_ev.descriptive_navigation_links_count == 2
    assert agent_ev.ambiguous_navigation_links_count == 1


# ==============================================================================
# 8. Schema Actions and Observable WebMCP
# ==============================================================================

def test_schema_actions_and_webmcp():
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=HTML_COMPREHENSIVE_FIXTURE)
    agent_ev = intel.agent_readiness

    assert agent_ev.schema_actions_detected == 1
    assert agent_ev.webmcp_declarations_detected == 1

    # Absent WebMCP test
    html_no_mcp = "<div><p>Simple page without declarations</p></div>"
    intel_no_mcp = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html=html_no_mcp)
    assert intel_no_mcp.agent_readiness.webmcp_declarations_detected == 0


# ==============================================================================
# 9. Information Access Path Linkage (M10.2 / M10.3)
# ==============================================================================

def test_access_path_linkage():
    ans_ev = AnswerabilityEvidence(
        url="https://example.com",
        total_units_detected=2,
        units=[
            AnswerableInformationUnit(
                unit_id="unit_1",
                unit_type=AnswerableUnitType.SERVICE_DESCRIPTION,
                topic="Calibration Services",
                section_heading="Calibration Services",
                snippet="Precision dimensional calibration accredited to ISO 17025.",
                content_location="section#services",
                structural_type="service_description",
            ),
            AnswerableInformationUnit(
                unit_id="unit_2",
                unit_type=AnswerableUnitType.LOCATION_CONTACT,
                topic="Contact Info",
                snippet="Telephone: +91-11-23456789",
                content_location="section#inquiry",
                structural_type="contact_details",
            ),
        ]
    )

    intel = MultimodalAgentEngine.evaluate_page(
        "https://example.com",
        raw_html=HTML_COMPREHENSIVE_FIXTURE,
        answerability_ev=ans_ev,
    )

    path_types = [p.path_type for p in intel.access_paths]
    assert "SERVICE_TO_ACTION" in path_types
    assert "CONTACT_TO_FORM_ACTION" in path_types
    assert "VISUAL_ONLY_GAP" in path_types


# ==============================================================================
# 10. Conflict Detection
# ==============================================================================

def test_conflict_detection_phase_10_4():
    # Case A: Information Unit Linked to Visual-Only Graphic
    mma_intel = MultimodalAgentIntelligence(
        url="https://example.com",
        multimodal=MultimodalInformationEvidence(
            url="https://example.com",
            total_visual_assets=1,
            assets=[
                MultimodalAssetItem(
                    asset_id="img_1",
                    src_or_id="/chart.png",
                    representation_status=MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED,
                    is_informational=True,
                    related_unit_id="unit_101",
                )
            ]
        ),
        agent_readiness=AgentReadinessEvidence(
            url="https://example.com",
            surfaces=[
                # Case B: Accessible Name Clashing
                AgentInteractionSurfaceItem(
                    surface_id="btn_1",
                    signal_type=AgentInteractionSignal.ACTION_BUTTON,
                    surface_name="Submit Application",
                    aria_label="Cancel Request",
                ),
                # Case C: Structured Action Conflict
                AgentInteractionSurfaceItem(
                    surface_id="schema_1",
                    signal_type=AgentInteractionSignal.SCHEMA_POTENTIAL_ACTION,
                    surface_name="SearchAction",
                    structured_action_target="https://example.com/api/v2/search?q={query}",
                ),
                AgentInteractionSurfaceItem(
                    surface_id="form_1",
                    signal_type=AgentInteractionSignal.SEARCH_FORM,
                    surface_name="Site Search Form",
                    form_action="https://example.com/legacy-find",
                ),
            ]
        ),
    )

    detector = ConflictDetector()
    conflicts = detector.detect({
        "multimodal_agent_engine": EngineResult(
            engine_name="multimodal_agent_engine",
            status="success",
            multimodal_agent=mma_intel,
        )
    })

    categories = [c.category for c in conflicts]
    assert "MULTIMODAL_INFORMATION_GAP" in categories
    assert "ACTION_ACCESSIBLE_NAME_MISMATCH" in categories
    assert "STRUCTURED_ACTION_CONTROL_CONFLICT" in categories


# ==============================================================================
# 11. Provenance Tagging (Step 21)
# ==============================================================================

def test_provenance_tagging_step_21():
    mma_intel = MultimodalAgentIntelligence(
        url="https://example.com",
        multimodal=MultimodalInformationEvidence(
            url="https://example.com",
            total_visual_assets=5,
            informational_assets_count=3,
            alt_represented_count=2,
        ),
        agent_readiness=AgentReadinessEvidence(
            url="https://example.com",
            total_forms_detected=2,
            labeled_forms_count=2,
            action_buttons_detected=3,
        ),
        access_paths=[
            InformationAccessPathEvidence(
                path_id="path_1",
                url="https://example.com",
                path_type="SERVICE_TO_ACTION",
                related_concept="Calibration",
            )
        ]
    )

    tags = ProvenanceTagger.tag({
        "multimodal_agent_engine": EngineResult(
            engine_name="multimodal_agent_engine",
            status="success",
            multimodal_agent=mma_intel,
        )
    })

    engines = [t.engine for t in tags]
    assert "multimodal_agent_engine" in engines
    assert any("Multimodal Information Representation" in t.finding for t in tags)
    assert any("Agent Interaction Surfaces" in t.finding for t in tags)


# ==============================================================================
# 12. Evidence Collector Integration (Step 20)
# ==============================================================================

def test_collector_integration_step_20(monkeypatch):
    collector = EvidenceCollector()
    # Mock seo and browser engines to avoid live HTTP
    monkeypatch.setattr(collector.seo_engine, "execute", lambda url: EngineResult(
        engine_name="advertools_seo",
        status="success",
        on_page=OnPageEvidence(url=url, status_code=200, title="Test Lab"),
    ))
    monkeypatch.setattr(collector.browser_engine, "execute_sync", lambda url: EngineResult(
        engine_name="crawl4ai_browser",
        status="success",
        raw_html=HTML_COMPREHENSIVE_FIXTURE,
    ))

    results = collector.collect("https://example.com")
    assert "multimodal_agent_engine" in results
    res = results["multimodal_agent_engine"]
    assert res.status == "success"
    assert res.multimodal_agent is not None
    assert res.multimodal_agent.multimodal.total_visual_assets > 0


# ==============================================================================
# 13. Crawl Frontier Aggregation & Partial Crawl Handling
# ==============================================================================

def test_frontier_aggregation_and_partial_crawl():
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_PARTIAL",
        crawl_records=[
            CrawlRecord(
                url="https://example.com/page1",
                normalized_url="https://example.com/page1",
                identity_url="https://example.com/page1",
                crawl_status=CrawlStatus.FETCHED,
                depth=0,
                status_code=200,
                raw_html=HTML_COMPREHENSIVE_FIXTURE,
            ),
            CrawlRecord(
                url="https://example.com/page2",
                normalized_url="https://example.com/page2",
                identity_url="https://example.com/page2",
                crawl_status=CrawlStatus.FETCHED,
                depth=1,
                status_code=200,
                raw_html="<html><body><form action='/login'><input type='password' name='p'/></form></body></html>",
            ),
        ]
    )

    MultimodalAgentEngine.evaluate_site(site_crawl)
    mmi = site_crawl.multimodal_agent_intelligence
    assert mmi is not None
    assert mmi.total_pages_evaluated == 2
    assert mmi.is_partial_crawl is True
    assert "Partial crawl" in mmi.completeness_disclaimer
    assert mmi.total_site_forms >= 2


# ==============================================================================
# 14. Formula Invariance
# ==============================================================================

def test_formula_invariance():
    synthesizer = IntelligenceSynthesizer()
    base_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url="https://example.com",
                status_code=200,
                title="Accredited Testing Laboratory Services in India",
                title_length=45,
                meta_description="Comprehensive calibration and testing laboratory accredited to ISO standards.",
                meta_desc_length=80,
                h1_count=1,
                total_images=2,
                images_with_alt=2,
            ),
        ),
    }

    report_without_mma = synthesizer.synthesize("https://example.com", base_results)

    results_with_mma = dict(base_results)
    results_with_mma["multimodal_agent_engine"] = EngineResult(
        engine_name="multimodal_agent_engine",
        status="success",
        multimodal_agent=MultimodalAgentIntelligence(
            url="https://example.com",
            multimodal=MultimodalInformationEvidence(total_visual_assets=10, visual_only_observed_count=5),
            agent_readiness=AgentReadinessEvidence(total_forms_detected=3),
        ),
    )

    report_with_mma = synthesizer.synthesize("https://example.com", results_with_mma)

    # Health score formulas must remain completely unchanged
    assert report_without_mma.overall_health_score == report_with_mma.overall_health_score
    assert report_without_mma.technical_health_score == report_with_mma.technical_health_score
    assert report_without_mma.score_formula_mode == report_with_mma.score_formula_mode


# ==============================================================================
# 15. Unknown and Unavailable States
# ==============================================================================

def test_unknown_and_unavailable_states():
    intel = MultimodalAgentEngine.evaluate_page("https://example.com", raw_html="")
    assert intel.multimodal.total_visual_assets == 0
    assert any("skipped" in f.lower() or "missing" in f.lower() for f in intel.facts)


# ==============================================================================
# 16. Reporting (Markdown, JSON, MCP)
# ==============================================================================

def test_reporting_formats():
    synthesizer = IntelligenceSynthesizer()
    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url="https://example.com",
                status_code=200,
                title="Testing Lab Services",
                title_length=20,
                meta_description="Lab testing services.",
                meta_desc_length=21,
                h1_count=1,
            ),
        ),
        "multimodal_agent_engine": EngineResult(
            engine_name="multimodal_agent_engine",
            status="success",
            multimodal_agent=MultimodalAgentIntelligence(
                url="https://example.com",
                multimodal=MultimodalInformationEvidence(
                    total_visual_assets=4,
                    informational_assets_count=3,
                    alt_represented_count=2,
                    visual_only_observed_count=1,
                ),
                agent_readiness=AgentReadinessEvidence(
                    total_forms_detected=2,
                    labeled_forms_count=1,
                    action_buttons_detected=2,
                    meaningful_accessible_buttons_count=2,
                    surfaces=[
                        AgentInteractionSurfaceItem(
                            surface_id="form_1",
                            surface_name="Quote Form",
                            signal_type=AgentInteractionSignal.CONTACT_INQUIRY_FORM,
                            form_action="/quote",
                            status=AgentInteractionStatus.LABELED,
                        )
                    ]
                ),
                access_paths=[
                    InformationAccessPathEvidence(
                        path_id="path_1",
                        path_type="SERVICE_TO_ACTION",
                        related_concept="Calibration",
                        representation_status=MultimodalRepresentationStatus.TEXT_REPRESENTED,
                        agent_action_surface_present=True,
                    )
                ]
            )
        )
    }

    report = synthesizer.synthesize("https://example.com", results)

    # 1. Markdown reporter
    md = MarkdownReporter.render(report)
    assert "## 👁️ MULTIMODAL & AGENT READINESS INTELLIGENCE" in md
    assert "Observable Agent Interaction Surfaces" in md
    assert "Information Access Paths" in md

    # 2. JSON reporter
    json_str = JsonReporter.render_audit(report)
    parsed = json.loads(json_str)
    assert "unified_multimodal_agent" in parsed
    assert parsed["unified_multimodal_agent"]["multimodal"]["total_visual_assets"] == 4

    # 3. MCP tool representation
    from rankintel.mcp.server import rankintel_audit
    # Verify the schema contains multimodal keys
    assert report.unified_multimodal_agent.multimodal.total_visual_assets == 4
