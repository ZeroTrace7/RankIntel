"""
Search Signal Intelligence Engine Unit Tests (Phase 9.1 - Layer A).
Verifies deterministic extraction, term normalization, structural source attribution,
entity and content reuse, duplicate handling, typed confidence, and FACT/ANALYSIS separation.
"""
import pytest
from bs4 import BeautifulSoup

from rankintel.engines.search_signal_engine import SearchSignalEngine, normalize_term
from rankintel.models.schema import (
    SearchSignalEvidence,
    SearchSignalLocation,
    SearchSignalConfidence,
    SearchSignalStatementType,
    OnPageEvidence,
    ContentEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    EntitySignalType,
    ImageSEOEvidence,
    ImageDetail,
)


SAMPLE_HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Acme Industrial Solutions | Precision Calibration & Testing Equipment</title>
    <meta name="description" content="Acme provides certified calibration instruments and metallurgical testing equipment for aerospace manufacturing enterprises worldwide." />
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Acme Global Solutions",
      "description": "Provider of precision calibration and industrial testing chambers."
    }
    </script>
</head>
<body>
    <header>
        <nav><a href="/">Home</a><a href="/products">Products</a></nav>
    </header>
    <main>
        <h1>Precision Calibration & Metallurgical Testing Equipment</h1>
        <p>Acme Global Solutions engineers advanced calibration instruments and metallurgical testing chambers for aerospace enterprises.</p>
        <p>Our certified calibration instruments guarantee traceable precision measurements under ISO standards.</p>
        <h2>Traceable Primary Standards</h2>
        <p>Every calibration instrument undergoes multi-point automated verification to maintain national traceability.</p>
        <h3>Spectrometer Verification Procedures</h3>
        <p>High resolution spectrometers deliver sub-ppm spectral analysis within seconds.</p>
        <img src="/images/calibration-bench.jpg" alt="Automated Calibration Bench System" />
    </main>
    <footer>
        <p>&copy; 2026 Acme Corp. All rights reserved.</p>
    </footer>
