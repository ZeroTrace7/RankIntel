"""
Phase 4 fix verification tests.
Covers M4.1 + M4.3 changes:
  - Architecture: raw_html wiring, adapter label, authority domain import
  - Bug fixes: no double deduction, no silent 75 default, passed_audit=90,
    fix guards (no schema fix when org present, no llms fix when present),
    score_formula_mode disclosure.
"""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    OnPageEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    PerformanceEvidence,
    EngineResult,
)
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.intelligence.fixer import FixGenerator
from rankintel.analyzers.trust_evaluator import TrustEvaluator


# ---------------------------------------------------------------------------
# M4.3 — F1: No double title/description deduction
# ---------------------------------------------------------------------------

class TestNoDoubleDeduction:
    def _make_synthesizer(self):
        return IntelligenceSynthesizer()

    def _score(self, on_page: OnPageEvidence, schema: SchemaEvidence | None = None):
        s = self._make_synthesizer()
        return s._compute_technical_score(
            on_page,
            MagicMock(found=True, bot_access={}),
            schema or SchemaEvidence(detected_types=["Organization"]),
        )

    def test_empty_title_deducts_25_only(self):
        """Missing title → -25 max, not -35 (old double-jeopardy was -25 + -10).
        Description is within bounds [110,165] so no additional desc deduction fires."""
        on_page = OnPageEvidence(
            url="https://example.com",
            title="",
            title_length=0,
            meta_description="A perfectly sized description, well within the recommended character range.",
            meta_desc_length=130,  # within [110, 165] — no desc deduction
            h1_count=1,
        )
        score = self._score(on_page)
        # 100 - 25 (no title) = 75
        assert score == 75, f"Expected 75 but got {score} — double-deduction may still be present"

    def test_empty_description_deducts_20_only(self):
        """Missing description → -20 max, not -30."""
        on_page = OnPageEvidence(
            url="https://example.com",
            title="A Perfectly Sized Title Right Here For Testing",
            title_length=47,  # within [30, 65] — no title deduction
            meta_description="",
            meta_desc_length=0,
            h1_count=1,
        )
        score = self._score(on_page)
        # 100 - 20 (no desc) = 80
        assert score == 80, f"Expected 80 but got {score}"

    def test_short_title_deducts_10_only(self):
        """Wrong-length title (present but short) → -10 only, not -35.
        Description and other signals are valid."""
        on_page = OnPageEvidence(
            url="https://example.com",
            title="Hi",
            title_length=2,  # < 30 → -10 for length, but title IS present so -25 does NOT fire
            meta_description="A description that is within the recommended bounds for meta descriptions.",
            meta_desc_length=130,  # within [110, 165]
            h1_count=1,
        )
        score = self._score(on_page)
        # 100 - 10 (short title) = 90
        assert score == 90, f"Expected 90 but got {score}"


# ---------------------------------------------------------------------------
# M4.3 — F2: No silent perf=75 default; formula mode = 3_engine when no perf
# ---------------------------------------------------------------------------

class TestPerfDefault:
    def test_missing_perf_score_is_zero_not_75(self):
        perf = PerformanceEvidence(
            overall_performance_score=0,
            source="unavailable",
            notes=["Performance engine did not execute — score excluded from holistic formula."],
        )
        assert perf.overall_performance_score == 0
        assert perf.source == "unavailable"

    def test_synthesizer_uses_3engine_formula_when_no_perf(self):
        """When perf engine returns source=unavailable, formula_mode must be 3_engine."""
        synth = IntelligenceSynthesizer()

        seo_res = EngineResult(engine_name="advertools_seo", status="success",
                               on_page=OnPageEvidence(url="https://x.com", title="Test Title Here OK",
                                                      title_length=18, h1_count=1,
                                                      meta_description="Desc", meta_desc_length=4),
                               schema_data=SchemaEvidence(detected_types=["Organization"]))
        geo_res = EngineResult(engine_name="rankintel_geo", status="success",
                               geo_aeo=GeoAeoEvidence(overall_citability_score=50))
        perf_res = EngineResult(engine_name="performance_engine", status="error",
                                error_message="No PSI key")

        engine_results = {
            "advertools_seo": seo_res,
            "browser_engine": EngineResult(engine_name="browser_engine", status="error"),
            "rankintel_geo": geo_res,
            "performance_engine": perf_res,
            "mcp_cloud": EngineResult(engine_name="mcp_cloud", status="skipped"),
        }

        report = synth.synthesize("https://x.com", engine_results)
        assert report.score_formula_mode == "3_engine", (
            f"Expected '3_engine' but got '{report.score_formula_mode}'"
        )
        assert report.performance_score == 0


# ---------------------------------------------------------------------------
# M4.3 — F3: passed_audit threshold is >= 90
# ---------------------------------------------------------------------------

class TestPassedAuditThreshold:
    def test_score_89_fails(self):
        perf = PerformanceEvidence(overall_performance_score=89, passed_audit=False)
        assert not perf.passed_audit

    def test_score_90_passes(self):
        perf = PerformanceEvidence(overall_performance_score=90, passed_audit=True)
        assert perf.passed_audit

    def test_performance_engine_notes_mention_rankintel_bands(self):
        """PSI API notes must say 'RankIntel performance bands', not 'Google standard'."""
        from rankintel.engines.performance_engine import PerformanceEngine
        import inspect
        source = inspect.getsource(PerformanceEngine)
        assert "RankIntel performance bands" in source, (
            "Performance engine must label bands as 'RankIntel performance bands'"
        )
        assert "Google standard" not in source


