"""
Query-Page Mapping Engine Unit Tests (Phase 9.3 - Layer A).
Verifies deterministic on-site concept-to-page mapping, evidence location attribution,
DIRECT / SUPPORTED / WEAK confidence tiers, bounded snippets, provenance tagging,
and strict FACT / ANALYSIS separation with zero external search queries or ranking claims.
"""
import pytest
from unittest.mock import MagicMock

from rankintel.engines.query_page_mapping_engine import (
    QueryPageMappingEngine,
    tokenize_concept,
)
from rankintel.models.schema import (
    SearchSignalEvidence,
    SearchSignalItem,
    SearchSignalOccurrence,
    SearchSignalLocation,
    SearchSignalConfidence,
    PageTopicIntelligence,
    TopicEvidence,
    TopicTermMembership,
    TopicMembershipType,
    ContentEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    EntitySignalType,
    OnPageEvidence,
    QueryPageEvidence,
    PageQueryEvidence,
)


def test_tokenize_concept():
    """Verify tokenize_concept extracts clean content words and excludes stopwords."""
    tokens = tokenize_concept("Precision Calibration Services")
    assert "precision" in tokens
    assert "calibration" in tokens
    assert "services" in tokens
    # Stopwords excluded
    sw_tokens = tokenize_concept("The State of Calibration in Laboratory")
    assert "the" not in sw_tokens
    assert "of" not in sw_tokens
    assert "in" not in sw_tokens
    assert "calibration" in sw_tokens
    assert "laboratory" in sw_tokens


def test_empty_or_none_evidence_handling():
    """Verify engine handles empty or None evidence gracefully without exceptions."""
    result = QueryPageMappingEngine.evaluate(url="https://example.com/test")
    assert isinstance(result, PageQueryEvidence)
    assert result.status == "skipped"
    assert result.total_concepts_mapped == 0
    assert result.mapped_concepts == []
    assert len(result.facts) >= 1


