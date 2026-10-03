"""
Integration tests for RankIntel Entity Intelligence Pipeline (Phase 8.2).
"""
import pytest
from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.models.schema import (
    EngineResult,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    CloudIntelligenceEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    VisibleStructuredComparison,
    EntityAlignmentStatus,
    SiteCrawlResult,
    CrawlRecord,
    CrawlStatus,
)
from rankintel.analyzers.entity_analyzer import SiteEntityAnalyzer


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Quality Testing Corp - Calibration Services</title>
    <meta name="description" content="Certified calibration services for industrial laboratories and manufacturing plants worldwide.">
    <meta property="og:site_name" content="Quality Testing Corp">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Quality Testing Corp",
        "telephone": "+1-800-555-TEST",
        "sameAs": ["https://twitter.com/qualitytest"]
    }
    </script>
</head>
<body>
    <main>
        <h1>Industrial Calibration & Testing</h1>
        <p>Providing precision calibration services across multiple industries.</p>
    </main>
    <footer>
        <p>&copy; 2026 Quality Testing Corp. All rights reserved.</p>
    </footer>
</body>
</html>
"""


def test_evidence_collector_entity_engine():
    """Verify EvidenceCollector invokes EntityEngine and populates entity evidence."""
    collector = EvidenceCollector()
    assert hasattr(collector, "entity_engine")

    # Mock engine results to isolate collector assembly
    results = collector.collect("https://qualitytesting.com")
    assert "entity_engine" in results
    ent_res = results["entity_engine"]
    assert ent_res.status in ("success", "skipped")
    assert ent_res.entity is not None


def test_synthesizer_unified_entity_and_provenance():
    """Verify synthesizer unifies entity evidence, records provenance, and preserves formula invariance."""
    synthesizer = IntelligenceSynthesizer()

    on_page = OnPageEvidence(
        url="https://qualitytesting.com",
        title="Quality Testing Corp - Calibration",
        title_length=35,
        meta_description="Certified calibration services for industrial laboratories.",
        meta_desc_length=60,
        h1_count=1,
        h1_text=["Industrial Calibration"],
        word_count=500,
    )

    entity_ev = EntityEvidence(
        url="https://qualitytesting.com",
        total_entities_detected=2,
        detected_entities=[
            DetectedEntity(
                entity_type=EntityType.ORGANIZATION,
                name="Quality Testing Corp",
                source=EntitySource.JSON_LD,
            ),
            DetectedEntity(
                entity_type=EntityType.ORGANIZATION,
                name="Quality Testing Corp",
                source=EntitySource.VISIBLE_HTML,
            ),
        ],
        structured_vs_visible=[
            VisibleStructuredComparison(
                entity_type=EntityType.ORGANIZATION,
                attribute_name="organization_name",
                structured_value="Quality Testing Corp",
                visible_value="Quality Testing Corp",
                alignment_status=EntityAlignmentStatus.EXACT_MATCH,
                notes="Exact character match.",
            )
        ],
    )

    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=on_page,
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["Organization"], has_organization=True),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(overall_citability_score=75, llms_txt_found=True),
        ),
        "performance_engine": EngineResult(
            engine_name="performance_engine",
            status="success",
            performance=PerformanceEvidence(overall_performance_score=85, ttfb_ms=450.0),
        ),
        "entity_engine": EngineResult(
            engine_name="entity_engine",
            status="success",
            entity=entity_ev,
        ),
    }

    report = synthesizer.synthesize("https://qualitytesting.com", engine_results)

    # 1. Unified entity must be attached
    assert report.unified_entity is not None
    assert report.unified_entity.total_entities_detected == 2
    assert len(report.unified_entity.detected_entities) == 2

    # 2. Formula invariance: standard 4_engine mode must remain unchanged
    assert report.score_formula_mode == "4_engine"
    assert report.overall_health_score > 0

    # 3. Provenance tags must include entity findings
    entity_tags = [t for t in report.provenance if t.engine == "entity_engine"]
    assert len(entity_tags) >= 1
    assert any("Entity Detection" in t.finding for t in entity_tags)


def test_conflict_divergent_organization_identity():
    """Verify conflict detection when structured data and visible branding are completely disjoint."""
    synthesizer = IntelligenceSynthesizer()

    on_page = OnPageEvidence(
        url="https://example.com",
        title="Acme Calibration",
        h1_count=1,
        word_count=500,
    )

    divergent_entity_ev = EntityEvidence(
        url="https://example.com",
        total_entities_detected=2,
        detected_entities=[
            DetectedEntity(
                entity_type=EntityType.ORGANIZATION,
                name="Totally Unrelated Brand Ltd",
                source=EntitySource.JSON_LD,
            ),
            DetectedEntity(
                entity_type=EntityType.ORGANIZATION,
                name="Acme Calibration",
                source=EntitySource.VISIBLE_HTML,
            ),
        ],
        structured_vs_visible=[
            VisibleStructuredComparison(
                entity_type=EntityType.ORGANIZATION,
                attribute_name="organization_name",
                structured_value="Totally Unrelated Brand Ltd",
                visible_value="Acme Calibration",
                alignment_status=EntityAlignmentStatus.DIVERGENT_IDENTITY_SUSPECTED,
                notes="Disjoint brand tokens.",
            )
        ],
    )

    engine_results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=on_page,
            robots=RobotsEvidence(found=True),
        ),
        "entity_engine": EngineResult(
            engine_name="entity_engine",
            status="success",
            entity=divergent_entity_ev,
        ),
    }

    report = synthesizer.synthesize("https://example.com", engine_results)
    divergent_conflicts = [c for c in report.conflicts_detected if c.category == "DIVERGENT_ORGANIZATION_IDENTITY"]
    assert len(divergent_conflicts) == 1
    assert divergent_conflicts[0].severity == "MEDIUM"


def test_markdown_reporter_entity_rendering():
    """Verify MarkdownReporter outputs both single-page and site-wide entity sections."""
    synthesizer = IntelligenceSynthesizer()

    on_page = OnPageEvidence(
        url="https://apexlabs.com",
        title="Apex Labs - Testing",
        h1_count=1,
        word_count=400,
    )

    entity_ev = EntityEvidence(
        url="https://apexlabs.com",
        total_entities_detected=1,
        detected_entities=[
            DetectedEntity(
                entity_type=EntityType.ORGANIZATION,
                name="Apex Testing Laboratories",
                source=EntitySource.JSON_LD,
                telephone="+1-800-555-APEX",
            )
        ],
        relationships=[],
        facts=["Detected 1 entity signals."],
    )

    report = synthesizer.synthesize("https://apexlabs.com", {
        "advertools_seo": EngineResult(engine_name="advertools_seo", status="success", on_page=on_page),
        "entity_engine": EngineResult(engine_name="entity_engine", status="success", entity=entity_ev),
    })

    # Attach a site crawl result with entity intelligence
    site_crawl = SiteCrawlResult(
        crawl_records=[
            CrawlRecord(
                url="https://apexlabs.com/",
                normalized_url="https://apexlabs.com/",
                identity_url="https://apexlabs.com/",
                crawl_status=CrawlStatus.FETCHED,
                depth=0,
                status_code=200,
                raw_html=SAMPLE_HTML,
            )
        ]
    )
    SiteEntityAnalyzer.analyze_site(site_crawl)
    report.site_crawl = site_crawl

    md_output = MarkdownReporter.render(report)

    # Check for single-page Entity Intelligence section
    assert "## 🏛️ ENTITY INTELLIGENCE & RECONCILIATION" in md_output
    assert "Apex Testing Laboratories" in md_output

    # Check for site-wide Entity Intelligence section
    assert "### 🏛️ Site-Wide Entity Intelligence & Consistency" in md_output
    assert "Primary Organization Candidate:" in md_output
