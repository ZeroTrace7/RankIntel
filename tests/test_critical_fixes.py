"""
Tests explicitly verifying the Critical Bug Fixes:
1. JSON-LD schema extraction not destroyed by script tag stripping
2. Browser engine schema extraction not destroyed by on_page parsing
3. GEO readiness score preserves legitimate 0 citability score
4. Unmeasured TTFB (0.0ms) does not win comparison against measured TTFB
5. McpEngine has compare() method and execution_time_sec tracking
6. FixGenerator meta description length never exceeds quality gate bounds (<= 165 chars)
"""
import json
from unittest.mock import patch, MagicMock
from rankintel.engines.seo_engine import SeoEngine
from rankintel.engines.browser_engine import BrowserEngine
from rankintel.engines.mcp_engine import McpEngine
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.intelligence.comparer import IntelligenceComparer
from rankintel.intelligence.fixer import FixGenerator
from rankintel.models.schema import (
    EngineResult,
    OnPageEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    PerformanceEvidence,
    SynthesisReport
)

SAMPLE_HTML_WITH_SCHEMA = """<!DOCTYPE html>
<html>
<head>
    <title>Enterprise Cloud Platform | Acme Corp</title>
    <meta name="description" content="Acme Corp provides mission-critical enterprise cloud architecture, automated security controls, and high-performance developer tools for global teams.">
    <script>
        var trackingConfig = { enabled: true, id: "GA-12345" };
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Acme Corp",
        "url": "https://acme.example.com",
        "sameAs": ["https://twitter.com/acmecorp"]
    }
    </script>
    <script>
        window.__INITIAL_STATE__ = { user: null };
    </script>
</head>
<body>
    <h1>Enterprise Cloud Infrastructure</h1>
    <h2>Reliable Architecture at Scale</h2>
    <p>Acme Corp delivers 99.999% uptime for cloud infrastructure.</p>
</body>
</html>"""

def test_schema_extraction_order_in_seo_engine():
    """Verify JSON-LD schema is extracted BEFORE script tags are stripped for word count."""
    engine = SeoEngine()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_HTML_WITH_SCHEMA
    mock_resp.headers = {"Content-Type": "text/html"}
    
    with patch("requests.get", return_value=mock_resp):
        on_page, schema = engine.audit_static_page("https://acme.example.com")
        
    assert schema.blocks_count == 1
    assert "Organization" in schema.detected_types
    assert schema.has_organization is True
    assert "https://twitter.com/acmecorp" in schema.sameas_urls
    assert on_page.word_count > 0

def test_browser_engine_schema_not_destroyed_by_on_page():
    """Verify BrowserEngine extracts schemas before on_page strips script tags."""
    engine = BrowserEngine()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_HTML_WITH_SCHEMA
    
    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_resp
    
    with patch("httpx.Client", return_value=mock_client):
        result = engine.execute_sync("https://acme.example.com")
        
    assert result.status == "success"
    assert result.schema_data is not None
    assert "Organization" in result.schema_data.detected_types

def test_geo_score_preserves_legitimate_zero():
    """Verify that a legitimate 0 citability score is preserved, not inflated to 40."""
    synthesizer = IntelligenceSynthesizer()
    
    geo = GeoAeoEvidence(
        overall_citability_score=0,
        answer_first_ratio=0.0
    )
    
    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            on_page=OnPageEvidence(title="Test", meta_description="Test description here that is valid length.")
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=geo
        )
    }
    
    report = synthesizer.synthesize("https://example.com", results)
    assert report.geo_readiness_score == 0

def test_ttfb_unmeasured_does_not_win_comparison():
    """Verify that unmeasured TTFB (0.0ms from failed engine) does not win comparison."""
    comparer = IntelligenceComparer()
    
    rep_a = SynthesisReport(
        url="https://site-a.com",
        domain="site-a.com",
        timestamp="2026-09-30",
        unified_performance=PerformanceEvidence(ttfb_ms=0.0)  # Unmeasured
    )
    rep_b = SynthesisReport(
        url="https://site-b.com",
        domain="site-b.com",
        timestamp="2026-09-30",
        unified_performance=PerformanceEvidence(ttfb_ms=250.0)  # Real measurement
    )
    
    comp = comparer.build_comparison(rep_a, rep_b)
    ttfb_delta = next(d for d in comp.category_deltas if "TTFB" in d.category)
    assert ttfb_delta.winner == "TIE"
    assert ttfb_delta.target_a_val == "N/A"
    assert ttfb_delta.target_b_val == "250ms"

def test_mcp_engine_compare_and_execution_time():
    """Verify McpEngine has compare() method and execution_time_sec."""
    engine = McpEngine()
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "organic_traffic": 50000,
            "organic_keywords": 1200
        }
        res = engine.execute("https://example.com")
        assert res.execution_time_sec >= 0.0
        assert res.status == "success"
        
        comp_data = engine.compare("https://site-a.com", "https://site-b.com")
        assert "https://site-a.com" in comp_data
        assert "https://site-b.com" in comp_data

def test_fixer_meta_desc_length_bounded():
    """Verify that generated meta description fix never exceeds 165 characters."""
    on_page = OnPageEvidence(
        title="Short",
        meta_description="This is an extremely excessively long meta description that goes on and on and on and contains far too many unnecessary words designed to exceed Google SERP truncation boundaries and trigger the fixer trimming logic into action."
    )
    fixes = FixGenerator.generate_meta_fixes(on_page, "acme.com")
    desc_len = int(fixes["desc_length"])
    assert desc_len <= 165
    assert desc_len >= 120
