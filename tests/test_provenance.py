"""
Unit tests for Evidence Provenance Tagger.
"""
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.models.schema import (
    EngineResult,
    OnPageEvidence,
    RobotsEvidence,
    BotStatus,
    SchemaEvidence,
    GeoAeoEvidence,
    PerformanceEvidence
)

def test_provenance_schema_cross_engine_confirmation():
    # Both static and browser engines detect Organization schema
    static_schema = SchemaEvidence(detected_types=["Organization", "WebSite"])
    browser_schema = SchemaEvidence(detected_types=["Organization", "WebSite", "Product"])

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            schema_data=static_schema
        ),
        "browser_engine": EngineResult(
            engine_name="browser_engine",
            schema_data=browser_schema
        )
    }

    tags = ProvenanceTagger.tag(results)

    # Organization should be confirmed by browser_engine
    org_tag = next((t for t in tags if "Organization" in t.finding), None)
    assert org_tag is not None
    assert "browser_engine" in org_tag.confirmed_by
    assert org_tag.engine == "seo_engine"

    # Product should be identified as JS-injected and contradicted by seo_engine
    prod_tag = next((t for t in tags if "Product" in t.finding), None)
    assert prod_tag is not None
    assert "JS-injected" in prod_tag.finding
    assert "seo_engine" in prod_tag.contradicted_by
    assert prod_tag.engine == "browser_engine"

def test_provenance_robots_and_geo_tags():
    robots = RobotsEvidence(found=True)
    robots.bot_access["OAI-SearchBot"] = BotStatus(
        bot="OAI-SearchBot", status="ALLOWED", category="search"
    )

    geo = GeoAeoEvidence(
        llms_txt_found=True,
        overall_citability_score=68
    )

    perf = PerformanceEvidence(
        source="pagespeed_crux_field",
        ttfb_ms=320.0
    )

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            robots=robots
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            geo_aeo=geo
        ),
        "performance_engine": EngineResult(
            engine_name="performance_engine",
            performance=perf
        )
    }

    tags = ProvenanceTagger.tag(results)

    assert any("OAI-SearchBot: ALLOWED" in t.finding for t in tags)
    assert any("/llms.txt: PRESENT" in t.finding for t in tags)
    assert any("Princeton GEO Citability: 68/100" in t.finding for t in tags)
    
    perf_tag = next(t for t in tags if "TTFB Latency" in t.finding)
    assert perf_tag.confidence == "high"

def test_provenance_cloud_intelligence():
    from rankintel.models.schema import CloudIntelligenceEvidence, KeywordIntelligence, BacklinkIntelligence

    cloud = CloudIntelligenceEvidence(
        available=True,
        keywords=KeywordIntelligence(
            estimated_monthly_traffic=125000,
            total_keywords=4200
        ),
        backlinks=BacklinkIntelligence(
            referring_domains=850,
            domain_authority_score=78
        )
    )

    results = {
        "mcp_cloud": EngineResult(
            engine_name="mcp_cloud",
            status="success",
            cloud_intelligence=cloud
        )
    }

    tags = ProvenanceTagger.tag(results)
    assert len(tags) == 2
    traf_tag = next(t for t in tags if "Organic Search Traffic" in t.finding)
    assert "125,000 visits/mo" in traf_tag.finding
    assert traf_tag.engine == "mcp_cloud"
    assert traf_tag.confidence == "high"

    ref_tag = next(t for t in tags if "Referring Domains" in t.finding)
    assert "850" in ref_tag.finding
    assert ref_tag.engine == "mcp_cloud"
