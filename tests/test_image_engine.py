"""
Unit & Integration Tests for Image SEO & Visual Search Engine (Phase 7.3).
"""
import pytest
from unittest.mock import patch, MagicMock
import httpx

from rankintel.engines.image_engine import ImageEngine
from rankintel.models.schema import (
    ImageFindingSeverity,
    ImageSeoEvidence,
    ImageDetail,
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
)
from rankintel.reporters.markdown import MarkdownReporter


SAMPLE_HTML_MIXED_IMAGES = """
<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <header>
        <!-- Hero image with loading="lazy" (defect) and missing width/height -->
        <img src="/images/hero-banner.jpg" alt="Company Hero Banner" loading="lazy">
    </header>
    <main>
        <!-- Missing alt and legacy format -->
        <img src="/images/IMG_5921.png">
        
        <!-- Generic alt -->
        <img src="/images/logo.png" alt="logo" width="200" height="50">
        
        <!-- Decorative alt (valid) -->
        <img src="/images/divider.svg" alt="" width="800" height="2">
        
        <!-- Modern format, responsive picture, good alt, explicit dimensions -->
        <picture>
            <source srcset="/images/pressure-gauge.avif" type="image/avif">
            <img src="/images/pressure-gauge.webp" alt="High Precision Pressure Gauge Calibration" width="600" height="400" loading="lazy">
        </picture>
    </main>
</body>
</html>
"""


class TestImageEngine:
    @pytest.fixture
    def engine(self):
        return ImageEngine()

    def test_evaluate_individual_images(self, engine):
        evidence = engine.audit_html(SAMPLE_HTML_MIXED_IMAGES, base_url="https://example.com")
        assert evidence.total_images == 5

        # 1. Hero image check
        hero = evidence.images[0]
        assert hero.src == "https://example.com/images/hero-banner.jpg"
        assert hero.loading == "lazy"
        assert hero.has_dimensions is False
        assert any(f.code == "IMG_LAZY_HERO_CONFLICT" for f in evidence.findings)

        # 2. Missing alt check
        img2 = evidence.images[1]
        assert img2.alt_quality == "missing"
        assert img2.has_alt is False
        assert any(f.code == "IMG_MISSING_ALT" for f in evidence.findings)

        # 3. Generic alt check
        img3 = evidence.images[2]
        assert img3.alt_quality == "generic"
        assert img3.has_dimensions is True
        assert any(f.code == "IMG_GENERIC_ALT" for f in evidence.findings)

        # 4. Decorative alt check
        img4 = evidence.images[3]
        assert img4.is_decorative is True
        assert img4.alt_quality == "decorative"

        # 5. Modern format & responsive check
        img5 = evidence.images[4]
        assert img5.is_modern_format is True
        assert img5.is_in_picture_tag is True
        assert img5.alt_quality == "good"
        assert img5.has_dimensions is True

    def test_clean_modern_images_score_high(self, engine):
        clean_html = """
        <html>
        <body>
            <img src="/img/cal-lab.webp" alt="NABL Calibration Laboratory Facility" width="800" height="600" fetchpriority="high">
            <img src="/img/meter.avif" alt="Digital Multimeter Testing Bench" width="400" height="300" loading="lazy">
        </body>
        </html>
        """
        evidence = engine.audit_html(clean_html, base_url="https://example.com")
        assert evidence.total_images == 2
        assert evidence.images_with_alt == 2
        assert evidence.images_with_dimensions == 2
        assert evidence.modern_format_count == 2
        assert evidence.score >= 90
        assert evidence.grade == "A"
        assert len(evidence.findings) == 0

    def test_empty_html_returns_defaults(self, engine):
        evidence = engine.audit_html("")
        assert evidence.total_images == 0
        assert evidence.score == 100
        assert evidence.grade == "A"

    @pytest.mark.anyio
    async def test_async_audit_url_with_mock(self, engine):
        async def handler(request: httpx.Request):
            return httpx.Response(200, headers={"Content-Type": "text/html"}, text=SAMPLE_HTML_MIXED_IMAGES)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            evidence = await engine.audit_url("https://example.com", client=client)

        assert evidence.total_images == 5
        assert evidence.images_with_alt >= 3

    def test_sync_audit_url_mock(self, engine):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_HTML_MIXED_IMAGES

        with patch("httpx.Client.get", return_value=mock_resp):
            evidence = engine.audit_url_sync("https://example.com")

        assert evidence.total_images == 5


class TestMarkdownReporterImageSeoIntegration:
    def test_reporter_renders_image_seo_section(self):
        engine = ImageEngine()
        img_evidence = engine.audit_html(SAMPLE_HTML_MIXED_IMAGES, base_url="https://example.com")

        report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-02T20:00:00",
            overall_health_score=85,
            image_seo_score=img_evidence.score,
            unified_on_page=OnPageEvidence(url="https://example.com", status_code=200, title="Example"),
            unified_robots=RobotsEvidence(found=True),
            unified_schema=SchemaEvidence(),
            unified_geo=GeoAeoEvidence(),
            unified_image_seo=img_evidence,
        )

        reporter = MarkdownReporter()
        md = reporter.render(report)

        assert "IMAGE SEO & VISUAL SEARCH INTELLIGENCE" in md
        assert "Image Optimization Score" in md
        assert "Alt Attribute Coverage" in md
        assert "Layout Stability" in md
        assert "Modern Format Delivery" in md
