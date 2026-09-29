"""
Unit tests for JsonReporter serialization and file output.
"""
import json
import os
import tempfile
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.models.schema import (
    SynthesisReport,
    ComparisonReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    GapDelta,
    GapAction
)

def test_json_reporter_audit_render_and_save():
    report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-09-30",
        overall_health_score=85,
        technical_health_score=90,
        geo_readiness_score=80,
        trust_score=75,
        performance_score=90,
        keyword_score=70,
        unified_on_page=OnPageEvidence(
            url="https://example.com",
            title="Example Domain",
            title_length=14,
            h1_count=1
        ),
        fixes={"optimized_title": "Optimized Title | Example"}
    )

    json_str = JsonReporter.render_audit(report)
    parsed = json.loads(json_str)

    assert parsed["url"] == "https://example.com"
    assert parsed["overall_health_score"] == 85
    assert parsed["keyword_score"] == 70
    assert parsed["fixes"]["optimized_title"] == "Optimized Title | Example"

    with tempfile.TemporaryDirectory() as tmpdir:
        path = JsonReporter.save_audit(report, output_dir=tmpdir)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["domain"] == "example.com"

def test_json_reporter_comparison_render_and_save():
    rep_a = SynthesisReport(
        url="https://a.com",
        domain="a.com",
        timestamp="2026-09-30",
        overall_health_score=80
    )
    rep_b = SynthesisReport(
        url="https://b.com",
        domain="b.com",
        timestamp="2026-09-30",
        overall_health_score=60
    )

    comparison = ComparisonReport(
        target_a_url="https://a.com",
        target_b_url="https://b.com",
        timestamp="2026-09-30",
        target_a_report=rep_a,
        target_b_report=rep_b,
        winner_url="https://a.com",
        score_gap=20,
        category_deltas=[
            GapDelta(
                category="Overall Search & GEO Health",
                target_a_val="80/100",
                target_b_val="60/100",
                winner="https://a.com",
                impact="Test impact"
            )
        ],
        action_plan=[
            GapAction(
                category="Performance",
                title="Optimize TTFB",
                rationale="Lower is better",
                impact_points=8,
                priority="MEDIUM",
                winning_advantage="Faster server",
                remediation_suggestion="Edge caching"
            )
        ]
    )

    json_str = JsonReporter.render_comparison(comparison)
    parsed = json.loads(json_str)

    assert parsed["winner_url"] == "https://a.com"
    assert parsed["score_gap"] == 20
    assert len(parsed["category_deltas"]) == 1
    assert len(parsed["action_plan"]) == 1

    with tempfile.TemporaryDirectory() as tmpdir:
        path = JsonReporter.save_comparison(comparison, output_dir=tmpdir)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["score_gap"] == 20
