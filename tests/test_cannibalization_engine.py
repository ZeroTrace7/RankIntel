"""
Cannibalization Analyzer Unit Test Suite (Phase 9.5 - Layer A).
Validates deterministic multi-page cannibalization signal detection, multi-dimensional
evidence gating (topic + DIRECT/SUPPORTED query mapping + title/H1 overlap + intent alignment +
main-content concept overlap), false-positive protection for topic-only overlap,
and explicit error capture.
"""
import pytest
from rankintel.analyzers.cannibalization_analyzer import (
    CannibalizationAnalyzer,
    tokenize_text,
    compute_jaccard_similarity,
)
from rankintel.models.schema import (
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    SiteCannibalizationIntelligence,
    PageCannibalizationEvidence,
    PotentialCannibalizationItem,
    CannibalizationSignalType,
    SearchSignalConfidence,
    SearchIntentCategory,
    PageIntentEvidence,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    SiteQueryPageIntelligence,
    TopicEvidence,
    SiteTopicIntelligence,
    SiteTopicCoverageIntelligence,
)


def test_tokenize_and_jaccard_similarity():
    """Verify deterministic tokenization and Jaccard token similarity calculation."""
    tokens_a = tokenize_text("Industrial Hardness Testing Equipment & Services")
    tokens_b = tokenize_text("Hardness Testing Services and Calibration")

    assert "industrial" in tokens_a
    assert "services" in tokens_a
    assert "and" not in tokens_b  # Stopword removed

    sim = compute_jaccard_similarity(tokens_a, tokens_b)
    assert sim > 0.30  # Shared 'hardness', 'testing', 'services'


def test_single_page_baseline_evaluation():
    """Verify single-page audit returns factual baseline explaining >=2 pages required."""
    res = CannibalizationAnalyzer.evaluate_page("https://example.com/page-a")
    assert isinstance(res, PageCannibalizationEvidence)
    assert res.status == "success"
    assert len(res.potential_signals) == 0
    assert any("requires multi-page crawl evidence" in f for f in res.facts)


def test_multi_dimensional_gate_detects_potential_cannibalization():
    """Verify all 5 dimensions satisfied triggers POTENTIAL_CANNIBALIZATION_SIGNAL."""
    u1 = "https://example.com/hardness-testing"
    u2 = "https://example.com/metal-hardness-testing"

    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><head><title>Hardness Testing Services</title></head><body><h1>Hardness Testing</h1><p>Rockwell and Brinell calibration services.</p></body></html>",
        title="Hardness Testing Services",
        h1_tags=["Hardness Testing"],
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><head><title>Industrial Hardness Testing Solutions</title></head><body><h1>Hardness Testing Solutions</h1><p>Rockwell hardness testing methods.</p></body></html>",
        title="Industrial Hardness Testing Solutions",
        h1_tags=["Hardness Testing Solutions"],
    )

    # Concept evidence
    q1 = PageQueryEvidence(
        url=u1,
        mapped_concepts=[
            QueryPageEvidence(
                concept="Hardness Testing",
                normalized_concept="hardness testing",
                evidence_strength=SearchSignalConfidence.DIRECT,
            ),
            QueryPageEvidence(
                concept="Rockwell",
                normalized_concept="rockwell",
                evidence_strength=SearchSignalConfidence.SUPPORTED,
            ),
        ]
    )
    q2 = PageQueryEvidence(
        url=u2,
        mapped_concepts=[
            QueryPageEvidence(
                concept="Hardness Testing",
                normalized_concept="hardness testing",
                evidence_strength=SearchSignalConfidence.DIRECT,
            ),
            QueryPageEvidence(
                concept="Rockwell",
                normalized_concept="rockwell",
                evidence_strength=SearchSignalConfidence.SUPPORTED,
            ),
        ]
    )

    query_intel = SiteQueryPageIntelligence(
        page_query_evidence={u1: q1, u2: q2},
        concept_relationships=[
            QueryPageRelationship(
                concept="Hardness Testing",
                normalized_concept="hardness testing",
                pages_count=2,
                page_urls=[u1, u2],
                supporting_pages=[
                    QueryPageEvidence(concept="Hardness Testing", normalized_concept="hardness testing", url=u1, evidence_strength=SearchSignalConfidence.DIRECT),
                    QueryPageEvidence(concept="Hardness Testing", normalized_concept="hardness testing", url=u2, evidence_strength=SearchSignalConfidence.DIRECT),
                ]
            )
        ]
    )

    intent_map = {
        u1: PageIntentEvidence(url=u1, primary_observed_intent_signal=SearchIntentCategory.COMMERCIAL),
        u2: PageIntentEvidence(url=u2, primary_observed_intent_signal=SearchIntentCategory.COMMERCIAL),
    }

    coverage_intel = SiteTopicCoverageIntelligence(page_intent_evidence=intent_map)

    site_crawl = SiteCrawlResult(
        crawl_records=[rec1, rec2],
        query_page_intelligence=query_intel,
        topic_coverage_intelligence=coverage_intel,
    )

    res = CannibalizationAnalyzer.analyze_site(site_crawl)

    assert isinstance(res, SiteCannibalizationIntelligence)
    assert res.status == "success"
    assert len(res.potential_signals) == 1

    signal = res.potential_signals[0]
    assert signal.signal_type == CannibalizationSignalType.POTENTIAL_CANNIBALIZATION_SIGNAL
    assert signal.topic == "Hardness Testing"
    assert u1 in signal.competing_urls and u2 in signal.competing_urls
    assert signal.shared_intent == SearchIntentCategory.COMMERCIAL
    assert signal.title_overlap_ratio > 0.30
    assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in signal.recommendation
    assert "POTENTIAL_CANNIBALIZATION_SIGNAL" in signal.rationale


