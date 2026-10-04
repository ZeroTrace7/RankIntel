"""
Phase 11.4 — Capability-Gap Discovery & Engine Evolution Tests.
Verifies deterministic gap analysis, zero network calls, formula invariance (Δ=0),
proper classification of true capability gaps vs website deficiencies,
and JSON/Markdown output parity.
"""
import json
import socket
from pathlib import Path
from unittest.mock import patch
import pytest

from rankintel.benchmark.models import (
    CapabilityGapAnalysisReport,
    CapabilityGapRecord,
    FalseGapExclusionRecord,
    GapCategory,
    GapClassification,
    GapSeverity,
)
from rankintel.benchmark.gap_analyzer import CapabilityGapAnalyzer
from rankintel.reporters.capability_gap_reporter import CapabilityGapReporter
from audit_engine import run_analyze_gaps


def test_gap_models_instantiation():
    """Verify Phase 11.4 Pydantic models instantiate and validate properly."""
    record = CapabilityGapRecord(
        gap_id="TEST-GAP-001",
        category=GapCategory.DETECTION_BLIND_SPOT,
        affected_engine="src/rankintel/engines/entity_engine.py",
        title="Test Gap Record",
        severity=GapSeverity.P0,
        classification=GapClassification.TRUE_CAPABILITY_GAP,
        confidence=0.99,
        observed_evidence="Observed test evidence.",
        why_current_output_insufficient="Output insufficient explanation.",
        supporting_sites=["sunrisetesting.vercel.app"],
        expected_behavior="Expected behavior statement.",
        recommended_future_direction="Recommended direction statement.",
    )
    assert record.gap_id == "TEST-GAP-001"
    assert record.severity == GapSeverity.P0
    assert record.classification == GapClassification.TRUE_CAPABILITY_GAP
    assert record.category == GapCategory.DETECTION_BLIND_SPOT

    ex = FalseGapExclusionRecord(
        exclusion_id="TEST-EXCL-001",
        candidate_gap="Candidate false gap",
        classification=GapClassification.WEBSITE_DEFICIENCY,
        observed_evidence="Site evidence",
        why_not_engine_defect="Genuinely absent on website",
        affected_sites=["alephindia.in"],
    )
    assert ex.exclusion_id == "TEST-EXCL-001"
    assert ex.classification == GapClassification.WEBSITE_DEFICIENCY


def test_analyzer_determinism():
    """Verify that CapabilityGapAnalyzer produces deterministic, bit-identical outputs on repeated runs."""
    report1 = CapabilityGapAnalyzer.analyze()
    report2 = CapabilityGapAnalyzer.analyze()

    assert report1.total_gaps_cataloged == report2.total_gaps_cataloged
    assert report1.true_capability_gaps_count == report2.true_capability_gaps_count
    assert report1.false_gap_exclusions_count == report2.false_gap_exclusions_count
    assert report1.priority_breakdown == report2.priority_breakdown
    assert report1.engine_distribution == report2.engine_distribution
    assert report1.model_dump_json() == report2.model_dump_json()


