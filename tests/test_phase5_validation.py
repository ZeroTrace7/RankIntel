"""
Phase 5 focused regression tests for confirmed fixes:
1. BrowserEngine extracts title and canonical from soup even when title param was empty.
2. BrowserEngine _parse_schema extracts has_organization, has_author, and sameas_urls.
3. Synthesizer OnPage reconciliation preserves title, meta_description, and canonical from SEO engine.
4. Schema.org ProfessionalService is recognized as Organization across SeoEngine and TrustEvaluator.
5. Soft-404 HTML pages on /llms.txt with zero markdown elements are rejected.
6. PerformanceEngine local probe with failed network timings returns source='unavailable' and score=0.
"""
from bs4 import BeautifulSoup
from unittest.mock import patch, MagicMock

from rankintel.engines.browser_engine import BrowserEngine
from rankintel.engines.seo_engine import SeoEngine
from rankintel.engines.performance_engine import PerformanceEngine
from rankintel.adapters.geo_optimizer_adapter import GeoOptimizerAdapter
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.analyzers.trust_evaluator import TrustEvaluator
from rankintel.models.schema import (
    OnPageEvidence,
    SchemaEvidence,
    EngineResult,
    RobotsEvidence,
)


def test_browser_engine_extracts_title_and_canonical_when_initially_empty():
    engine = BrowserEngine()
    html = """<!DOCTYPE html>
    <html>
    <head>
        <title>TCR Engineering Services | Materials Testing</title>
        <link rel="canonical" href="https://www.tcreng.com/">
        <meta name="description" content="Leading material testing lab.">
    </head>
    <body>
        <h1>Materials fail. Evidence doesn't.</h1>
    </body>
    </html>"""
    soup = BeautifulSoup(html, "html.parser")
    # Pass empty title to simulate httpx fallback or missing meta.title
    on_page = engine._build_on_page(soup, "https://www.tcreng.com/", "", [], [], 0.1)

    assert on_page.title == "TCR Engineering Services | Materials Testing"
    assert on_page.title_length == len("TCR Engineering Services | Materials Testing")
    assert on_page.canonical_url == "https://www.tcreng.com/"
    assert on_page.h1_count == 1


def test_browser_engine_schema_extracts_org_and_sameas():
    engine = BrowserEngine()
    html = """<!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "ProfessionalService",
            "name": "Aleph India",
            "sameAs": [
                "https://www.facebook.com/InAleph/",
                "https://twitter.com/inaleph"
            ]
        }
        </script>
    </head>
    <body></body>
    </html>"""
    soup = BeautifulSoup(html, "html.parser")
    schema_ev = engine._parse_schema(soup)

    assert "ProfessionalService" in schema_ev.detected_types
    assert schema_ev.has_organization is True
    assert len(schema_ev.sameas_urls) == 2


def test_synthesizer_on_page_reconciliation_preserves_title_desc_canonical():
    synth = IntelligenceSynthesizer()

    # Browser result has empty title and missing canonical
    browser_on_page = OnPageEvidence(
        url="https://example.com",
        status_code=200,
        title="",
        title_length=0,
        meta_description="",
        meta_desc_length=0,
        canonical_url=None,
    )
    # SEO result has extracted title, meta_description, and canonical
    seo_on_page = OnPageEvidence(
        url="https://example.com",
        status_code=200,
        title="Example Domain Title",
        title_length=20,
        meta_description="A comprehensive description that is valid length for search snippets.",
        meta_desc_length=68,
        canonical_url="https://example.com/",
    )

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=seo_on_page,
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["Organization"]),
        ),
        "browser_engine": EngineResult(
            engine_name="browser_engine",
            status="success",
            on_page=browser_on_page,
            schema_data=SchemaEvidence(detected_types=["Organization"]),
        ),
    }

    report = synth.synthesize("https://example.com", results)
    assert report.unified_on_page.title == "Example Domain Title"
    assert report.unified_on_page.title_length == 20
    assert report.unified_on_page.meta_description == "A comprehensive description that is valid length for search snippets."
    assert report.unified_on_page.canonical_url == "https://example.com/"


def test_professional_service_recognized_as_organization_in_all_engines():
    # 1. SeoEngine
    seo_engine = SeoEngine()
    html = """<!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "ProfessionalService", "name": "Test Firm"}
        </script>
    </head>
    <body></body>
    </html>"""
    mock_resp = MagicMock(status_code=200, text=html, history=[], headers={})
    with patch("requests.get", return_value=mock_resp):
        _, schema_ev = seo_engine.audit_static_page("https://test.com")
    assert schema_ev.has_organization is True

    # 2. TrustEvaluator
    on_page = OnPageEvidence(url="https://test.com")
    trust = TrustEvaluator.evaluate(
        url="https://test.com",
        on_page=on_page,
        schema=schema_ev,
        raw_html=html,
    )
    ident_layer = trust.layers["identity"]
    assert "Organization / LocalBusiness Structured Data" in ident_layer.signals_found


def test_geo_adapter_rejects_soft_404_html_llms_txt():
    adapter = GeoOptimizerAdapter()

    # Simulate an audit_llms_txt result where an HTML soft-404 returned HTTP 200,
    # so found=True, but zero markdown structure (no H1, no links, no sections)
    mock_llms_result = MagicMock(
        found=True,
        has_h1=False,
        has_links=False,
        has_sections=False,
        has_blockquote=False,
        has_description=False,
        has_full=True,
        validation_warnings=["soft-404"],
    )

    with patch("rankintel.adapters.geo_optimizer_adapter.audit_llms_txt", return_value=mock_llms_result):
        with patch.object(adapter, "_run_citability", wraps=adapter._run_citability):
            cit_mock = MagicMock(total_score=40, methods=[])
            with patch("rankintel.adapters.geo_optimizer_adapter.audit_citability", return_value=cit_mock):
                geo_ev = adapter._run_citability("https://soft404site.com", raw_html="<html><body>404 Page</body></html>")
                assert geo_ev.llms_txt_found is False
                assert geo_ev.llms_full_found is False


def test_performance_engine_empty_timings_returns_unavailable():
    engine = PerformanceEngine()

    # Simulate all network probe requests failing (e.g. host unreachable)
    with patch("requests.get", side_effect=Exception("Connection refused")):
        perf = engine._measure_local_performance("https://unreachable-host.local")

    assert perf.source == "unavailable"
    assert perf.overall_performance_score == 0
    assert perf.ttfb_ms == 0.0
    assert perf.passed_audit is False
    assert any("probe failed" in note.lower() for note in perf.notes)
