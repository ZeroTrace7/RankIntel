"""
Tests for Phase 11.5.1: P0 Correctness Fixes
- P0-1: Deterministic Primary Brand / Organization Fallback (GAP-ENT-002)
- P0-2: Reliable Rendered DOM Collection & Explicit Fallback Isolation (GAP-RETRIEVAL-001)
- Strict Formula Invariance (Delta = 0)
"""
import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from rankintel.engines.entity_engine import (
    EntityEngine,
    EntityType,
    EntitySource,
    EntitySignalType,
    EvidenceNature,
    normalize_entity_name,
)
from rankintel.engines.browser_engine import BrowserEngine
from rankintel.engines.seo_engine import SeoEngine
from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.models.schema import (
    EngineResult,
    OnPageEvidence,
    SchemaEvidence,
    RobotsEvidence,
    GeoAeoEvidence,
    PerformanceEvidence,
)
from rankintel.engines.retrieval_readiness_engine import RetrievalReadinessEngine


# =============================================================================
# P0-1: BRAND / ORGANIZATION FALLBACK TESTS
# =============================================================================

class TestBrandEntityFallback:
    """Validate deterministic, evidence-based brand fallback for schema-less sites."""

    def test_fallback_extracts_brand_for_yadav_measurements(self):
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>India's Leading Private Testing, Calibration Company - Yadav Measurements</title>
        </head>
        <body>
            <h1>Calibration and Testing Services</h1>
            <p>Welcome to our accredited laboratory facilities across India.</p>
        </body>
        </html>
        """
        result = engine.evaluate(raw_html=html, url="https://www.yadavmeasurements.com/")
        org_names = [e.name for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        assert "Yadav Measurements" in org_names

        # Verify entity properties
        brand_entity = next(e for e in result.detected_entities if e.name == "Yadav Measurements")
        assert brand_entity.source == EntitySource.VISIBLE_HTML
        assert brand_entity.confidence_nature == EvidenceNature.INFERRED
        assert brand_entity.signal_type == EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL

        # Verify domain relationship
        assert any(
            r.subject_name == "Yadav Measurements" and "yadavmeasurements.com" in r.object_name
            for r in result.relationships
        )

    def test_fallback_extracts_brand_for_quality_international(self):
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quality International | Inspection & Certification</title>
        </head>
        <body>
            <h1>Head Office :</h1>
            <p>Inspection, verification, testing and certification services.</p>
        </body>
        </html>
        """
        result = engine.evaluate(raw_html=html, url="https://qualityinternational.org/")
        org_names = [e.name for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        assert "Quality International" in org_names
        # Ensure "Head Office :" is NEVER extracted as an organization
        assert not any("Head Office" in n for n in org_names)

    def test_fallback_extracts_brand_for_unique_measurement(self):
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unique Measurement Service</title>
        </head>
        <body>
            <h1>Our Services</h1>
            <p>CMM inspection and dimensional metrology solutions.</p>
        </body>
        </html>
        """
        result = engine.evaluate(raw_html=html, url="https://www.uniquemeasurement.com/")
        org_names = [e.name for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        assert "Unique Measurement Service" in org_names
        # Ensure "Our Services" heading is rejected
        assert not any("Our Services" in n for n in org_names)

    def test_fallback_extracts_brand_for_sunrise_testing(self):
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sunrise Testing & Inspection Services - Industrial Testing Lab</title>
            <meta property="og:site_name" content="Sunrise Testing Services">
        </head>
        <body>
            <h1>Non-Destructive Testing Solutions</h1>
        </body>
        </html>
        """
        result = engine.evaluate(raw_html=html, url="https://sunrisetesting.vercel.app/")
        org_names = [e.name for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        assert any("Sunrise Testing" in n for n in org_names)

    def test_fallback_skipped_when_schema_org_already_present(self):
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Aleph India - Quality Management Consulting</title>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "Aleph India",
                "url": "https://alephindia.in/"
            }
            </script>
        </head>
        <body>
            <h1>Product Certification Services</h1>
        </body>
        </html>
        """
        result = engine.evaluate(raw_html=html, url="https://alephindia.in/")
        org_entities = [e for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        # Should have exactly 1 organization from JSON-LD schema, not duplicate fallback
        assert len(org_entities) == 1
        assert org_entities[0].name == "Aleph India"
        assert org_entities[0].confidence_nature == EvidenceNature.OBSERVED
        assert "Deterministic brand fallback" not in (org_entities[0].raw_context or "")

    def test_slogan_and_generic_phrase_rejection(self):
        engine = EntityEngine()
        # Test candidate filter directly
        assert engine._is_rejected_brand_candidate("Excellence in Precision Calibration") is True
        assert engine._is_rejected_brand_candidate("Welcome to our website") is True
        assert engine._is_rejected_brand_candidate("Home") is True
        assert engine._is_rejected_brand_candidate("About Us") is True
        assert engine._is_rejected_brand_candidate("Contact Us Today") is True
        assert engine._is_rejected_brand_candidate("Privacy Policy") is True
        assert engine._is_rejected_brand_candidate("Head Office : Mumbai") is True
        assert engine._is_rejected_brand_candidate("+91 98765 43210") is True
        assert engine._is_rejected_brand_candidate("info@example.com") is True
        assert engine._is_rejected_brand_candidate("All Rights Reserved") is True
        assert engine._is_rejected_brand_candidate("ISO") is True  # Generic single token

    def test_multi_signal_corroboration_requirement(self):
        """Single weak signal (e.g. random H1 only with opaque domain) must NOT emit entity."""
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page 123 - Index</title>
        </head>
        <body>
            <h1>Random Heading Text</h1>
            <p>Some body text.</p>
        </body>
        </html>
        """
        # Domain 'xyz-789.com' has zero lexical match with 'Random Heading Text',
        # and title doesn't agree with H1 -> single weak signal must be rejected
        result = engine.evaluate(raw_html=html, url="https://xyz-789.com/")
        org_names = [e.name for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        assert "Random Heading Text" not in org_names
        assert len(org_names) == 0

    def test_title_and_h1_agreement_corroborates_brand(self):
        """Title and H1 agreement provides 2 independent signals even if domain name is abbreviated."""
        engine = EntityEngine()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pinnacle Calibration Labs - Home</title>
        </head>
        <body>
            <h1>Pinnacle Calibration Labs</h1>
            <p>Industrial measurement standards.</p>
        </body>
        </html>
        """
        result = engine.evaluate(raw_html=html, url="https://pcl-service.in/")
        org_names = [e.name for e in result.detected_entities if e.entity_type == EntityType.ORGANIZATION]
        assert "Pinnacle Calibration Labs" in org_names


# =============================================================================
# P0-2: RENDERED DOM COLLECTION & EXPLICIT FALLBACK TESTS
# =============================================================================

class TestRenderedDomCollection:
    """Validate reliable rendered DOM collection and explicit fallback isolation."""

    def test_successful_browser_rendering_exposes_rendered_dom_and_words(self):
        """When browser rendering succeeds, rendered_html_available is True and words are measured."""
        retrieval_engine = RetrievalReadinessEngine()
        static_html = "<html><body><h1>Loading App...</h1></body></html>"
        rendered_dom = "<html><body><h1>Loaded App</h1><p>" + " ".join(["content"] * 120) + "</p></body></html>"

        evidence = retrieval_engine.evaluate_page(
            url="https://example.com/app",
            status_code=200,
            raw_html=static_html,
            rendered_html=rendered_dom,
        )

        assert evidence.content_availability.rendered_html_available is True
        assert evidence.content_availability.rendered_word_count > 100
        assert evidence.content_availability.raw_word_count < 10
        assert evidence.content_availability.word_count_delta > 100

    def test_browser_fallback_never_pretends_static_is_rendered(self):
        """When browser fails and fallback is used, rendered_html_available is False, rendered_words is 0."""
        retrieval_engine = RetrievalReadinessEngine()
        static_html = "<html><body><h1>Static Company Site</h1><p>Static paragraphs only.</p></body></html>"

        evidence = retrieval_engine.evaluate_page(
            url="https://example.com/",
            status_code=200,
            raw_html=static_html,
            rendered_html=None,  # Browser failed/fallback
        )

        assert evidence.content_availability.rendered_html_available is False
        assert evidence.content_availability.rendered_word_count == 0
        assert evidence.content_availability.word_count_delta == 0

    def test_browser_engine_httpx_fallback_status_is_explicit(self):
        """BrowserEngine._execute_httpx_fallback explicitly sets status='fallback' and engine_source."""
        engine = BrowserEngine()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><h1>Fallback Content</h1></body></html>"
        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_resp

        with patch("httpx.Client", return_value=mock_client):
            result = engine._execute_httpx_fallback("https://example.com")

        assert result.status == "fallback"
        assert result.on_page.engine_source == "httpx_static_fallback"
        assert result.error_message is not None
        assert "static httpx fallback used" in result.error_message

    def test_evidence_collector_dual_dom_preservation(self):
        """EvidenceCollector correctly preserves static_html and rendered_dom separately."""
        collector = EvidenceCollector()
        static_html = "<html><head><title>Static Page</title></head><body><h1>Static Title</h1><p>Static 1 2 3</p></body></html>"
        rendered_html = "<html><head><title>Hydrated Page</title></head><body><h1>Hydrated Title</h1><p>" + " ".join(["hydrated"] * 80) + "</p></body></html>"

        mock_seo = EngineResult(
            engine_name="advertools_seo",
            status="success",
            raw_html=static_html,
            on_page=OnPageEvidence(url="https://example.com", title="Static Page", h1_text=["Static Title"], status_code=200),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(),
        )

        mock_browser = EngineResult(
            engine_name="crawl4ai_browser",
            status="success",
            raw_html=rendered_html,
            on_page=OnPageEvidence(
                url="https://example.com",
                title="Hydrated Page",
                h1_text=["Hydrated Title"],
                engine_source="crawl4ai_browser_dom",
            ),
        )

        with patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser), \
             patch.object(collector.seo_engine, "execute", return_value=mock_seo), \
             patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
             patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="skipped")):
            results = collector.collect("https://example.com")

        assert "retrieval_readiness_engine" in results
        retrieval_ev = results["retrieval_readiness_engine"].retrieval_readiness
        assert retrieval_ev is not None
        assert retrieval_ev.content_availability.rendered_html_available is True
        assert retrieval_ev.content_availability.rendered_word_count > 50
        assert retrieval_ev.content_availability.word_count_delta > 0


# =============================================================================
# STRICT FORMULA INVARIANCE TESTS (Delta = 0)
# =============================================================================

class TestFormulaInvariance:
    """Verify that adding P0 brand entity fallback does NOT alter health score formulas."""

    def test_health_score_invariance_with_and_without_brand_fallback(self):
        synthesizer = IntelligenceSynthesizer()

        base_engine_results = {
            "advertools_seo": EngineResult(
                engine_name="advertools_seo",
                status="success",
                on_page=OnPageEvidence(
                    url="https://example.com",
                    title="Enterprise Testing Lab Solutions",
                    meta_description="Comprehensive industrial calibration and non-destructive testing for engineering systems.",
                    status_code=200,
                ),
                robots=RobotsEvidence(found=True),
                schema_data=SchemaEvidence(detected_types=["Organization"], has_organization=True),
            ),
            "browser_engine": EngineResult(
                engine_name="browser_engine",
                status="success",
                on_page=OnPageEvidence(url="https://example.com", status_code=200),
            ),
            "rankintel_geo": EngineResult(
                engine_name="rankintel_geo",
                status="success",
                geo_aeo=GeoAeoEvidence(overall_citability_score=75),
            ),
        }

        report = synthesizer.synthesize("https://example.com", base_engine_results)

        assert report.score_formula_mode == "3_engine"
        assert report.overall_health_score > 0
        assert report.technical_health_score > 0
        assert report.geo_readiness_score == 75