def test_deterministic_direct_evidence_strength():
    """Verify concepts in Title or H1 receive DIRECT evidence strength."""
    sig_item = SearchSignalItem(
        term="precision calibration",
        raw_term="Precision Calibration",
        category="heading",
        locations=[SearchSignalLocation.TITLE, SearchSignalLocation.H1, SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=4,
        confidence=SearchSignalConfidence.DIRECT,
        occurrences=[
            SearchSignalOccurrence(location=SearchSignalLocation.TITLE, raw_text="Precision Calibration Services", count=1),
            SearchSignalOccurrence(location=SearchSignalLocation.H1, raw_text="Precision Calibration Lab", count=1),
        ],
    )
    search_signal_ev = SearchSignalEvidence(
        url="https://example.com/calibration",
        signals=[sig_item],
        total_signals_detected=1,
    )

    result = QueryPageMappingEngine.evaluate(
        url="https://example.com/calibration",
        search_signal_ev=search_signal_ev,
    )

    assert result.status == "success"
    assert result.total_concepts_mapped == 1
    assert result.direct_concepts_count == 1
    item = result.mapped_concepts[0]
    assert item.concept == "Precision Calibration"
    assert item.evidence_strength == SearchSignalConfidence.DIRECT
    assert item.has_title_or_h1 is True
    assert "TITLE" in item.evidence_locations
    assert "H1" in item.evidence_locations
    assert item.is_exact_term_match is True
    assert item.provenance == "query_page_mapping_engine"


def test_supported_and_weak_evidence_strength():
    """Verify concepts in headings + body receive SUPPORTED, and peripheral mentions receive WEAK."""
    sig_supported = SearchSignalItem(
        term="spectrometer analysis",
        raw_term="Spectrometer Analysis",
        category="heading",
        locations=[SearchSignalLocation.H2, SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=3,
        confidence=SearchSignalConfidence.SUPPORTED,
        occurrences=[
            SearchSignalOccurrence(location=SearchSignalLocation.H2, raw_text="Spectrometer Analysis Guide", count=1),
            SearchSignalOccurrence(location=SearchSignalLocation.MAIN_CONTENT, raw_text="Spectrometer analysis confirms purity", count=2),
        ],
    )
    sig_weak = SearchSignalItem(
        term="testing manual",
        raw_term="Testing Manual",
        category="image_alt",
        locations=[SearchSignalLocation.IMAGE_ALT],
        total_occurrences=1,
        confidence=SearchSignalConfidence.WEAK,
        occurrences=[
            SearchSignalOccurrence(location=SearchSignalLocation.IMAGE_ALT, raw_text="Testing manual cover", count=1),
        ],
    )
    search_signal_ev = SearchSignalEvidence(
        url="https://example.com/lab",
        signals=[sig_supported, sig_weak],
        total_signals_detected=2,
    )

    result = QueryPageMappingEngine.evaluate(
        url="https://example.com/lab",
        search_signal_ev=search_signal_ev,
    )

    assert result.total_concepts_mapped >= 1
    concepts_by_norm = {m.normalized_concept: m for m in result.mapped_concepts}
    
    assert "spectrometer analysis" in concepts_by_norm
    supp_item = concepts_by_norm["spectrometer analysis"]
    assert supp_item.evidence_strength == SearchSignalConfidence.SUPPORTED
    assert supp_item.has_title_or_h1 is False
    assert "H2" in supp_item.evidence_locations


def test_topic_membership_and_entity_association():
    """Verify M9.2 topic intelligence and Phase 8 entities are properly integrated."""
    topic = TopicEvidence(
        topic_name="Metallurgical Testing",
        normalized_name="metallurgical testing",
        topic_nature="DERIVED_CONCEPT_GROUP",
        supporting_terms=[
            TopicTermMembership(term="metallurgical testing", normalized_term="metallurgical testing"),
            TopicTermMembership(term="tensile strength", normalized_term="tensile strength"),
        ],
        occurrences_count=5,
        title_or_h1_presence=True,
        observed_locations=["TITLE", "H1", "MAIN_CONTENT"],
        associated_entities=["Acme Labs (Organization)"],
    )
    topic_intel = PageTopicIntelligence(
        url="https://example.com/metallurgy",
        topics=[topic],
        total_topics_derived=1,
    )

    entity = DetectedEntity(
        name="Acme Labs",
        entity_type=EntityType.ORGANIZATION,
        source=EntitySource.JSON_LD,
        signal_type=EntitySignalType.STRUCTURED_DATA_DECLARATION,
    )
    entity_ev = EntityEvidence(
        url="https://example.com/metallurgy",
        detected_entities=[entity],
    )

    result = QueryPageMappingEngine.evaluate(
        url="https://example.com/metallurgy",
        topic_intel_ev=topic_intel,
        entity_ev=entity_ev,
    )

    assert result.status == "success"
    c_map = {m.normalized_concept: m for m in result.mapped_concepts}
    assert "metallurgical testing" in c_map
    top_c = c_map["metallurgical testing"]
    assert top_c.is_topic_membership is True
    assert top_c.concept_nature == "EVIDENCED_TOPIC"
    assert top_c.has_title_or_h1 is True
    assert top_c.evidence_strength == SearchSignalConfidence.DIRECT
    assert len(top_c.supporting_snippets) > 0


def test_url_path_evidence_and_bounded_snippets():
    """Verify URL path matching and assertion that supporting_snippets is bounded (<= 5)."""
    # Create signal with multiple occurrences
    sig = SearchSignalItem(
        term="chemical calibration",
        raw_term="Chemical Calibration",
        category="heading",
        locations=[SearchSignalLocation.H2, SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=6,
        confidence=SearchSignalConfidence.SUPPORTED,
        occurrences=[
            SearchSignalOccurrence(location=SearchSignalLocation.H2, raw_text=f"Chemical calibration header {i}", count=1)
            for i in range(10)
        ],
    )
    search_signal_ev = SearchSignalEvidence(
        url="https://example.com/services/chemical-calibration",
        signals=[sig],
        total_signals_detected=1,
    )

    result = QueryPageMappingEngine.evaluate(
        url="https://example.com/services/chemical-calibration",
        search_signal_ev=search_signal_ev,
    )

    item = result.mapped_concepts[0]
    assert item.url_path_match is True
    assert "URL_PATH" in item.evidence_locations
    # Ensure bounded snippets
    assert len(item.supporting_snippets) <= 5


def test_fact_analysis_separation():
    """Verify strict separation of facts and analyses in PageQueryEvidence."""
    sig = SearchSignalItem(
        term="traceability standards",
        raw_term="Traceability Standards",
        category="heading",
        locations=[SearchSignalLocation.TITLE, SearchSignalLocation.MAIN_CONTENT],
        total_occurrences=3,
        confidence=SearchSignalConfidence.DIRECT,
    )
    search_signal_ev = SearchSignalEvidence(
        url="https://example.com/traceability",
        signals=[sig],
        total_signals_detected=1,
    )

    result = QueryPageMappingEngine.evaluate(
        url="https://example.com/traceability",
        search_signal_ev=search_signal_ev,
    )

    assert len(result.facts) >= 2
    assert len(result.analyses) >= 1
    # Facts verify observable counts
    assert any("Mapped" in f and "observed concepts" in f for f in result.facts)
    # Analyses characterize distribution without ranking claims
    assert any("evidence distribution" in a.lower() for a in result.analyses)
    # No SEO scores or external ranking claims
    for text in result.facts + result.analyses:
        assert "rank" not in text.lower() or "ranking" not in text.lower()
        assert "score" not in text.lower()
