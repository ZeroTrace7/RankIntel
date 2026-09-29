"""
Unit tests for McpEngine and cloud intelligence triangulation.
"""
from unittest.mock import patch, MagicMock
from rankintel.engines.mcp_engine import McpEngine
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.models.schema import (
    EngineResult,
    CloudIntelligenceEvidence,
    KeywordIntelligence,
    BacklinkIntelligence,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence
)

def test_mcp_engine_silent_fallback():
    engine = McpEngine()

    # Even if network raises an unexpected error or times out, execute() returns status="skipped"
    with patch("requests.post", side_effect=Exception("Connection refused / no credits")):
        result = engine.execute("https://example.com")

    assert result.status == "skipped"
    assert result.cloud_intelligence is not None
    assert not result.cloud_intelligence.available

def test_mcp_engine_parses_cloud_responses():
    engine = McpEngine(api_key="test-key")

    mock_overview = MagicMock()
    mock_overview.status_code = 200
    mock_overview.json.return_value = {
        "organic_traffic": 125000,
        "organic_keywords": 4500,
        "top_keywords": [{"keyword": "payment gateway", "position": 1, "volume": 50000}]
    }

    mock_backlinks = MagicMock()
    mock_backlinks.status_code = 200
    mock_backlinks.json.return_value = {
        "referring_domains": 1850,
        "backlinks": 45000,
        "domain_rank": 82
    }

    def mock_post(url, **kwargs):
        if "domain_overview" in url:
            return mock_overview
        elif "backlink_analysis" in url:
            return mock_backlinks
        return MagicMock(status_code=404)

    with patch("requests.post", side_effect=mock_post):
        result = engine.execute("https://stripe.com")

    assert result.status == "success"
    assert result.cloud_intelligence.available
    assert result.cloud_intelligence.keywords.estimated_monthly_traffic == 125000
    assert result.cloud_intelligence.backlinks.referring_domains == 1850

def test_cloud_intelligence_5th_dimension_scoring():
    synthesizer = IntelligenceSynthesizer()

    cloud = CloudIntelligenceEvidence(
        available=True,
        keywords=KeywordIntelligence(
            estimated_monthly_traffic=150000,
            total_keywords=5000
        )
    )

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            on_page=OnPageEvidence(
                url="https://example.com",
                status_code=200,
                title="Example Domain - Optimal Title Length Target",
                title_length=42,
                meta_description="A comprehensive meta description with actionable text exceeding 120 chars for SEO quality verification.",
                meta_desc_length=130,
                h1_count=1,
                h1_text=["Example Domain"]
            ),
            schema_data=SchemaEvidence(detected_types=["Organization"])
        ),
        "mcp_cloud": EngineResult(
            engine_name="mcp_cloud",
            status="success",
            cloud_intelligence=cloud
        )
    }

    report = synthesizer.synthesize("https://example.com", results)

    assert report.keyword_score == 95
    assert report.cloud_intelligence.available
    # 5-engine scoring was triggered
    assert report.overall_health_score > 0
