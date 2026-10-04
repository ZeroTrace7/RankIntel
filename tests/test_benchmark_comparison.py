"""
Phase 11.3 — Cross-Site Competitive Comparison & Void Analysis Tests.
Validates determinism, zero network calls, formula invariance (delta = 0),
epistemic separation, provenance retention, and output parity.
"""
import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from rankintel.benchmark.models import (
    ComparisonState,
    CrossSiteMatrixItem,
    EntityComparisonAnalysis,
    ServiceProductComparisonAnalysis,
    TopicConceptComparisonAnalysis,
    SearchIntentComparisonAnalysis,
    ConcentrationOverlapComparisonAnalysis,
    SchemaCoverageComparisonAnalysis,
    AnswerabilityComparisonAnalysis,
    ClaimGroundingComparisonAnalysis,
    AiRetrievalComparisonAnalysis,
    MultimodalAgentComparisonAnalysis,
    TechnicalA11ySecurityComparisonAnalysis,
    ObservableVoidItem,
    TargetVsBenchmarkComparison,
    EvidenceUncertaintyProfile,
    BenchmarkComparisonReport,
)
from rankintel.benchmark.comparator import CrossSiteComparator
from rankintel.reporters.comparison_reporter import ComparisonReporter
from audit_engine import run_compare_benchmark

BENCHMARK_REVIEWS_FILE = Path("benchmarks/reviews/benchmark_reviews_phase11.json")


def test_comparison_models_instantiation():
    """Verify all comparison models instantiate cleanly with defaults."""
    item = CrossSiteMatrixItem(domain="example.com")
    assert item.domain == "example.com"
    assert item.health_score == 0

    ent = EntityComparisonAnalysis()
    assert ent.total_unique_entities_across_benchmark == 0
    assert ent.state == ComparisonState.OBSERVED_DIFFERENCE

    srv = ServiceProductComparisonAnalysis()
    assert srv.all_observed_services == []

    top = TopicConceptComparisonAnalysis()
    assert top.all_dominant_concepts == []

    void = ObservableVoidItem(
        void_id="VOID-TEST-001",
        category="SCHEMA",
        title="Test Void",
        description="Testing void detection.",
    )
    assert void.void_id == "VOID-TEST-001"
    assert void.state == ComparisonState.OBSERVED_DIFFERENCE


def test_comparison_states_enum():
    """Verify required explicit comparison states are present."""
    assert ComparisonState.OBSERVED_DIFFERENCE == "OBSERVED_DIFFERENCE"
    assert ComparisonState.COMMON == "COMMON"
    assert ComparisonState.UNIQUE == "UNIQUE"
    assert ComparisonState.PARTIAL == "PARTIAL"
    assert ComparisonState.INSUFFICIENT_EVIDENCE == "INSUFFICIENT_EVIDENCE"
    assert ComparisonState.NOT_COMPARABLE == "NOT_COMPARABLE"


def test_deterministic_comparison_execution():
    """Verify CrossSiteComparator generates a comprehensive BenchmarkComparisonReport."""
    assert BENCHMARK_REVIEWS_FILE.exists(), "Benchmark reviews file must exist"
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)

    assert isinstance(report, BenchmarkComparisonReport)
    assert report.total_sites == 11
    assert report.target_domain == "sunrisetesting.vercel.app"
    assert len(report.cohort_domains) == 10
    assert len(report.cross_site_matrix) == 11

    # Check 14 analytical areas are populated
    assert report.entity_comparison.total_unique_entities_across_benchmark > 0
    assert len(report.service_comparison.all_observed_services) > 0
    assert len(report.topic_concept_comparison.all_dominant_concepts) > 0
    assert len(report.search_intent_comparison.intent_distribution) > 0
    assert len(report.concentration_comparison.content_to_boilerplate_by_site) == 11
    assert len(report.schema_comparison.schema_adoption_counts) == 11
    assert len(report.answerability_comparison.total_units_by_site) == 11
    assert len(report.claim_grounding_comparison.total_claims_by_site) == 11
    assert len(report.retrieval_comparison.search_bots_allowed_by_site) == 11
    assert len(report.multimodal_agent_comparison.visual_assets_by_site) == 11
    assert len(report.technical_a11y_security_comparison.https_by_site) == 11
    assert len(report.observable_voids) >= 8
    assert report.target_vs_benchmark.target_domain == "sunrisetesting.vercel.app"
    assert len(report.uncertainty_and_limitations.dimensional_statuses) == 15


def test_comparison_repeatability():
    """Verify deterministic repeatability: two runs produce identical results."""
    report1 = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
    report2 = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)

    json1 = report1.model_dump_json(indent=2)
    json2 = report2.model_dump_json(indent=2)
    assert json1 == json2, "Repeated comparison execution must yield bit-identical JSON"


def test_formula_invariance_delta_zero():
    """Verify that health scores remain bit-identical across comparison (Delta = 0)."""
    with open(BENCHMARK_REVIEWS_FILE, "r", encoding="utf-8") as f:
        rev_data = json.load(f)["reviews"]

    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
    assert report.formula_invariance_verified is True

    for item in report.cross_site_matrix:
        src = rev_data[item.domain]
        assert item.health_score == src["overall_health_score"]
        assert item.technical_health_score == src["technical_health_score"]
        assert item.geo_readiness_score == src["geo_readiness_score"]
        assert item.trust_score == src["trust_score"]
        assert item.performance_score == src["performance_score"]


