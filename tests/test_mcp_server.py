"""
Unit tests for RankIntel FastMCP server tools.
"""
from unittest.mock import patch, MagicMock
from rankintel.mcp.server import rankintel_audit, rankintel_compare, rankintel_generate_fixes
from rankintel.models.schema import SynthesisReport, OnPageEvidence, RobotsEvidence, SchemaEvidence, GeoAeoEvidence

def test_rankintel_audit_tool():
    mock_report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-09-30",
        overall_health_score=80,
        technical_health_score=85,
        geo_readiness_score=75,
        trust_score=70,
        performance_score=85,
        unified_on_page=OnPageEvidence(title="Example", title_length=7),
        unified_geo=GeoAeoEvidence(llms_txt_found=True),
        fixes={"optimized_title": "Optimized Example | Brand"}
    )

    with patch("rankintel.mcp.server.EvidenceCollector"), \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as mock_synth_cls:
        mock_synth = mock_synth_cls.return_value
        mock_synth.synthesize.return_value = mock_report

        res = rankintel_audit("https://example.com")

    assert res["url"] == "https://example.com"
    assert res["overall_health_score"] == 80
    assert res["llms_txt_present"] is True
    assert "production_fixes" in res
    assert res["production_fixes"]["optimized_title"] == "Optimized Example | Brand"

def test_rankintel_compare_tool():
    rep_a = SynthesisReport(
        url="https://a.com",
        domain="a.com",
        timestamp="2026-09-30",
        overall_health_score=85,
        technical_health_score=90,
        geo_readiness_score=80
    )
    rep_b = SynthesisReport(
        url="https://b.com",
        domain="b.com",
        timestamp="2026-09-30",
        overall_health_score=50,
        technical_health_score=50,
        geo_readiness_score=50
    )

    from rankintel.intelligence.comparer import IntelligenceComparer
    comp_report = IntelligenceComparer().build_comparison(rep_a, rep_b)

    with patch("rankintel.mcp.server.IntelligenceComparer") as mock_comp_cls:
        mock_comp = mock_comp_cls.return_value
        mock_comp.compare.return_value = comp_report

        res = rankintel_compare("https://a.com", "https://b.com")

    assert res["target_a_score"] == 85
    assert res["target_b_score"] == 50
    assert res["winner_url"] == "https://a.com"
    assert res["score_gap"] == 35
    assert len(res["category_deltas"]) > 0

def test_rankintel_generate_fixes_tool():
    mock_report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-09-30",
        fixes={
            "optimized_title": "Optimized Title",
            "jsonld_schema": "<script>{}</script>",
            "llms_txt": "# LLMS.txt",
            "hardened_robots": "User-agent: *"
        }
    )

    with patch("rankintel.mcp.server.EvidenceCollector"), \
         patch("rankintel.mcp.server.IntelligenceSynthesizer") as mock_synth_cls:
        mock_synth = mock_synth_cls.return_value
        mock_synth.synthesize.return_value = mock_report

        fixes = rankintel_generate_fixes("https://example.com")

    assert "optimized_title" in fixes
    assert "jsonld_schema" in fixes
    assert "llms_txt" in fixes
    assert "hardened_robots" in fixes
