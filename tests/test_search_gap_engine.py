"""
Search Gap Analyzer Unit Test Suite (Phase 9.5 - Layer A).
Validates deterministic on-site topic gap detection, concept coverage asymmetry,
content depth & heading structure asymmetry, partial-crawl safeguards,
and explicit error capture.
"""
import pytest
from rankintel.analyzers.search_gap_analyzer import SearchGapAnalyzer
from rankintel.models.schema import (
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    SiteCannibalizationIntelligence,
    ObservableTopicGapItem,
    TopicGapType,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    SiteQueryPageIntelligence,
    TopicEvidence,
    SiteTopicIntelligence,
    ContentEvidence,
    HeadingStructureEvidence,
    HeadingSectionDetail,
    SiteContentIntelligence,
)


def test_concept_coverage_asymmetry_detection():
    """Verify pages covering same topic with concept asymmetry trigger OBSERVED_TOPIC_GAP."""
    u1 = "https://example.com/ndt-calibration"
    u2 = "https://example.com/ndt-services"

    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><body><h1>NDT Calibration</h1></body></html>",
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body><h1>NDT Services</h1></body></html>",
    )

    # u2 covers NDT with rich sub-concepts, u1 only covers NDT
    q1 = PageQueryEvidence(
        url=u1,
        mapped_concepts=[
            QueryPageEvidence(concept="NDT", normalized_concept="ndt"),
        ]
    )
    q2 = PageQueryEvidence(
        url=u2,
        mapped_concepts=[
            QueryPageEvidence(concept="NDT", normalized_concept="ndt"),
            QueryPageEvidence(concept="Ultrasonic Testing", normalized_concept="ultrasonic testing"),
            QueryPageEvidence(concept="Magnetic Particle", normalized_concept="magnetic particle"),
            QueryPageEvidence(concept="Radiography", normalized_concept="radiography"),
        ]
    )

    query_intel = SiteQueryPageIntelligence(
        page_query_evidence={u1: q1, u2: q2},
        concept_relationships=[
            QueryPageRelationship(
                concept="NDT",
                normalized_concept="ndt",
                pages_count=2,
                page_urls=[u1, u2],
            )
        ]
    )

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        crawl_records=[rec1, rec2],
        query_page_intelligence=query_intel,
    )

    res = SearchGapAnalyzer.analyze_site(site_crawl)

    assert isinstance(res, SiteCannibalizationIntelligence)
    assert res.status == "success"
    assert len(res.observable_topic_gaps) >= 1

    gap = res.observable_topic_gaps[0]
    assert gap.gap_type == TopicGapType.OBSERVED_TOPIC_GAP
    assert gap.source_url == u1  # Page missing the concepts
    assert gap.related_url == u2
    assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in gap.recommendation
    assert any("ultrasonic" in c.lower() or "magnetic" in c.lower() for c in gap.missing_concepts)


def test_content_depth_and_heading_asymmetry_detection():
    """Verify deep heading structure on one page vs thin structure on related page triggers CONTENT_DEPTH_ASYMMETRY."""
    u1 = "https://example.com/metallurgy-summary"
    u2 = "https://example.com/metallurgy-comprehensive"

    rec1 = CrawlRecord(
        url=u1,
        normalized_url=u1,
        identity_url=u1,
        crawl_status=CrawlStatus.FETCHED,
        depth=0,
        status_code=200,
        raw_html="<html><body><h1>Metallurgy</h1><p>Brief text.</p></body></html>",
        word_count=120,
        h2_tags=[],
    )
    rec2 = CrawlRecord(
        url=u2,
        normalized_url=u2,
        identity_url=u2,
        crawl_status=CrawlStatus.FETCHED,
        depth=1,
        status_code=200,
        raw_html="<html><body><h1>Metallurgy</h1><h2>Microstructure Analysis</h2><h2>Chemical Composition</h2><h2>Grain Size</h2><p>Extensive details.</p></body></html>",
        word_count=750,
        h2_tags=["Microstructure Analysis", "Chemical Composition", "Grain Size"],
    )

    q1 = PageQueryEvidence(
        url=u1,
        mapped_concepts=[QueryPageEvidence(concept="Metallurgy", normalized_concept="metallurgy")]
    )
    q2 = PageQueryEvidence(
        url=u2,
        mapped_concepts=[QueryPageEvidence(concept="Metallurgy", normalized_concept="metallurgy")]
    )

    query_intel = SiteQueryPageIntelligence(
        page_query_evidence={u1: q1, u2: q2},
        concept_relationships=[
            QueryPageRelationship(
                concept="Metallurgy",
                normalized_concept="metallurgy",
                pages_count=2,
                page_urls=[u1, u2],
            )
        ]
    )

    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_COMPLETE",
        crawl_records=[rec1, rec2],
        query_page_intelligence=query_intel,
    )

    res = SearchGapAnalyzer.analyze_site(site_crawl)

    depth_gaps = [g for g in res.observable_topic_gaps if g.gap_type == TopicGapType.CONTENT_DEPTH_ASYMMETRY]
    assert len(depth_gaps) >= 1
    d_gap = depth_gaps[0]
    assert d_gap.source_url == u1
    assert d_gap.related_url == u2
    assert "CONTENT_DEPTH_ASYMMETRY" in d_gap.rationale
    assert "REQUIRES_EXTERNAL_SEARCH_VALIDATION" in d_gap.recommendation


def test_partial_crawl_safeguards():
    """Verify partial crawl guardrail attaches disclaimer and does not claim site-wide gaps."""
    site_crawl = SiteCrawlResult(
        completeness_status="CRAWL_PARTIAL_MAX_PAGES",
        remaining_frontier=10,
        pages_skipped=2,
        crawl_records=[
            CrawlRecord(url="https://example.com/p1", normalized_url="https://example.com/p1", identity_url="https://example.com/p1", crawl_status=CrawlStatus.FETCHED, depth=0, status_code=200, raw_html="<p>Test</p>"),
            CrawlRecord(url="https://example.com/p2", normalized_url="https://example.com/p2", identity_url="https://example.com/p2", crawl_status=CrawlStatus.FETCHED, depth=1, status_code=200, raw_html="<p>Test 2</p>"),
        ]
    )

    res = SearchGapAnalyzer.analyze_site(site_crawl)

    assert res.is_partial_crawl is True
    assert "Observed topic gaps reflect crawled pages only" in res.completeness_disclaimer
    assert "uncrawled pages" in res.completeness_disclaimer


def test_search_gap_explicit_error_capture():
    """Verify exceptions are explicitly captured in SiteCannibalizationIntelligence with status='error'."""
    site_crawl = SiteCrawlResult()
    site_crawl.crawl_records = [123, 456]  # type: ignore

    res = SearchGapAnalyzer.analyze_site(site_crawl)

    assert res.status == "error"
    assert res.error_message is not None
    assert "Search gap analysis failed" in res.error_message
    assert any("Error during search gap analysis" in f for f in res.facts)
