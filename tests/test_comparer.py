"""
Unit tests for IntelligenceComparer and Gap Analysis.
"""
from rankintel.intelligence.comparer import IntelligenceComparer
from rankintel.models.schema import (
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence
)

def test_comparer_build_comparison():
    comparer = IntelligenceComparer()

    rep_a = SynthesisReport(
        url="https://site-a.com",
        domain="site-a.com",
        timestamp="2026-09-30",
        overall_health_score=85,
        technical_health_score=90,
        geo_readiness_score=80,
        trust_score=80,
        performance_score=90,
        unified_geo=GeoAeoEvidence(llms_txt_found=True, answer_first_ratio=0.5),
        unified_schema=SchemaEvidence(has_organization=True),
        unified_trust=TrustStackResult(grade="A", overall_score=80),
        unified_performance=PerformanceEvidence(ttfb_ms=250.0)
    )

    rep_b = SynthesisReport(
        url="https://site-b.com",
        domain="site-b.com",
        timestamp="2026-09-30",
        overall_health_score=45,
        technical_health_score=50,
        geo_readiness_score=40,
        trust_score=40,
        performance_score=50,
        unified_geo=GeoAeoEvidence(llms_txt_found=False, answer_first_ratio=0.1),
        unified_schema=SchemaEvidence(has_organization=False),
        unified_trust=TrustStackResult(grade="D", overall_score=40),
        unified_performance=PerformanceEvidence(ttfb_ms=1100.0)
    )

    comp = comparer.build_comparison(rep_a, rep_b)

    assert comp.winner_url == "https://site-a.com"
    assert comp.score_gap == 40
    assert len(comp.category_deltas) >= 5
    assert len(comp.action_plan) >= 2
    # Verify that gap action prioritizes the missing /llms.txt
    assert any("llms.txt" in act.title for act in comp.action_plan)