def test_false_positive_protection_differing_intents():
    """Verify different intents (e.g. INFORMATIONAL guide vs TRANSACTIONAL quote) prevent cannibalization flags."""
    u1 = "https://example.com/guide/hardness-testing"
    u2 = "https://example.com/quote/hardness-testing"

    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><head><title>Hardness Testing Guide</title></head><body><h1>Hardness Testing Overview</h1></body></html>",
        title="Hardness Testing Guide",
        h1_tags=["Hardness Testing Overview"],
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><head><title>Hardness Testing Quote Request</title></head><body><h1>Request Hardness Testing</h1></body></html>",
        title="Hardness Testing Quote Request",
        h1_tags=["Request Hardness Testing"],
    )

    q1 = PageQueryEvidence(
        url=u1,
        mapped_concepts=[QueryPageEvidence(concept="Hardness Testing", normalized_concept="hardness testing", evidence_strength=SearchSignalConfidence.DIRECT)]
    )
    q2 = PageQueryEvidence(
        url=u2,
        mapped_concepts=[QueryPageEvidence(concept="Hardness Testing", normalized_concept="hardness testing", evidence_strength=SearchSignalConfidence.DIRECT)]
    )

    query_intel = SiteQueryPageIntelligence(
        page_query_evidence={u1: q1, u2: q2},
        concept_relationships=[
            QueryPageRelationship(
                concept="Hardness Testing",
                normalized_concept="hardness testing",
                pages_count=2,
                page_urls=[u1, u2],
                supporting_pages=[
                    QueryPageEvidence(concept="Hardness Testing", normalized_concept="hardness testing", url=u1, evidence_strength=SearchSignalConfidence.DIRECT),
                    QueryPageEvidence(concept="Hardness Testing", normalized_concept="hardness testing", url=u2, evidence_strength=SearchSignalConfidence.DIRECT),
                ]
            )
        ]
    )

    # Differing intents: Informational vs Transactional
    intent_map = {
        u1: PageIntentEvidence(url=u1, primary_observed_intent_signal=SearchIntentCategory.INFORMATIONAL),
        u2: PageIntentEvidence(url=u2, primary_observed_intent_signal=SearchIntentCategory.TRANSACTIONAL),
    }

    coverage_intel = SiteTopicCoverageIntelligence(page_intent_evidence=intent_map)

    site_crawl = SiteCrawlResult(
        crawl_records=[rec1, rec2],
        query_page_intelligence=query_intel,
        topic_coverage_intelligence=coverage_intel,
    )

    res = CannibalizationAnalyzer.analyze_site(site_crawl)

    # Must NOT emit POTENTIAL_CANNIBALIZATION_SIGNAL
    assert len(res.potential_signals) == 0
    # Must document intent segmentation in analyses
    assert any("OBSERVED_INTENT_OVERLAP" in a and "intent segmentation" in a for a in res.analyses)