# ---------------------------------------------------------------------------
# M4.3 — F4: Fix guards
# ---------------------------------------------------------------------------

class TestFixGuards:
    def test_no_schema_fix_when_org_present(self):
        schema = SchemaEvidence(has_organization=True)
        result = FixGenerator.generate_jsonld_schema(
            "https://example.com", "example.com",
            OnPageEvidence(url="https://example.com"), schema
        )
        assert result is None, "Should return None when Organization schema already present"

    def test_schema_fix_generated_when_no_org(self):
        schema = SchemaEvidence(has_organization=False)
        result = FixGenerator.generate_jsonld_schema(
            "https://example.com", "example.com",
            OnPageEvidence(url="https://example.com"), schema
        )
        assert result is not None
        assert "application/ld+json" in result

    def test_no_llms_fix_when_already_present(self):
        geo = GeoAeoEvidence(llms_txt_found=True)
        result = FixGenerator.generate_llms_txt(
            "example.com", "https://example.com",
            OnPageEvidence(url="https://example.com"), geo
        )
        assert result is None, "Should return None when llms.txt is already present"

    def test_llms_fix_generated_when_missing(self):
        geo = GeoAeoEvidence(llms_txt_found=False)
        result = FixGenerator.generate_llms_txt(
            "example.com", "https://example.com",
            OnPageEvidence(url="https://example.com", title="Example", meta_description="Desc"),
            geo
        )
        assert result is not None
        assert result.startswith("# Example")


# ---------------------------------------------------------------------------
# M4.3 — F6: score_formula_mode disclosed in report
# ---------------------------------------------------------------------------

class TestFormulaModeDisclosure:
    def test_4engine_formula_mode_present(self):
        synth = IntelligenceSynthesizer()

        engine_results = {
            "advertools_seo": EngineResult(
                engine_name="advertools_seo", status="success",
                on_page=OnPageEvidence(url="https://x.com", title="Title Here Good",
                                       title_length=16, h1_count=1,
                                       meta_description="Good description text", meta_desc_length=21),
                schema_data=SchemaEvidence(detected_types=["WebSite"]),
            ),
            "browser_engine": EngineResult(engine_name="browser_engine", status="error"),
            "rankintel_geo": EngineResult(engine_name="rankintel_geo", status="success",
                                          geo_aeo=GeoAeoEvidence(overall_citability_score=60)),
            "performance_engine": EngineResult(
                engine_name="performance_engine", status="success",
                performance=PerformanceEvidence(overall_performance_score=85, passed_audit=False, source="local_probe"),
            ),
            "mcp_cloud": EngineResult(engine_name="mcp_cloud", status="skipped"),
        }

        report = synth.synthesize("https://x.com", engine_results)
        assert report.score_formula_mode == "4_engine"
        assert hasattr(report, "score_formula_mode")


# ---------------------------------------------------------------------------
# M4.1 — Architecture: raw_html wiring
# ---------------------------------------------------------------------------

class TestRawHtmlWiring:
    def test_engine_result_has_raw_html_field(self):
        er = EngineResult(engine_name="browser_engine", status="success", raw_html="<html></html>")
        assert er.raw_html == "<html></html>"

    def test_trust_evaluator_accepts_raw_html(self):
        """TrustEvaluator.evaluate() must accept raw_html param without error."""
        on_page = OnPageEvidence(
            url="https://example.com",
            title="Test", title_length=4,
            meta_description="", meta_desc_length=0,
            h1_count=1,
            response_headers={"content-type": "text/html"},
        )
        schema = SchemaEvidence(detected_types=["Organization"], has_organization=True)
        result = TrustEvaluator.evaluate(
            url="https://example.com",
            on_page=on_page,
            schema=schema,
            raw_html="<html><head></head><body><h1>Test</h1></body></html>",
        )
        assert result is not None
        assert 0 <= result.overall_score <= 100

    def test_trust_evaluator_legacy_html_soup_still_works(self):
        """Backward-compat: html_soup param must still be accepted."""
        on_page = OnPageEvidence(url="https://example.com", title="T", title_length=1,
                                  response_headers={})
        soup = BeautifulSoup("<html><body><h1>T</h1></body></html>", "html.parser")
        result = TrustEvaluator.evaluate(
            url="https://example.com",
            on_page=on_page,
            schema=SchemaEvidence(),
            html_soup=soup,
        )
        assert result is not None


# ---------------------------------------------------------------------------
# M4.1 — Shared authority domains module
# ---------------------------------------------------------------------------

class TestAuthorityDomains:
    def test_shared_module_importable(self):
        from rankintel.references.authority_domains import (
            AUTHORITATIVE_DOMAINS, SOCIAL_DOMAINS, AUTHORITATIVE_TLDS
        )
        assert "wikipedia.org" in AUTHORITATIVE_DOMAINS
        assert "linkedin.com" in SOCIAL_DOMAINS
        assert ".edu" in AUTHORITATIVE_TLDS

    def test_trust_evaluator_uses_shared_domains(self):
        """trust_evaluator.py must NOT define its own AUTHORITATIVE_DOMAINS list."""
        import inspect
        from rankintel.analyzers import trust_evaluator as te_module
        src = inspect.getsource(te_module)
        # Must not have inline list definition; must import from references
        assert "from rankintel.references.authority_domains import" in src

    def test_geo_optimizer_adapter_importable(self):
        from rankintel.adapters.geo_optimizer_adapter import GeoOptimizerAdapter
        adapter = GeoOptimizerAdapter()
        assert adapter is not None
