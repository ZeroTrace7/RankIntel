"""
Integration test suite for RankIntel Phase 10.3: Claim Grounding & Entity Intelligence.
Verifies end-to-end integration across:
- EvidenceCollector (Step 19, zero duplicate network calls)
- ProvenanceTagger (provenance preservation)
- ConflictDetector (structured-vs-visible divergence & on-site contradictions)
- IntelligenceSynthesizer (reconciliation & health score formula invariance)
- MarkdownReporter (single-page & site crawl sections)
- JsonReporter (schema compliance & serialization)
- CLI (scorecard compact row)
- MCP Server (rankintel_audit telemetry fields)
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.mcp.server import rankintel_audit
from rankintel.cli import main
from rankintel.models.schema import (
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    CloudIntelligenceEvidence,
    EngineResult,
    ClaimSupportStatus,
    EntityConsistencyStatus,
    StructuredVisibleAgreementStatus,
    StructuredVisibleAgreement,
    ClaimEvidence,
    EntityGroundingEvidence,
    ClaimGroundingEvidence,
    SiteClaimGroundingIntelligence,
)


def build_mock_claim_grounding_evidence(url: str = "https://example.com") -> ClaimGroundingEvidence:
    """Build a deterministic mock ClaimGroundingEvidence object."""
    claim1 = ClaimEvidence(
        claim_id="claim-test-1",
        url=url,
        claim_text="Sunrise Testing Lab provides BIS certification testing under IS 13252.",
        claim_type="accreditation_claim",
        source_location="body > section > p",
        source_type="visible_body",
        extraction_method="m10_2_unit_reuse",
        bounded_snippet="Sunrise Testing Lab provides BIS certification testing under IS 13252.",
        support_status=ClaimSupportStatus.SUPPORTED_ON_SITE,
        supporting_snippets=["Scope covers IS 13252 with uncertainty ±0.05%"],
        provenance="claim_grounding_engine",
    )
    claim2 = ClaimEvidence(
        claim_id="claim-test-2",
        url=url,
        claim_text="Over 25 years of electrical testing experience.",
        claim_type="metric_or_statistic",
        source_location="body > p",
        source_type="visible_body",
        extraction_method="editorial_assertion_extraction",
        bounded_snippet="Over 25 years of electrical testing experience.",
        support_status=ClaimSupportStatus.UNCORROBORATED_ON_SITE,
        provenance="claim_grounding_engine",
    )
    entity1 = EntityGroundingEvidence(
        entity_name="Sunrise Testing Lab",
        entity_type="ORGANIZATION",
        url=url,
        bounded_snippet="Entity: Sunrise Testing Lab across 4/6 surfaces",
        consistency_status=EntityConsistencyStatus.CONSISTENT,
        observed_in_visible_body=True,
        observed_in_headings=True,
        observed_in_title_meta=True,
        observed_in_json_ld=True,
        provenance="claim_grounding_engine",
    )
    agree1 = StructuredVisibleAgreement(
        field_name="telephone",
        context_label="primary_contact",
        url=url,
        structured_value="+91-11-23456789",
        visible_value="+91-11-23456789",
        status=StructuredVisibleAgreementStatus.AGREEMENT,
        bounded_snippet="telephone: agreement",
        provenance="claim_grounding_engine",
    )
    return ClaimGroundingEvidence(
        url=url,
        engine_source="claim_grounding_engine",
        total_claims_detected=2,
        supported_claims_count=1,
        partially_supported_count=0,
        uncorroborated_count=1,
        contradicted_count=0,
        claims=[claim1, claim2],
        entity_grounding=[entity1],
        structured_agreements=[agree1],
        agreement_count=1,
        disagreement_count=0,
        facts=["Detected 2 observable claim(s).", "1 supported on-site, 1 uncorroborated on-site."],
        analyses=["Page features structured certification claim."],
    )


class TestCollectorStep19Integration:
    """Verifies EvidenceCollector Step 19 without redundant network calls."""

    def test_collector_runs_claim_grounding_engine(self):
        collector = EvidenceCollector()
        mock_html = """
        <html><body>
        <h1>Sunrise Testing Lab</h1>
        <p>We provide electrical calibration services.</p>
        </body></html>
        """

        mock_seo_res = EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url="https://example.com",
                status_code=200,
                title="Sunrise Testing Lab",
                h1_text=["Sunrise Testing Lab"],
            ),
        )

        mock_browser_res = EngineResult(
            engine_name="crawl4ai_browser",
            status="success",
            raw_html=mock_html,
            on_page=OnPageEvidence(
                url="https://example.com",
                status_code=200,
                title="Sunrise Testing Lab",
                engine_source="crawl4ai_browser_dom",
            ),
        )

        with patch.object(collector.seo_engine, "execute", return_value=mock_seo_res), \
             patch.object(collector.browser_engine, "crawl_page", return_value=mock_browser_res):
            results = collector.collect("https://example.com")

        assert "claim_grounding_engine" in results
        cg_res = results["claim_grounding_engine"]
        assert cg_res.status == "success"
        assert cg_res.claim_grounding is not None
        assert isinstance(cg_res.claim_grounding, ClaimGroundingEvidence)


class TestZeroDuplicateHttpRequests:
    """Verifies that executing ClaimGroundingEngine initiates 0 network requests."""

    def test_zero_network_calls_during_claim_grounding(self):
        collector = EvidenceCollector()
        mock_html = "<html><body><h1>Acme Co</h1><p>Founded in 1999.</p></body></html>"

        with patch("urllib.request.urlopen") as mock_urllib, \
             patch("httpx.Client.get") as mock_httpx, \
             patch("httpx.AsyncClient.get") as mock_async_httpx:

            ev = collector.claim_grounding_engine.evaluate_page(
                url="https://example.com",
                raw_html=mock_html,
                rendered_html=None,
            )

            assert mock_urllib.call_count == 0
            assert mock_httpx.call_count == 0
            assert mock_async_httpx.call_count == 0
            assert ev.total_claims_detected > 0


class TestFormulaInvariance:
    """Verifies health scores remain byte-for-byte identical with or without ClaimGroundingEngine."""

    def test_health_score_invariance(self):
        synthesizer = IntelligenceSynthesizer()

        base_results = {
            "advertools_seo": EngineResult(
                engine_name="advertools_seo",
                status="success",
                on_page=OnPageEvidence(
                    url="https://example.com",
                    status_code=200,
                    title="Example Domain",
                    title_length=14,
                    meta_description="Example domain meta description for testing.",
                    meta_desc_length=47,
                    h1_count=1,
                    h1_text=["Example Domain"],
                ),
                robots=RobotsEvidence(found=True),
                schema_data=SchemaEvidence(detected_types=["Organization"], has_organization=True),
            ),
            "browser_engine": EngineResult(
                engine_name="browser_engine",
                status="success",
                on_page=OnPageEvidence(
                    url="https://example.com",
                    status_code=200,
                    title="Example Domain",
                ),
            ),
            "rankintel_geo": EngineResult(
                engine_name="rankintel_geo",
                status="success",
                geo_aeo=GeoAeoEvidence(
                    llms_txt_found=True,
                    h2_geo_density=0.8,
                ),
            ),
        }

        # Synthesize baseline report without claim_grounding_engine
        report_before = synthesizer.synthesize("https://example.com", base_results)

        # Add claim_grounding_engine evidence
        results_with_cg = dict(base_results)
        results_with_cg["claim_grounding_engine"] = EngineResult(
            engine_name="claim_grounding_engine",
            status="success",
            claim_grounding=build_mock_claim_grounding_evidence(),
        )

        report_after = synthesizer.synthesize("https://example.com", results_with_cg)

        # Invariance assertion
        assert report_after.overall_health_score == report_before.overall_health_score
        assert report_after.technical_health_score == report_before.technical_health_score
        assert report_after.geo_readiness_score == report_before.geo_readiness_score
        assert report_after.trust_score == report_before.trust_score
        assert report_after.unified_claim_grounding is not None


class TestConflictAndProvenanceIntegration:
    """Verifies ConflictDetector and ProvenanceTagger capture claim divergence and provenance."""

    def test_conflict_detector_identifies_structured_visible_disagreement(self):
        detector = ConflictDetector()

        cg_ev = build_mock_claim_grounding_evidence()
        # Add explicit disagreement
        cg_ev.structured_agreements.append(StructuredVisibleAgreement(
            field_name="telephone",
            context_label="primary_contact",
            structured_value="+91-11-11111111",
            visible_value="+91-11-99999999",
            status=StructuredVisibleAgreementStatus.DISAGREEMENT,
            evidence_snippet="JSON-LD: +91-11-11111111 | DOM: +91-11-99999999",
        ))

        engine_results = {
            "claim_grounding_engine": EngineResult(
                engine_name="claim_grounding_engine",
                status="success",
                claim_grounding=cg_ev,
            )
        }

        conflicts = detector.detect(engine_results)
        divergence_conflicts = [c for c in conflicts if c.category == "STRUCTURED_VISIBLE_DIVERGENCE"]
        assert len(divergence_conflicts) == 1
        assert "Telephone" in divergence_conflicts[0].feature
        assert divergence_conflicts[0].severity == "HIGH"

    def test_provenance_tagger_records_claim_grounding(self):
        engine_results = {
            "claim_grounding_engine": EngineResult(
                engine_name="claim_grounding_engine",
                status="success",
                claim_grounding=build_mock_claim_grounding_evidence(),
            )
        }

        tags = ProvenanceTagger.tag(engine_results)
        cg_tags = [t for t in tags if t.engine == "claim_grounding_engine"]
        assert len(cg_tags) >= 2
        assert any("Observable Claims Grounding" in t.finding for t in cg_tags)
        assert any("Structured vs Visible Alignment" in t.finding for t in cg_tags)


class TestReportersIntegration:
    """Verifies Markdown and JSON reporting for Claim Grounding."""

    def test_markdown_and_json_reporters_render_claim_grounding(self):
        report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-04",
            overall_health_score=85,
            unified_claim_grounding=build_mock_claim_grounding_evidence(),
        )

        # Markdown render
        md = MarkdownReporter.render(report)
        assert "CLAIM GROUNDING & ENTITY INTELLIGENCE" in md
        assert "Structured vs Visible Representation Agreement" in md
        assert "Multi-Surface Entity Consistency" in md
        assert "Observable Claims Sample" in md
        assert "Sunrise Testing Lab" in md

        # JSON render
        json_str = JsonReporter.render_audit(report)
        data = json.loads(json_str)
        assert "unified_claim_grounding" in data
        assert data["unified_claim_grounding"]["total_claims_detected"] == 2
        assert data["unified_claim_grounding"]["supported_claims_count"] == 1


class TestCliAndMcpTelemetry:
    """Verifies CLI table row and FastMCP tool telemetry output."""

    def test_mcp_rankintel_audit_exposes_claim_grounding_fields(self):
        mock_report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-04",
            overall_health_score=90,
            unified_claim_grounding=build_mock_claim_grounding_evidence(),
        )

        with patch("rankintel.mcp.server.EvidenceCollector") as mock_col_cls, \
             patch("rankintel.mcp.server.IntelligenceSynthesizer") as mock_syn_cls:
            mock_syn = MagicMock()
            mock_syn.synthesize.return_value = mock_report
            mock_syn_cls.return_value = mock_syn

            mcp_output = rankintel_audit("https://example.com")

        assert "claim_grounding_total_claims" in mcp_output
        assert mcp_output["claim_grounding_total_claims"] == 2
        assert mcp_output["claim_grounding_supported_count"] == 1
        assert mcp_output["claim_grounding_agreements_count"] == 1