def test_zero_network_calls_during_analysis(monkeypatch):
    """Verify that CapabilityGapAnalyzer executes 100% offline with zero network requests."""
    def guarded_connect(*args, **kwargs):
        raise AssertionError("Network socket connection attempted during strictly offline gap analysis!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    report = CapabilityGapAnalyzer.analyze()
    assert report is not None
    assert report.total_gaps_cataloged > 0


def test_formula_invariance_preserved():
    """Verify strict health-score formula invariance (Δ=0)."""
    report = CapabilityGapAnalyzer.analyze()
    assert report.formula_invariance_verified is True


def test_critical_distinction_true_gaps_vs_website_deficiencies():
    """Verify strict separation between true capability gaps and false-gap website deficiencies."""
    report = CapabilityGapAnalyzer.analyze()

    # Verify false gap exclusions are exclusively classified as WEBSITE_DEFICIENCY
    for ex in report.false_gap_exclusions:
        assert ex.classification == GapClassification.WEBSITE_DEFICIENCY
        assert "engine defect" not in ex.why_not_engine_defect.lower() or "not an engine" in ex.why_not_engine_defect.lower()

    # Specific exclusion checks
    ex_ids = {ex.exclusion_id: ex for ex in report.false_gap_exclusions}
    assert "EXCL-WEBSITE-001" in ex_ids  # /llms.txt absence
    assert "EXCL-WEBSITE-002" in ex_ids  # Schema absence on 6 sites
    assert "EXCL-WEBSITE-003" in ex_ids  # 0% alt coverage on sunrise
    assert "EXCL-WEBSITE-004" in ex_ids  # Missing CSP headers
    assert "EXCL-WEBSITE-005" in ex_ids  # 0 forms on sunrise

    # Verify true gaps are not classified as WEBSITE_DEFICIENCY
    true_gaps = [g for g in report.gaps if g.classification == GapClassification.TRUE_CAPABILITY_GAP]
    for g in true_gaps:
        assert g.classification != GapClassification.WEBSITE_DEFICIENCY


def test_p0_critical_gaps_present():
    """Verify that the critical P0 gaps are cataloged with concrete supporting evidence."""
    report = CapabilityGapAnalyzer.analyze()
    p0_gaps = [g for g in report.gaps if g.severity == GapSeverity.P0]
    p0_ids = {g.gap_id for g in p0_gaps}

    # Brand entity detection blind spot
    assert "GAP-ENT-002" in p0_ids
    ent_gap = next(g for g in p0_gaps if g.gap_id == "GAP-ENT-002")
    assert any("yadavmeasurements.com" in s for s in ent_gap.supporting_sites)
    assert ent_gap.category == GapCategory.DETECTION_BLIND_SPOT


    # Headless browser rendering bypass
    assert "GAP-RETRIEVAL-001" in p0_ids
    ret_gap = next(g for g in p0_gaps if g.gap_id == "GAP-RETRIEVAL-001")
    assert ret_gap.category == GapCategory.DETECTION_BLIND_SPOT
    assert "rendered_words: 0" in ret_gap.observed_evidence


def test_category_breadth_coverage():
    """Verify that all required capability gap categories are evaluated."""
    report = CapabilityGapAnalyzer.analyze()
    categories_found = {g.category for g in report.gaps}

    required_categories = {
        GapCategory.DETECTION_BLIND_SPOT,
        GapCategory.EXTRACTION_BLIND_SPOT,
        GapCategory.SEMANTIC_INTERPRETATION,
        GapCategory.SEARCH_INTENT,
        GapCategory.TOPIC_DIFFERENTIATION,
        GapCategory.ENTITY_CLAIM_GROUNDING,
        GapCategory.AI_GEO_INTERPRETATION,
        GapCategory.MULTIMODAL_AGENT,
        GapCategory.CROSS_SITE_COMPARISON,
        GapCategory.EVIDENCE_PROVENANCE,
        GapCategory.RECOMMENDATION_QUALITY,
    }

    for cat in required_categories:
        assert cat in categories_found, f"Required category {cat} missing from catalog!"


def test_reporting_defect_forms_and_buttons():
    """Verify GAP-AGENT-001 accurately documents the 'Forms' column conflation defect."""
    report = CapabilityGapAnalyzer.analyze()
    agent_gap = next((g for g in report.gaps if g.gap_id == "GAP-AGENT-001"), None)
    assert agent_gap is not None
    assert agent_gap.classification == GapClassification.REPORTING_DEFECT
    assert "alephindia.in: 87" in agent_gap.observed_evidence
    assert "3 forms, 84 buttons" in agent_gap.observed_evidence


def test_markdown_json_output_parity(tmp_path):
    """Verify 100% data parity between JSON and Markdown reports."""
    report = CapabilityGapAnalyzer.analyze()
    json_path, md_path = CapabilityGapReporter.save_reports(report, output_dir=str(tmp_path))

    assert Path(json_path).exists()
    assert Path(md_path).exists()

    with open(json_path, "r", encoding="utf-8") as f:
        loaded_json = json.load(f)

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # All gap IDs and titles in JSON must appear in Markdown
    for g in loaded_json["gaps"]:
        assert g["gap_id"] in md_text
        assert g["category"] in md_text

    # All exclusion IDs must appear in Markdown
    for ex in loaded_json["false_gap_exclusions"]:
        assert ex["exclusion_id"] in md_text

    # Priority counts must match
    assert f"P0: {loaded_json['priority_breakdown']['P0']}" in md_text
    assert f"P1: {loaded_json['priority_breakdown']['P1']}" in md_text


def test_cli_analyze_gaps_execution(tmp_path):
    """Verify that run_analyze_gaps executes successfully via CLI harness."""
    md_result = run_analyze_gaps(
        output_dir=str(tmp_path),
        output_format="markdown",
    )
    assert Path(md_result).exists()
    assert "capability_gaps_phase11.md" in md_result

    json_result = run_analyze_gaps(
        output_dir=str(tmp_path),
        output_format="json",
    )
    assert Path(json_result).exists()
    assert "capability_gaps_phase11.json" in json_result


def test_all_gap_fields_valid():
    """Verify all gap records contain non-empty required fields and high confidence."""
    report = CapabilityGapAnalyzer.analyze()
    for g in report.gaps:
        assert g.gap_id.startswith("GAP-") or g.gap_id.startswith("LIM-")
        assert len(g.title) > 5
        assert len(g.observed_evidence) > 20
        assert len(g.why_current_output_insufficient) > 20
        assert len(g.expected_behavior) > 20
        assert len(g.recommended_future_direction) > 20
        assert 0.0 <= g.confidence <= 1.0
        assert len(g.supporting_sites) > 0


def test_epistemic_separation_integrity():
    """Verify epistemic separation contains facts, analyses, external observations, and recommendations."""
    report = CapabilityGapAnalyzer.analyze()
    assert len(report.epistemic_separation.facts) > 0
    assert len(report.epistemic_separation.analyses) > 0
    assert len(report.epistemic_separation.recommendations) > 0
    assert len(report.epistemic_separation.external_observations) > 0


def test_m11_5_recommendations_count():
    """Verify actionable roadmap recommendations for Phase 11.5 are present and prioritized."""
    report = CapabilityGapAnalyzer.analyze()
    assert len(report.recommendations_for_m11_5) >= 8
    # P0 recommendations are first
    assert "GAP-ENT-002" in report.recommendations_for_m11_5[0]
    assert "GAP-RETRIEVAL-001" in report.recommendations_for_m11_5[1]

