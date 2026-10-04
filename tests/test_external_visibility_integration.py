"""
Integration Tests for Controlled External AI Visibility (Phase 10.5).
"""
import json
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
    ExternalVisibilityStatus,
    CrawlConfig,
    SiteCrawlResult,
)
from rankintel.crawler.frontier import CrawlFrontier


def create_mock_engine_results():
    """Helper creating standard base engine results for score invariance testing."""
    return {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url="https://sunrisetesting.vercel.app",
                title="Sunrise Testing Laboratory - BIS Testing & NABL Services",
                title_length=56,
                meta_description="Premier laboratory for BIS, RoHS, and electrical testing in Delhi NCR.",
                meta_desc_length=68,
                h1_count=1,
                h1_text=["Sunrise Testing Laboratory"],
                total_images=5,
                images_with_alt=5,
                word_count=450,
            ),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["LocalBusiness", "Organization"]),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(
                overall_citability_score=75,
                llms_txt_found=True,
                answer_first_ratio=0.8,
            ),
        ),
        "performance_engine": EngineResult(
            engine_name="performance_engine",
            status="success",
            performance=PerformanceEvidence(
                source="local_probe",
                overall_performance_score=85,
                ttfb_ms=250.0,
            ),
        ),
    }


class TestExternalVisibilityIntegration:
    """Verifies complete end-to-end integration and score invariance."""

    def test_default_audit_disabled_without_opt_in(self):
        collector = EvidenceCollector(enable_external_visibility=False)
        assert collector.external_visibility_engine.enabled is False

        with patch.object(collector.seo_engine, "execute") as mock_seo, \
             patch.object(collector.browser_engine, "execute_sync") as mock_browser, \
             patch.object(collector.performance_engine, "execute") as mock_perf, \
             patch.object(collector.mcp_engine, "execute") as mock_mcp:

            mock_seo.return_value = EngineResult(engine_name="advertools_seo", status="success")
            mock_browser.return_value = EngineResult(engine_name="browser_engine", status="success")
            mock_perf.return_value = EngineResult(engine_name="performance_engine", status="success")
            mock_mcp.return_value = EngineResult(engine_name="mcp_cloud", status="skipped")

            results = collector.collect("https://sunrisetesting.vercel.app")
            assert "external_visibility_engine" in results
            ext_res = results["external_visibility_engine"]
            assert ext_res.status == "skipped"
            assert ext_res.external_visibility.status == ExternalVisibilityStatus.DISABLED

    def test_health_score_invariance(self):
        """
        CRITICAL TEST: Ensures Phase 10.5 NEVER alters existing health-score formulas.
        The score must be 100% identical with and without external AI enabled.
        """
        synthesizer = IntelligenceSynthesizer()

        # Baseline run without external AI
        base_results = create_mock_engine_results()
        base_report = synthesizer.synthesize("https://sunrisetesting.vercel.app", base_results)

        # Run with external AI enabled and successful observations
        ext_results = create_mock_engine_results()
        collector = EvidenceCollector(enable_external_visibility=True, external_providers=["mock"])
        ext_engine_res = collector.external_visibility_engine.evaluate_page("https://sunrisetesting.vercel.app")
        ext_results["external_visibility_engine"] = EngineResult(
            engine_name="external_visibility_engine",
            status="success",
            external_visibility=ext_engine_res,
        )

        ext_report = synthesizer.synthesize("https://sunrisetesting.vercel.app", ext_results)

        # STRICT INVARIANCE ASSERTIONS
        assert ext_report.overall_health_score == base_report.overall_health_score
        assert ext_report.technical_health_score == base_report.technical_health_score
        assert ext_report.geo_readiness_score == base_report.geo_readiness_score
        assert ext_report.trust_score == base_report.trust_score
        assert ext_report.performance_score == base_report.performance_score
        assert ext_report.score_formula_mode == base_report.score_formula_mode

        # Verify unified_external_visibility was attached
        assert ext_report.unified_external_visibility is not None
        assert ext_report.unified_external_visibility.status == ExternalVisibilityStatus.SUCCESS
        assert ext_report.unified_external_visibility.successful_observations_count > 0

    def test_markdown_and_json_reporters(self):
        synthesizer = IntelligenceSynthesizer()
        results = create_mock_engine_results()
        collector = EvidenceCollector(enable_external_visibility=True, external_providers=["mock"])
        ext_engine_res = collector.external_visibility_engine.evaluate_page("https://sunrisetesting.vercel.app")
        results["external_visibility_engine"] = EngineResult(
            engine_name="external_visibility_engine",
            status="success",
            external_visibility=ext_engine_res,
        )

        report = synthesizer.synthesize("https://sunrisetesting.vercel.app", results)

        # Markdown check
        md_text = MarkdownReporter.render(report)
        assert "## 🌐 CONTROLLED EXTERNAL AI VISIBILITY INTELLIGENCE" in md_text
        assert "EXTERNAL OBSERVATION SCOPE & LIMITATION DISCLAIMER" in md_text
        assert "### 📋 Observable Query Results Matrix:" in md_text
        assert "### 🔗 External Citations & Target Domain Linkage:" in md_text
        assert "### 🛤️ Website ↔ External Evidence Chain Linkages:" in md_text

        # JSON check
        json_str = JsonReporter.render_audit(report)
        data = json.loads(json_str)
        assert "unified_external_visibility" in data
        assert data["unified_external_visibility"]["status"] == "SUCCESS"
        assert len(data["unified_external_visibility"]["observations"]) > 0

    def test_site_crawl_frontier_aggregation(self):
        frontier = CrawlFrontier(
            base_url="https://sunrisetesting.vercel.app",
            config=CrawlConfig(
                enable_external_visibility=True,
                external_visibility_providers=["mock"],
            ),
        )
        # Mock site records
        site_result = SiteCrawlResult(
            completeness_status="CRAWL_COMPLETE",
            pages_crawled=2,
        )
        with patch.object(frontier, "build_result", wraps=frontier.build_result):
            from rankintel.engines.external_visibility_engine import ExternalVisibilityEngine
            ExternalVisibilityEngine.evaluate_site(site_result, config=frontier.config)

            assert site_result.external_visibility_intelligence is not None
            assert site_result.external_visibility_intelligence.status in ("success", "partial", "unavailable")
            assert len(site_result.external_visibility_intelligence.limitations_and_disclaimers) > 0
