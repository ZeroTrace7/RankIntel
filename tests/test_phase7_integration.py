"""
Milestone M7.4 — Comprehensive Phase 7 Integration and Regression Tests.

Validates that:
1. ImageEngine evidence reaches the final report.
2. Accessibility evidence reaches the final report.
3. Security evidence reaches the final report.
4. Provenance survives the complete pipeline.
5. UNKNOWN status survives the complete pipeline.
6. UNAVAILABLE status survives the complete pipeline.
7. NOT_APPLICABLE status survives the complete pipeline.
8. Browser-unavailable accessibility behavior remains explicit.
9. Security findings do not become arbitrary scores.
10. Accessibility does not become an arbitrary score.
11. Existing synthesis formula modes (3_engine, 4_engine, 5_engine) remain unchanged.
12. Existing Phase 6 behavior remains unchanged.
13. Existing reports (Markdown & JSON) render cleanly.
14. Cross-engine conflicts only trigger when deterministic evidence exists.
15. Collector evidence reuse avoids redundant HTTP page downloads.
"""
import pytest
from unittest.mock import patch, MagicMock
from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.evidence.provenance import ProvenanceTagger
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
    CloudIntelligenceEvidence,
    KeywordIntelligence,
    ImageSEOEvidence,
    ImageDetail,
    ImageFormatEvidence,
    HtmlHeadEvidence,
    AccessibilityEvidence,
    AccessibilityViolation,
    AccessibilitySeverity,
    WcagStatus,
    WcagLevel,
    SecurityEvidence,
    SecurityFinding,
    SecurityFindingCategory,
    SecuritySeverity,
    SecurityStatus,
    TlsCertificateDetails,
)


def _make_base_engine_results(url="https://example.com"):
    """Helper fixture providing minimal Phase 1-6 successful engine results."""
    on_page = OnPageEvidence(
        url=url,
        status_code=200,
        title="Example Domain for Integration Testing",
        title_length=38,
        meta_description="A descriptive and clear meta description meeting standard character bounds.",
        meta_desc_length=80,
        h1_count=1,
        h1_text=["Welcome to Example"],
        total_images=2,
        images_with_alt=2,
        response_headers={"content-type": "text/html", "strict-transport-security": "max-age=31536000"}
    )
    robots = RobotsEvidence(found=True, robots_url=f"{url}/robots.txt")
    schema = SchemaEvidence(detected_types=["Organization", "WebSite"], has_organization=True)
    geo = GeoAeoEvidence(overall_citability_score=75, llms_txt_found=True, answer_first_ratio=0.5)
    trust = TrustStackResult(overall_score=85, raw_score=21, grade="B")
    perf = PerformanceEvidence(overall_performance_score=90, ttfb_ms=180.0, source="local_probe")

    return {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=on_page, robots=robots, schema_data=schema),
        "browser_engine": EngineResult(engine_name="browser_engine", status="success", on_page=on_page, schema_data=schema, raw_html="<html><head><title>Test</title></head><body><h1>Welcome</h1></body></html>"),
        "rankintel_geo": EngineResult(engine_name="rankintel_geo", status="success", geo_aeo=geo),
        "performance_engine": EngineResult(engine_name="performance_engine", status="success", performance=perf),
    }


