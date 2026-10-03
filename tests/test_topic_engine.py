"""
Topic Intelligence Engine Unit Tests (Phase 9.2 - Layer A).
Verifies deterministic concept grouping, phrase containment, conservative token overlap,
evidence-gated SUBTOPIC_OF relationships, entity anchoring, telemetry metrics,
and FACT/ANALYSIS separation with zero external search queries and zero arbitrary scores.
"""
import pytest
from unittest.mock import MagicMock

from rankintel.engines.topic_intelligence_engine import (
    TopicIntelligenceEngine,
    tokenize_term,
    is_word_bounded_substring,
)
from rankintel.engines.search_signal_engine import SearchSignalEngine
from rankintel.models.schema import (
    SearchSignalEvidence,
    SearchSignalItem,
    SearchSignalOccurrence,
    SearchSignalLocation,
    SearchSignalConfidence,
    SearchSignalStatementType,
    ContentEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    EntitySignalType,
    TopicEvidence,
    TopicTermMembership,
    TopicMembershipType,
    TopicRelationship,
    TopicRelationshipType,
    PageTopicIntelligence,
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
        <p>High resolution optical emission spectrometers deliver sub-ppm spectral analysis within seconds.</p>
        <img src="/images/calibration-bench.jpg" alt="Automated Calibration Bench System" />
    </main>
    <footer>
        <p>&copy; 2026 Acme Corp. All rights reserved.</p>
    </footer>
</body>
</html>
"""


def test_tokenize_term_conservative_no_stemming():
    """Verify tokenize_term extracts alphanumeric tokens without aggressive stemming."""
    tokens = tokenize_term("Precision Calibration Services")
    assert "precision" in tokens
    assert "calibration" in tokens
    assert "services" in tokens
    # No stemming of 'services' to 'service', 'calibration' to 'calibrate'
    assert "service" not in tokens
    assert "calibrate" not in tokens
    # Stopwords excluded
    tokens_sw = tokenize_term("The Verification of the Instruments")
    assert "the" not in tokens_sw
    assert "of" not in tokens_sw
    assert "verification" in tokens_sw
    assert "instruments" in tokens_sw


def test_is_word_bounded_substring():
    """Verify word-bounded substring matching avoids accidental partial token matches."""
    assert is_word_bounded_substring("calibration", "precision calibration services")
    assert is_word_bounded_substring("spectrometer", "optical emission spectrometer")
    # Substring that is not word bounded should NOT match
    assert not is_word_bounded_substring("cal", "calibration")
    assert not is_word_bounded_substring("meter", "spectrometer")
    assert not is_word_bounded_substring("", "anything")
    assert not is_word_bounded_substring("same length", "same length")


def test_deterministic_grouping_phrase_containment():
    """Verify phrase containment groups multi-word terms with their broader anchor."""
    sig_ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com/products/calibration",
    )
    topic_intel = TopicIntelligenceEngine.evaluate(
        search_signal_ev=sig_ev,
        url="https://example.com/products/calibration",
    )

    assert topic_intel.status == "success"
    assert topic_intel.total_topics_derived > 0
    assert topic_intel.total_terms_mapped > 0

    # Look for a topic group covering calibration
    calib_topics = [t for t in topic_intel.topics if "calibration" in t.normalized_name]
    assert len(calib_topics) >= 1
    calib_top = calib_topics[0]

    # Verify supporting terms include phrase containment
    member_terms = [m.normalized_term for m in calib_top.supporting_terms]
    assert any("calibration" in m for m in member_terms)
    membership_types = [m.membership_type for m in calib_top.supporting_terms]
    assert TopicMembershipType.EXACT in membership_types or TopicMembershipType.PHRASE_CONTAINMENT in membership_types


def test_entity_assisted_topic_association():
    """Verify Phase 8 detected entities anchor topics and associate related terms."""
    sig_ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com",
    )
    ent_ev = EntityEvidence(
        url="https://example.com",
        detected_entities=[
            DetectedEntity(
                name="Acme Global Solutions",
                entity_type=EntityType.ORGANIZATION,
                entity_source=EntitySource.JSON_LD,
                signal_type=EntitySignalType.STRUCTURED_DATA_DECLARATION,
            )
        ]
    )

    topic_intel = TopicIntelligenceEngine.evaluate(
        search_signal_ev=sig_ev,
        entity_ev=ent_ev,
        url="https://example.com",
    )

    # Acme Global Solutions should be represented as a concept topic
    acme_topics = [t for t in topic_intel.topics if "acme" in t.normalized_name]
    assert len(acme_topics) >= 1
    acme_top = acme_topics[0]
    assert any(m.membership_type == TopicMembershipType.ENTITY_MEMBER for m in acme_top.supporting_terms)


def test_subtopic_of_evidence_gating():
    """
    Verify SUBTOPIC_OF is strictly gated:
    Requires BOTH lexical containment AND structural hierarchy.
    Without structural hierarchy, falls back to LEXICAL_OVERLAP.
    """
    # 1. Structural hierarchy present: parent in H1/Title, child in H2/H3
    sig_item_parent = SearchSignalItem(
        term="calibration",
        raw_term="Calibration",
        category="HEADING",
        locations=[SearchSignalLocation.H1, SearchSignalLocation.TITLE],
        total_occurrences=5,
    )
    sig_item_child = SearchSignalItem(
        term="pressure calibration",
        raw_term="Pressure Calibration",
        category="HEADING",
        locations=[SearchSignalLocation.H2, SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=3,
    )

    sig_ev = SearchSignalEvidence(
        url="https://example.com",
        signals=[sig_item_parent, sig_item_child],
    )

    intel = TopicIntelligenceEngine.evaluate(
        search_signal_ev=sig_ev,
        url="https://example.com",
    )

    # Check relationships
    subtopic_rels = [r for r in intel.relationships if r.relationship_type == TopicRelationshipType.SUBTOPIC_OF]
    assert len(subtopic_rels) >= 1
    assert subtopic_rels[0].topic_a == "Pressure Calibration"
    assert subtopic_rels[0].topic_b == "Calibration"

    # 2. Structural hierarchy absent: both only in MAIN_CONTENT
    sig_item_parent2 = SearchSignalItem(
        term="spectrometer",
        raw_term="Spectrometer",
        category="CONTENT",
        locations=[SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=4,
    )
    sig_item_child2 = SearchSignalItem(
        term="optical emission spectrometer",
        raw_term="Optical Emission Spectrometer",
        category="CONTENT",
        locations=[SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=3,
    )

    sig_ev2 = SearchSignalEvidence(
        url="https://example.com",
        signals=[sig_item_parent2, sig_item_child2],
    )

    intel2 = TopicIntelligenceEngine.evaluate(
        search_signal_ev=sig_ev2,
        url="https://example.com",
    )

    # Should fall back to LEXICAL_OVERLAP because neither is in Title/H1
    lex_rels = [r for r in intel2.relationships if r.relationship_type == TopicRelationshipType.LEXICAL_OVERLAP]
    assert len(lex_rels) >= 1
    assert not any(r.relationship_type == TopicRelationshipType.SUBTOPIC_OF for r in intel2.relationships)


def test_fact_and_analysis_separation_no_recommendations():
    """Verify FACT vs ANALYSIS separation and absence of premature recommendations."""
    sig_ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com/products/calibration",
    )
    intel = TopicIntelligenceEngine.evaluate(
        search_signal_ev=sig_ev,
        url="https://example.com/products/calibration",
    )

    assert len(intel.facts) >= 2
    assert len(intel.analyses) >= 2

    # Verify FACT statements contain observable numbers
    for f in intel.facts:
        assert isinstance(f, str)
        assert any(c.isdigit() for c in f)

    # Verify ANALYSIS statements describe derived grouping
    for a in intel.analyses:
        assert isinstance(a, str)

    # Verify no recommendations attribute exists or is generated
    assert not hasattr(intel, "recommendations")
    assert not hasattr(intel, "action_items")


def test_telemetry_metrics_no_arbitrary_scores():
    """Verify topics provide deterministic telemetry metrics and NO arbitrary SEO scores."""
    sig_ev = SearchSignalEngine.evaluate(
        raw_html=SAMPLE_HTML_PAGE,
        url="https://example.com",
    )
    intel = TopicIntelligenceEngine.evaluate(
        search_signal_ev=sig_ev,
        url="https://example.com",
    )

    for top in intel.topics:
        # Telemetry metrics exist
        assert hasattr(top, "pages_count")
        assert hasattr(top, "occurrences_count")
        assert hasattr(top, "structural_presence_count")
        assert hasattr(top, "title_or_h1_presence")
        assert isinstance(top.occurrences_count, int)
        assert isinstance(top.title_or_h1_presence, bool)

        # No arbitrary scores
        assert not hasattr(top, "score")
        assert not hasattr(top, "topic_score")
        assert not hasattr(top, "seo_grade")
        assert not hasattr(top, "priority_score")


def test_partial_crawl_and_empty_inputs():
    """Verify safe execution with empty/missing inputs without crashing."""
    # None inputs
    intel_none = TopicIntelligenceEngine.evaluate(
        search_signal_ev=None,
        content_ev=None,
        entity_ev=None,
        url="",
    )
    assert intel_none.status == "skipped"
    assert intel_none.total_topics_derived == 0
    assert len(intel_none.facts) > 0

    # Empty signals
    empty_sig = SearchSignalEvidence(url="https://example.com", signals=[])
    intel_empty = TopicIntelligenceEngine.evaluate(
        search_signal_ev=empty_sig,
        url="https://example.com",
    )
    assert intel_empty.status == "success"
    assert intel_empty.total_topics_derived == 0