def test_zero_network_calls_during_comparison():
    """Verify comparison executes strictly in-memory with zero network requests."""
    def guarded_connect(*args, **kwargs):
        raise AssertionError("Network socket connection attempted during offline cross-site comparison!")

    with patch.object(socket.socket, "connect", side_effect=guarded_connect):
        report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
        assert report.total_sites == 11


def test_epistemic_separation_and_state_preservation():
    """Verify findings are strictly partitioned into epistemic tiers."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)

    assert len(report.epistemic_separation.facts) > 0
    assert len(report.epistemic_separation.external_observations) > 0
    assert len(report.epistemic_separation.analyses) > 0
    assert len(report.epistemic_separation.recommendations) > 0

    valid_states = {s.value for s in ComparisonState}
    for void in report.observable_voids:
        assert void.state.value in valid_states
        assert void.epistemic_tier in ("FACT", "ANALYSIS", "EXTERNAL OBSERVATION", "RECOMMENDATION")


def test_common_vs_unique_entities_and_services():
    """Verify common vs unique entity and service extraction."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)

    # Services
    srv = report.service_comparison
    assert "Testing" in srv.common_services or "testing" in [s.lower() for s in srv.common_services]
    assert "Calibration" in srv.common_services or "calibration" in [s.lower() for s in srv.common_services]
    assert len(srv.target_common_services) > 0

    # Entity types
    ent = report.entity_comparison
    assert "ORGANIZATION" in ent.entity_types_coverage or "LOCAL_BUSINESS" in ent.entity_types_coverage


def test_jaccard_concept_overlap_matrix():
    """Verify mathematical properties of the Jaccard similarity matrix."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
    matrix = report.topic_concept_comparison.jaccard_similarity_matrix

    all_doms = report.cohort_domains + [report.target_domain]
    for d1 in all_doms:
        assert d1 in matrix
        # Self-similarity must be 1.0
        assert matrix[d1][d1] == 1.0

        for d2 in all_doms:
            sim = matrix[d1][d2]
            # Bounded between 0.0 and 1.0
            assert 0.0 <= sim <= 1.0
            # Symmetry
            assert matrix[d1][d2] == matrix[d2][d1]


def test_observable_voids_detection_and_provenance():
    """Verify that detected voids retain provenance, supporting fields, and references."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)

    for void in report.observable_voids:
        assert void.void_id.startswith("VOID-")
        assert len(void.supporting_fields) > 0
        assert len(void.provenance_sources) > 0
        assert len(void.evidence_references) > 0

    schema_void = next((v for v in report.observable_voids if v.void_id == "VOID-SCHEMA-001"), None)
    assert schema_void is not None
    assert schema_void.target_site_status == "ABSENT"


def test_target_vs_benchmark_comparison():
    """Verify Target vs Benchmark comparison logic and deltas."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
    target_comp = report.target_vs_benchmark

    assert target_comp.target_domain == "sunrisetesting.vercel.app"
    assert len(target_comp.benchmark_cohort_domains) == 10
    assert len(target_comp.target_unique_capabilities) > 0
    assert len(target_comp.common_capabilities) > 0
    assert len(target_comp.dimensional_deltas) >= 5

    health_delta = next((d for d in target_comp.dimensional_deltas if d["dimension"] == "Overall Search Health"), None)
    assert health_delta is not None
    assert "target_value" in health_delta
    assert "observable_delta" in health_delta


def test_output_parity_markdown_and_json(tmp_path):
    """Verify data parity between Markdown and JSON outputs."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
    artifacts = ComparisonReporter.save_comparison_artifacts(report, output_dir=tmp_path)

    with open(artifacts["comparison_json"], "r", encoding="utf-8") as f:
        json_data = json.load(f)

    with open(artifacts["comparison_md"], "r", encoding="utf-8") as f:
        md_text = f.read()

    # Domain count parity
    assert json_data["total_sites"] == 11
    assert "11 permanent benchmark sites" in md_text

    # Target health score parity
    target_score = next(m["health_score"] for m in json_data["cross_site_matrix"] if m["domain"] == "sunrisetesting.vercel.app")
    assert f"`sunrisetesting.vercel.app` | **TARGET** | **{target_score}**" in md_text

    # Void count parity
    assert len(json_data["observable_voids"]) == len(report.observable_voids)
    for v in json_data["observable_voids"]:
        assert v["void_id"] in md_text


def test_comparison_reporter_persistence(tmp_path):
    """Verify ComparisonReporter writes all four files correctly."""
    report = CrossSiteComparator.compare(BENCHMARK_REVIEWS_FILE)
    artifacts = ComparisonReporter.save_comparison_artifacts(report, output_dir=tmp_path)

    assert Path(artifacts["comparison_json"]).exists()
    assert Path(artifacts["comparison_md"]).exists()
    assert Path(artifacts["target_json"]).exists()
    assert Path(artifacts["target_md"]).exists()


def test_cli_run_compare_benchmark(tmp_path):
    """Verify run_compare_benchmark CLI handler operates without error."""
    out = run_compare_benchmark(
        target="sunrisetesting.vercel.app",
        reviews_file=str(BENCHMARK_REVIEWS_FILE),
        output_dir=str(tmp_path),
        output_format="markdown",
    )
    assert Path(out).exists()