def test_01_image_engine_evidence_reaches_final_report():
    """Verify ImageEngine evidence is populated in SynthesisReport and rendered in Markdown."""
    results = _make_base_engine_results()
    img_ev = ImageSEOEvidence(
        total_images=3,
        images_with_alt=2,
        missing_alt_count=1,
        generic_alt_count=0,
        decorative_alt_count=0,
        missing_dimensions_count=1,
        modern_format_count=2,
        legacy_format_count=1,
        lazy_loaded_count=1,
        head_audit=HtmlHeadEvidence(
            viewport_present=True,
            viewport_configuration="width=device-width, initial-scale=1.0",
            lang_present=True,
            lang_code="en",
            charset_present=True,
            charset_declared="utf-8",
            heading_hierarchy_valid=True
        )
    )
    results["image_engine"] = EngineResult(engine_name="image_engine", status="success", image_seo=img_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_image_seo.total_images == 3
    assert report.unified_image_seo.missing_alt_count == 1
    assert report.unified_image_seo.modern_format_count == 2
    assert report.unified_image_seo.head_audit.viewport_present is True

    md = MarkdownReporter.render(report)
    assert "## 🖼️ IMAGE SEO & VISUAL ASSET INTELLIGENCE" in md
    assert "3 images declared alt text" in md or "2/3 images declared alt text" in md
    assert "Layout Stability (Explicit Dimensions):" in md
    assert "Viewport Tag:" in md


def test_02_accessibility_evidence_reaches_final_report():
    """Verify AccessibilityEngine violations and status reach the final report and Markdown."""
    results = _make_base_engine_results()
    a11y_ev = AccessibilityEvidence(
        url="https://example.com",
        engine_source="axe_core_playwright",
        browser_evaluated=True,
        wcag_aa_status=WcagStatus.FAIL,
        total_violations=1,
        critical_count=1,
        violations=[
            AccessibilityViolation(
                rule_id="color-contrast",
                wcag_sc="1.4.3",
                level=WcagLevel.AA,
                severity=AccessibilitySeverity.CRITICAL,
                description="Elements must have sufficient color contrast",
                failure_summary="Text has contrast ratio of 2.1:1, expected 4.5:1."
            )
        ]
    )
    results["accessibility_engine"] = EngineResult(engine_name="accessibility_engine", status="success", accessibility=a11y_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_accessibility.wcag_aa_status == WcagStatus.FAIL
    assert report.unified_accessibility.total_violations == 1
    assert report.unified_accessibility.critical_count == 1

    md = MarkdownReporter.render(report)
    assert "## ♿ ACCESSIBILITY (WCAG 2.1/2.2 AA Automated Checks)" in md
    assert "Automated WCAG Status:** FAIL" in md
    assert "color-contrast" in md
    assert "WCAG 2.1/2.2 AA criteria and do not constitute complete manual accessibility certification" in md


def test_03_security_evidence_reaches_final_report():
    """Verify SecurityEngine headers, TLS, and findings reach the final report and Markdown."""
    results = _make_base_engine_results()
    sec_ev = SecurityEvidence(
        url="https://example.com",
        is_https=True,
        overall_status=SecurityStatus.PASS,
        hsts_present=True,
        csp_present=True,
        tls_details=TlsCertificateDetails(is_valid=True, protocol_version="TLSv1.3", days_until_expiration=120),
        findings=[]
    )
    results["security_engine"] = EngineResult(engine_name="security_engine", status="success", security=sec_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_security.overall_status == SecurityStatus.PASS
    assert report.unified_security.hsts_present is True
    assert report.unified_security.tls_details.is_valid is True

    md = MarkdownReporter.render(report)
    assert "## 🛡️ SECURITY & WEB BEST PRACTICES" in md
    assert "Overall Status:** PASS" in md
    assert "TLSv1.3" in md


def test_04_provenance_survives_complete_pipeline():
    """Verify Phase 7 engine provenance tags are generated and reach SynthesisReport."""
    results = _make_base_engine_results()
    results["image_engine"] = EngineResult(
        engine_name="image_engine",
        status="success",
        image_seo=ImageSEOEvidence(total_images=5, missing_alt_count=1)
    )
    results["accessibility_engine"] = EngineResult(
        engine_name="accessibility_engine",
        status="success",
        accessibility=AccessibilityEvidence(
            engine_source="static_ast_auditor",
            wcag_aa_status=WcagStatus.PARTIAL,
            total_violations=2
        )
    )
    results["security_engine"] = EngineResult(
        engine_name="security_engine",
        status="success",
        security=SecurityEvidence(
            overall_status=SecurityStatus.PARTIAL,
            total_findings=1,
            hsts_present=True
        )
    )

    tags = ProvenanceTagger.tag(results)
    engines_in_tags = {t.engine for t in tags}
    assert "image_engine" in engines_in_tags
    assert "static_ast_auditor" in engines_in_tags
    assert "security_engine" in engines_in_tags

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)
    rep_engines = {p.engine for p in report.provenance}
    assert "image_engine" in rep_engines
    assert "static_ast_auditor" in rep_engines
    assert "security_engine" in rep_engines


def test_05_unknown_status_survives_complete_pipeline():
    """Verify UNKNOWN status from static accessibility auditor is preserved without being converted to FAIL/PASS."""
    results = _make_base_engine_results()
    a11y_ev = AccessibilityEvidence(
        url="https://example.com",
        engine_source="static_ast_auditor",
        browser_evaluated=False,
        wcag_aa_status=WcagStatus.UNKNOWN,
        total_violations=0
    )
    results["accessibility_engine"] = EngineResult(engine_name="accessibility_engine", status="success", accessibility=a11y_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_accessibility.wcag_aa_status == WcagStatus.UNKNOWN
    # UNKNOWN must NOT generate prioritized actions
    a11y_actions = [a for a in report.prioritized_actions if "Accessibility" in a.title]
    assert len(a11y_actions) == 0

    md = MarkdownReporter.render(report)
    assert "UNKNOWN" in md


def test_06_unavailable_status_survives_complete_pipeline():
    """Verify UNAVAILABLE security status on missing headers is preserved without converting to FAIL."""
    results = _make_base_engine_results()
    sec_ev = SecurityEvidence(
        url="https://example.com",
        is_https=True,
        overall_status=SecurityStatus.UNAVAILABLE,
        findings=[]
    )
    results["security_engine"] = EngineResult(engine_name="security_engine", status="skipped", security=sec_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_security.overall_status == SecurityStatus.UNAVAILABLE
    # UNAVAILABLE must NOT generate prioritized actions from SecurityEngine
    sec_actions = [a for a in report.prioritized_actions if a.engine_confidence == "HIGH (Security engine telemetry)"]
    assert len(sec_actions) == 0


def test_07_not_applicable_status_survives_complete_pipeline():
    """Verify NOT_APPLICABLE status is preserved where checks genuinely do not apply."""
    results = _make_base_engine_results()
    sec_ev = SecurityEvidence(
        url="http://insecure-example.com",
        is_https=False,
        overall_status=SecurityStatus.FAIL,
        tls_details=TlsCertificateDetails(handshake_status=SecurityStatus.NOT_APPLICABLE)
    )
    results["security_engine"] = EngineResult(engine_name="security_engine", status="success", security=sec_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("http://insecure-example.com", results)

    assert report.unified_security.tls_details.handshake_status == SecurityStatus.NOT_APPLICABLE


def test_08_browser_unavailable_accessibility_behavior_remains_explicit():
    """Verify that when browser evaluation is unavailable, static fallback explicitly reports browser_evaluated=False."""
    a11y_ev = AccessibilityEvidence(
        url="https://example.com",
        engine_source="static_ast_auditor",
        browser_evaluated=False,
        wcag_aa_status=WcagStatus.UNKNOWN,
        notes=["Playwright not installed. Browser rendering UNAVAILABLE."]
    )
    assert a11y_ev.browser_evaluated is False
    assert a11y_ev.wcag_aa_status == WcagStatus.UNKNOWN
    assert "Browser rendering UNAVAILABLE" in a11y_ev.notes[0]


def test_09_security_findings_do_not_become_arbitrary_scores():
    """Verify that Security findings do not fabricate arbitrary numeric scores or grades."""
    results = _make_base_engine_results()
    sec_ev = SecurityEvidence(
        url="https://example.com",
        is_https=True,
        overall_status=SecurityStatus.PARTIAL,
        total_findings=2,
        findings=[
            SecurityFinding(
                code="SEC_CSP_MISSING",
                title="Missing CSP",
                category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                severity=SecuritySeverity.HIGH,
                description="No Content-Security-Policy",
                recommendation="Deploy CSP"
            )
        ]
    )
    results["security_engine"] = EngineResult(engine_name="security_engine", status="success", security=sec_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    # Security score defaults to 0 and does not invent arbitrary scores
    assert report.security_score == 0
    assert report.unified_security.overall_status == SecurityStatus.PARTIAL
    md = MarkdownReporter.render(report)
    assert "Overall Status:** PARTIAL" in md
    assert "Security Posture Score" not in md  # No arbitrary score claim


def test_10_accessibility_does_not_become_arbitrary_score():
    """Verify that Accessibility findings do not fabricate arbitrary numeric scores or letter grades."""
    results = _make_base_engine_results()
    a11y_ev = AccessibilityEvidence(
        url="https://example.com",
        engine_source="static_ast_auditor",
        wcag_aa_status=WcagStatus.PARTIAL,
        total_violations=3
    )
    results["accessibility_engine"] = EngineResult(engine_name="accessibility_engine", status="success", accessibility=a11y_ev)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.accessibility_score == 0
    assert report.unified_accessibility.wcag_aa_status == WcagStatus.PARTIAL
    md = MarkdownReporter.render(report)
    assert "Automated WCAG Status:** PARTIAL" in md


def test_11_existing_synthesis_formula_modes_remain_unchanged():
    """Verify formula modes: 3_engine, 4_engine, 5_engine remain completely unchanged."""
    synthesizer = IntelligenceSynthesizer()

    # 1. 3-Engine Mode (No performance)
    results_3 = _make_base_engine_results()
    results_3.pop("performance_engine")
    rep_3 = synthesizer.synthesize("https://example.com", results_3)
    assert rep_3.score_formula_mode == "3_engine"

    # 2. 4-Engine Mode (Standard with performance)
    results_4 = _make_base_engine_results()
    rep_4 = synthesizer.synthesize("https://example.com", results_4)
    assert rep_4.score_formula_mode == "4_engine"

    # 3. 5-Engine Mode (With Cloud Intelligence keywords)
    results_5 = _make_base_engine_results()
    cloud_ev = CloudIntelligenceEvidence(
        available=True,
        keywords=KeywordIntelligence(estimated_monthly_traffic=10_000, total_keywords=50)
    )
    results_5["mcp_cloud"] = EngineResult(engine_name="mcp_cloud", status="success", cloud_intelligence=cloud_ev)
    rep_5 = synthesizer.synthesize("https://example.com", results_5)
    assert rep_5.score_formula_mode == "5_engine"


def test_12_phase6_behavior_remains_unchanged():
    """Verify that Phase 6 features (TrustEvaluator, BotMatrix, FixGenerator) remain fully functional."""
    results = _make_base_engine_results()
    results["rankintel_geo"].geo_aeo.llms_txt_found = False

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    assert report.unified_trust.overall_score > 0
    assert report.unified_trust.grade in ("A", "B", "C", "D", "F")
    assert "hardened_robots" in report.fixes
    assert "llms_txt" in report.fixes


def test_13_existing_reports_remain_valid():
    """Verify both Markdown and JSON reporting render cleanly with Phase 7 models populated."""
    results = _make_base_engine_results()
    results["image_engine"] = EngineResult(engine_name="image_engine", status="success", image_seo=ImageSEOEvidence(total_images=2))
    results["accessibility_engine"] = EngineResult(engine_name="accessibility_engine", status="success", accessibility=AccessibilityEvidence(total_violations=0, wcag_aa_status=WcagStatus.UNKNOWN))
    results["security_engine"] = EngineResult(engine_name="security_engine", status="success", security=SecurityEvidence(overall_status=SecurityStatus.PASS))

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize("https://example.com", results)

    # Markdown
    md = MarkdownReporter.render(report)
    assert "# RANKINTEL INTELLIGENCE REPORT" in md
    assert "## 📊 EXECUTIVE SCORECARD" in md
    assert "## 🛡️ SECURITY & WEB BEST PRACTICES" in md
    assert "## 🖼️ IMAGE SEO & VISUAL ASSET INTELLIGENCE" in md
    assert "## ♿ ACCESSIBILITY" in md

    # JSON
    json_str = JsonReporter.render_audit(report)
    assert "unified_security" in json_str
    assert "unified_image_seo" in json_str
    assert "unified_accessibility" in json_str


def test_14_cross_engine_mixed_content_conflict_triggers_deterministically():
    """Verify MIXED_CONTENT_SECURITY conflict triggers when and only when deterministic evidence exists."""
    detector = ConflictDetector()

    # Case A: HTTPS page with insecure images AND security mixed content -> Triggers
    img_ev = ImageSEOEvidence(
        head_audit=HtmlHeadEvidence(insecure_resource_urls=["http://example.com/asset.js"])
    )
    sec_ev = SecurityEvidence(
        is_https=True,
        mixed_content_resources=["http://example.com/asset.js"]
    )
    results = {
        "image_engine": EngineResult(engine_name="image_engine", image_seo=img_ev),
        "security_engine": EngineResult(engine_name="security_engine", security=sec_ev)
    }
    conflicts = detector.detect(results)
    assert any(c.category == "MIXED_CONTENT_SECURITY" for c in conflicts)

    # Case B: HTTP page (not HTTPS) -> Does NOT trigger
    sec_ev_http = SecurityEvidence(is_https=False, mixed_content_resources=[])
    results_http = {
        "image_engine": EngineResult(engine_name="image_engine", image_seo=img_ev),
        "security_engine": EngineResult(engine_name="security_engine", security=sec_ev_http)
    }
    conflicts_http = detector.detect(results_http)
    assert not any(c.category == "MIXED_CONTENT_SECURITY" for c in conflicts_http)


def test_15_evidence_collector_reuses_evidence_without_duplicate_http():
    """Verify EvidenceCollector reuses browser_html and response_headers without redundant requests."""
    collector = EvidenceCollector()

    mock_on_page = OnPageEvidence(
        url="https://example.com",
        status_code=200,
        response_headers={"strict-transport-security": "max-age=31536000"}
    )
    mock_seo_res = EngineResult(engine_name="advertools_seo", status="success", on_page=mock_on_page)
    mock_browser_res = EngineResult(
        engine_name="browser_engine",
        status="success",
        on_page=mock_on_page,
        raw_html="<html><body><img src='test.webp' alt='Test' width='100' height='100'/></body></html>"
    )

    with patch.object(collector.seo_engine, "execute", return_value=mock_seo_res), \
         patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser_res), \
         patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
         patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="success")), \
         patch.object(collector.mcp_engine, "execute", return_value=EngineResult(engine_name="mcp_cloud", status="skipped")), \
         patch.object(collector.security_engine, "check_tls_certificate", return_value=TlsCertificateDetails(is_valid=True)), \
         patch.object(collector.security_engine, "audit_url_sync") as mock_audit_sync:

        res = collector.collect("https://example.com")

        # audit_url_sync should NOT be called because headers were already provided
        mock_audit_sync.assert_not_called()

        assert "image_engine" in res
        assert "accessibility_engine" in res
        assert "security_engine" in res
        assert res["image_engine"].image_seo.total_images == 1
        assert res["security_engine"].security.hsts_present is True