def test_false_positive_protection_disjoint_titles_and_h1s():
    """Verify low title/H1 overlap prevents cannibalization signals even if topic overlaps."""
    u1 = "https://example.com/ndt-hardness-testing"
    u2 = "https://example.com/company-accreditation"

    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><head><title>Non-Destructive Hardness Testing</title></head><body><h1>Hardness Testing</h1></body></html>",
        title="Non-Destructive Hardness Testing",
        h1_tags=["Hardness Testing"],
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><head><title>Laboratory ISO Accreditation</title></head><body><h1>Quality Certificates</h1></body></html>",
        title="Laboratory ISO Accreditation",
        h1_tags=["Quality Certificates"],
    )

    q1 = PageQueryEvidence(
        url=u1,
        mapped_concepts=[QueryPageEvidence(concept="Testing", normalized_concept="testing", evidence_strength=SearchSignalConfidence.DIRECT)]
    )
    q2 = PageQueryEvidence(
        url=u2,
        mapped_concepts=[QueryPageEvidence(concept="Testing", normalized_concept="testing", evidence_strength=SearchSignalConfidence.SUPPORTED)]
    )

    query_intel = SiteQueryPageIntelligence(
        page_query_evidence={u1: q1, u2: q2},
        concept_relationships=[
            QueryPageRelationship(
                concept="Testing",
                normalized_concept="testing",
                pages_count=2,
                page_urls=[u1, u2],
                supporting_pages=[
                    QueryPageEvidence(concept="Testing", normalized_concept="testing", url=u1, evidence_strength=SearchSignalConfidence.DIRECT),
                    QueryPageEvidence(concept="Testing", normalized_concept="testing", url=u2, evidence_strength=SearchSignalConfidence.SUPPORTED),
                ]
            )
        ]
    )

    intent_map = {
        u1: PageIntentEvidence(url=u1, primary_observed_intent_signal=SearchIntentCategory.COMMERCIAL),
        u2: PageIntentEvidence(url=u2, primary_observed_intent_signal=SearchIntentCategory.COMMERCIAL),
    }

    site_crawl = SiteCrawlResult(
        crawl_records=[rec1, rec2],
        query_page_intelligence=query_intel,
        topic_coverage_intelligence=SiteTopicCoverageIntelligence(page_intent_evidence=intent_map),
    )

    res = CannibalizationAnalyzer.analyze_site(site_crawl)

    # Must NOT emit POTENTIAL_CANNIBALIZATION_SIGNAL due to low title/H1 overlap
    assert len(res.potential_signals) == 0
    assert any("OBSERVED_TOPIC_OVERLAP" in a for a in res.analyses)


def test_explicit_error_capture_never_swallowed():
    """Verify exceptions are captured explicitly with status='error' and diagnostics."""
    site_crawl = SiteCrawlResult()
    # Intentionally pass invalid crawl_records structure to trigger processing error
    site_crawl.crawl_records = [None, None]  # type: ignore

    res = CannibalizationAnalyzer.analyze_site(site_crawl)

    assert res.status == "error"
    assert res.error_message is not None
    assert "Cannibalization analysis failed" in res.error_message
    assert any("Error during cannibalization analysis" in f for f in res.facts)