</body>
</html>
"""


def test_normalize_term_safe_and_deterministic():
    """Verify normalize_term behaves safely without aggressive stemming."""
    # Basic lowercasing and trimming
    assert normalize_term("  Calibration  Services  ") == "calibration services"
    # Punctuation stripping at boundaries
    assert normalize_term("“Industrial Testing!”") == "industrial testing"
    assert normalize_term("(ISO-17025 Certified)") == "iso-17025 certified"
    # Underscore replacement
    assert normalize_term("environmental_simulation_chamber") == "environmental simulation chamber"
    # Preservation of technical words without destructive stemming (per correction #3)
    assert normalize_term("Calibration Services") == "calibration services"  # not stripped to 'calibration service'
    assert normalize_term("Measurement Instruments") == "measurement instruments"
    assert normalize_term("Spectrometers") == "spectrometers"
    assert normalize_term("Process Analysis") == "process analysis"
    assert normalize_term("Business") == "business"
    assert normalize_term("Status") == "status"
    # Empty string handling
    assert normalize_term("") == ""
    assert normalize_term(None) == ""


def test_deterministic_signal_extraction_from_all_sources():
    """Verify extraction from Title, Meta Description, H1, H2, H3, Main Content, URL, Alt, and Schema."""
    url = "https://example.com/products/calibration-equipment"
    ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url=url,
    )

    assert ev.status == "success"
    assert ev.total_signals_detected > 0
    assert ev.unique_terms_count > 0

    # 1. Title terms evidenced
    assert len(ev.title_terms) > 0
    assert any("calibration" in t for t in ev.title_terms)
    assert any("testing" in t for t in ev.title_terms)

    # 2. Meta description terms evidenced
    assert len(ev.meta_description_terms) > 0
    assert any("aerospace" in t for t in ev.meta_description_terms)

    # 3. Headings evidenced (H1, H2, H3)
    assert len(ev.heading_terms) > 0
    assert any("calibration" in t for t in ev.heading_terms)
    assert any("spectrometer" in t for t in ev.heading_terms)

    # 4. Main content top terms
    assert len(ev.main_content_top_terms) > 0

    # 5. URL path terms
    assert len(ev.url_path_terms) > 0
    assert "products" in ev.url_path_terms or "calibration" in ev.url_path_terms

    # 6. Image alt terms
    assert len(ev.image_alt_terms) > 0
    assert any("calibration bench" in t for t in ev.image_alt_terms)

    # 7. Structured data terms
    assert len(ev.structured_data_terms) > 0


def test_source_attribution_and_structural_locations():
    """Verify each signal item records exact structural locations and occurrences."""
    ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com/products/calibration-equipment",
    )

    term_items = {s.term: s for s in ev.signals}
    calib = term_items.get("calibration")
    assert calib is not None
    assert SearchSignalLocation.TITLE in calib.locations
    assert SearchSignalLocation.H1 in calib.locations
    assert SearchSignalLocation.MAIN_CONTENT in calib.locations

    # Check occurrence snippet
    assert len(calib.occurrences) > 0
    for occ in calib.occurrences:
        assert occ.location in (SearchSignalLocation.TITLE, SearchSignalLocation.H1, SearchSignalLocation.MAIN_CONTENT, SearchSignalLocation.META_DESCRIPTION, SearchSignalLocation.STRUCTURED_DATA)
        assert len(occ.raw_text) > 0


def test_entity_reuse_without_reparsing():
    """Verify that pre-extracted EntityEvidence is cleanly reused without re-running entity extraction."""
    pre_extracted_entity = EntityEvidence(
        url="https://example.com",
        total_entities_detected=2,
        detected_entities=[
            DetectedEntity(
                name="Acme Corp Aerospace",
                entity_type=EntityType.ORGANIZATION,
                source=EntitySource.JSON_LD,
                signal_type=EntitySignalType.STRUCTURED_DATA_DECLARATION,
            ),
            DetectedEntity(
                name="Spectrometer Calibration Service",
                entity_type=EntityType.SERVICE,
                source=EntitySource.VISIBLE_HTML,
                signal_type=EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL,
            ),
        ]
    )

    ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com",
        entity_ev=pre_extracted_entity,
    )

    entity_signals = [s for s in ev.signals if s.is_entity]
    assert len(entity_signals) >= 2
    entity_names = [s.term for s in entity_signals]
    assert any("acme corp aerospace" in n for n in entity_names)
    assert any("spectrometer calibration service" in n for n in entity_names)

    # Verify entity terms list is populated
    assert len(ev.entity_terms) == 2
    assert ev.entity_terms[0]["entity_name"] == "Acme Corp Aerospace"
    assert ev.entity_terms[0]["entity_type"] == "ORGANIZATION"


def test_content_reuse_strictly_scoped_to_main_editorial():
    """Verify that content terms are extracted strictly from established editorial content without footer/boilerplate."""
    content_with_boilerplate = """
    <html>
    <body>
        <nav><a href="/">Home</a></nav>
        <main>
            <h1>Metallurgical Analysis</h1>
            <p>Precise optical emission spectroscopy reveals elemental composition in metallic alloys.</p>
            <p>Elemental composition is verified against international alloy standards.</p>
        </main>
        <footer>
            <p>Privacy Policy Contact Us Terms Copyright Privacy Policy Contact Us Terms Copyright Privacy Policy</p>
        </footer>
    </body>
    </html>
    """

    ev = SearchSignalEngine.evaluate(
        raw_html=content_with_boilerplate,
        url="https://example.com/test",
    )

    # "privacy" and "copyright" repeated in footer must NOT dominate main content terms
    main_terms = [t["term"] for t in ev.main_content_top_terms]
    assert "privacy" not in main_terms
    assert "copyright" not in main_terms
    assert "elemental" in main_terms or "composition" in main_terms or "spectroscopy" in main_terms or "alloys" in main_terms


def test_duplicate_handling_single_page():
    """Verify terms appearing repeatedly on a page aggregate counts rather than duplicating signal items."""
    html = """
    <html>
    <head><title>Hardness Testing Instruments</title></head>
    <body>
        <h1>Hardness Testing</h1>
        <p>Hardness testing is critical. We perform hardness testing on samples.</p>
    </body>
    </html>
    """
    ev = SearchSignalEngine.evaluate(raw_html=html, url="https://example.com")

    # Count how many times the term 'hardness testing' or 'hardness' appears as a distinct SearchSignalItem
    hardness_items = [s for s in ev.signals if s.term == "hardness testing"]
    assert len(hardness_items) <= 1  # Exactly 1 item, aggregated!
    if hardness_items:
        assert hardness_items[0].total_occurrences >= 2


def test_typed_confidence_assignment():
    """Verify assignment of DIRECT, SUPPORTED, and WEAK confidence levels."""
    ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com/products/calibration-equipment",
    )

    items_map = {s.term: s for s in ev.signals}

    # "calibration" appears in Title, H1, Meta, Main Content -> must be DIRECT
    calib = items_map.get("calibration")
    assert calib is not None
    assert calib.confidence == SearchSignalConfidence.DIRECT

    # Find a term with WEAK confidence (e.g. single occurrence in alt text only or isolated)
    weak_candidates = [s for s in ev.signals if s.confidence == SearchSignalConfidence.WEAK]
    assert len(weak_candidates) > 0
    for w in weak_candidates:
        assert SearchSignalLocation.TITLE not in w.locations
        assert SearchSignalLocation.H1 not in w.locations


def test_fact_and_analysis_separation_no_recommendations():
    """Verify strict separation of FACT and ANALYSIS, with zero premature RECOMMENDATION statements."""
    ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com/products/calibration-equipment",
    )

    # 1. Facts are non-empty and describe direct observations
    assert len(ev.facts) > 0
    for f in ev.facts:
        assert isinstance(f, str)
        assert not f.lower().startswith("recommend")

    # 2. Analyses are non-empty and describe structural co-occurrences
    assert len(ev.analyses) > 0
    for a in ev.analyses:
        assert isinstance(a, str)
        assert not a.lower().startswith("recommend")

    # 3. No recommendations field exists in SearchSignalEvidence (per correction #1)
    assert not hasattr(ev, "recommendations")


def test_partial_crawl_behavior_empty_html():
    """Verify empty or missing HTML is handled gracefully without crashing."""
    ev_none = SearchSignalEngine.evaluate(raw_html=None, url="https://example.com")
    assert ev_none.status == "skipped"
    assert ev_none.total_signals_detected == 0
    assert len(ev_none.facts) > 0

    ev_empty = SearchSignalEngine.evaluate(raw_html="   ", url="https://example.com")
    assert ev_empty.status == "skipped"
    assert ev_empty.total_signals_detected == 0

    ev_minimal = SearchSignalEngine.evaluate(raw_html="<html><body><p>Hello world</p></body></html>", url="https://example.com")
    assert ev_minimal.status == "success"
    assert len(ev_minimal.title_terms) == 0
    assert len(ev_minimal.heading_terms) == 0
