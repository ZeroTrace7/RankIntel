"""
Site Topic Coverage Analyzer — Multi-page crawl topic coverage and intent distribution (Layer A).
Aggregates topic coverage across crawled pages, aligns observed topics with page-level intent signals,
determines observed dominant intent per topic with strict deterministic thresholding,
identifies multi-intent topics, and enforces partial crawl boundaries.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteTopicCoverageIntelligence,
    TopicCoverageEvidence,
    PageIntentEvidence,
    SearchIntentCategory,
    SearchSignalConfidence,
)
from rankintel.engines.search_intent_engine import SearchIntentEngine


class SiteTopicCoverageAnalyzer:
    """
    Analyzes cross-page topic coverage and intent signal alignment from multi-page crawl records.
    Operates strictly in-memory without initiating any duplicate or external HTTP requests.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteTopicCoverageIntelligence:
        """
        Processes crawl records in site_crawl to evaluate page intent, aggregate topic coverage,
        determine observed dominant intent with deterministic thresholding, and attach
        SiteTopicCoverageIntelligence to site_crawl.
        """
        is_partial = (
            (site_crawl.completeness_status != "CRAWL_COMPLETE")
            or (getattr(site_crawl, "remaining_frontier", 0) > 0)
            or (getattr(site_crawl, "pages_skipped", 0) > 0)
            or (getattr(site_crawl, "pages_blocked", 0) > 0)
        )
        disclaimer = (
            "Observed topic coverage reflects crawled pages only; absence of coverage for any topic or intent in partial crawls does not indicate lack of content or intent on uncrawled pages of the website."
            if is_partial
            else "Observed topic coverage derived from complete crawl graph execution."
        )

        try:
            records_to_process = [
                rec for rec in site_crawl.crawl_records
                if (rec.status_code == 200 or rec.status_code is None) and rec.raw_html
            ]

            # In-memory evidence lookups
            signal_map = {}
            if site_crawl.search_signal_intelligence and site_crawl.search_signal_intelligence.page_signal_evidence:
                signal_map = site_crawl.search_signal_intelligence.page_signal_evidence

            topic_map = {}
            if site_crawl.topic_intelligence and site_crawl.topic_intelligence.page_topic_intelligence:
                topic_map = site_crawl.topic_intelligence.page_topic_intelligence

            query_map = {}
            if site_crawl.query_page_intelligence and site_crawl.query_page_intelligence.page_query_evidence:
                query_map = site_crawl.query_page_intelligence.page_query_evidence

            content_map = {}
            if site_crawl.content_intelligence and site_crawl.content_intelligence.page_content_evidence:
                content_map = site_crawl.content_intelligence.page_content_evidence

            entity_map = {}
            if site_crawl.entity_intelligence and site_crawl.entity_intelligence.page_entity_evidence:
                entity_map = site_crawl.entity_intelligence.page_entity_evidence

            # 1. Evaluate single-page intent evidence for each crawled page
            page_intent_map: Dict[str, PageIntentEvidence] = {}
            site_intent_distribution: Dict[str, int] = defaultdict(int)

            for rec in records_to_process:
                url = rec.url
                p_intent = SearchIntentEngine.evaluate(
                    url=url,
                    raw_html=rec.raw_html,
                    on_page=None,
                    search_signal_ev=signal_map.get(url),
                    topic_intel_ev=topic_map.get(url),
                    query_page_ev=query_map.get(url),
                    content_ev=content_map.get(url),
                    entity_ev=entity_map.get(url),
                    schema_ev=None,
                )
                page_intent_map[url] = p_intent
                site_intent_distribution[p_intent.primary_observed_intent_signal.value] += 1

            # 2. Collect topic-to-page mappings
            # Extract topics from site_crawl.topic_intelligence, query_page_intelligence, and search_signal_intelligence
            topic_pages_map: Dict[str, Set[str]] = defaultdict(set)
            topic_primary_pages_map: Dict[str, Set[str]] = defaultdict(set)
            topic_display_names: Dict[str, str] = {}
            topic_associated_entities: Dict[str, Set[str]] = defaultdict(set)

            # From TopicIntelligence (M9.2)
            if site_crawl.topic_intelligence and site_crawl.topic_intelligence.topics:
                for t in site_crawl.topic_intelligence.topics:
                    norm = t.normalized_name
                    topic_display_names[norm] = t.topic_name
                    for p in t.page_urls:
                        topic_pages_map[norm].add(p)
                    if t.associated_entities:
                        topic_associated_entities[norm].update(t.associated_entities)

            # From QueryPageIntelligence (M9.3)
            if site_crawl.query_page_intelligence and site_crawl.query_page_intelligence.concept_relationships:
                for rel in site_crawl.query_page_intelligence.concept_relationships:
                    norm = rel.normalized_concept
                    if norm not in topic_display_names or len(rel.concept) > len(topic_display_names[norm]):
                        topic_display_names[norm] = rel.concept
                    for p in rel.page_urls:
                        topic_pages_map[norm].add(p)
                    for dp in rel.direct_pages:
                        topic_primary_pages_map[norm].add(dp)
                    for th1 in rel.title_or_h1_pages:
                        topic_primary_pages_map[norm].add(th1)
                    if rel.associated_entities:
                        topic_associated_entities[norm].update(rel.associated_entities)

            # Also check page-level query evidence primary concepts
            for url, q_ev in query_map.items():
                for c_item in q_ev.mapped_concepts:
                    norm = c_item.normalized_concept
                    if norm not in topic_display_names:
                        topic_display_names[norm] = c_item.concept
                    topic_pages_map[norm].add(url)
                    if c_item.evidence_strength == SearchSignalConfidence.DIRECT or c_item.has_title_or_h1:
                        topic_primary_pages_map[norm].add(url)

            # 3. Build TopicCoverageEvidence for each topic
            covered_topics: List[TopicCoverageEvidence] = []
            multi_intent_topics: List[str] = []

            for norm_topic, urls in topic_pages_map.items():
                display_name = topic_display_names.get(norm_topic, norm_topic)
                sorted_urls = sorted(list(urls))
                primary_urls = sorted(list(topic_primary_pages_map.get(norm_topic, set())))

                # Calculate intent breakdown across supporting pages
                intent_breakdown: Dict[str, int] = defaultdict(int)
                classified_intents: List[SearchIntentCategory] = []

                for u in sorted_urls:
                    p_ev = page_intent_map.get(u)
                    if p_ev:
                        cat = p_ev.primary_observed_intent_signal
                        intent_breakdown[cat.value] += 1
                        if cat not in (SearchIntentCategory.UNSPECIFIED, SearchIntentCategory.MIXED):
                            classified_intents.append(cat)

                # Determine observed_dominant_intent using deterministic thresholding
                observed_dominant: SearchIntentCategory = SearchIntentCategory.UNSPECIFIED

                if not classified_intents:
                    observed_dominant = SearchIntentCategory.UNSPECIFIED
                elif len(classified_intents) == 1:
                    observed_dominant = classified_intents[0]
                else:
                    # Tally classified categories
                    cat_counts: Dict[SearchIntentCategory, int] = defaultdict(int)
                    for c in classified_intents:
                        cat_counts[c] += 1

                    sorted_cat_counts = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
                    top_c, top_count = sorted_cat_counts[0]
                    total_classified = len(classified_intents)

                    # Threshold: >= 60% of classified pages must agree on the category
                    if (top_count / total_classified) >= 0.60:
                        observed_dominant = top_c
                    else:
                        observed_dominant = SearchIntentCategory.MIXED

                # Check if multi-intent (spans >= 2 distinct classified intent categories)
                distinct_intents = set(classified_intents)
                if len(distinct_intents) >= 2:
                    multi_intent_topics.append(display_name)

                supp_ev: List[str] = [
                    f"Observed on {len(sorted_urls)} page(s) across intent stages: {dict(intent_breakdown)}"
                ]

                cov_item = TopicCoverageEvidence(
                    topic_name=display_name,
                    normalized_name=norm_topic,
                    coverage_nature="OBSERVED_TOPIC_COVERAGE",
                    pages_count=len(sorted_urls),
                    page_urls=sorted_urls,
                    primary_pages=primary_urls if primary_urls else sorted_urls[:3],
                    intent_breakdown=dict(intent_breakdown),
                    observed_dominant_intent=observed_dominant,
                    associated_entities=sorted(list(topic_associated_entities.get(norm_topic, set()))),
                    supporting_evidence=supp_ev,
                    provenance="site_topic_coverage_analyzer",
                )
                covered_topics.append(cov_item)

            # Sort covered topics by pages_count descending
            covered_topics.sort(key=lambda t: t.pages_count, reverse=True)

            # 4. Formulate Facts and Analyses
            facts: List[str] = []
            analyses: List[str] = []

            facts.append(
                f"Multi-page crawl evaluated {len(records_to_process)} HTML pages; {len(covered_topics)} recurring topics covered."
            )
            dist_str = ", ".join([f"{k}: {v}" for k, v in sorted(site_intent_distribution.items())])
            facts.append(f"Site-wide primary observed intent distribution: {dist_str}.")

            if multi_intent_topics:
                facts.append(
                    f"{len(multi_intent_topics)} topic(s) exhibit multi-intent coverage spanning distinct intent categories."
                )
                sample_multi = ", ".join(multi_intent_topics[:4])
                analyses.append(
                    f"OBSERVED_TOPIC_COVERAGE: Multi-stage intent coverage observed for topics [{sample_multi}], spanning distinct informational/transactional pages."
                )

            if site_intent_distribution:
                dominant_site_cat = max(site_intent_distribution.items(), key=lambda x: x[1])[0]
                analyses.append(
                    f"INFERRED_FROM_ON_SITE_EVIDENCE: Prevalent on-site intent signal across crawled pages is '{dominant_site_cat}'."
                )

            intel = SiteTopicCoverageIntelligence(
                status="partial" if is_partial else "success",
                total_pages_evaluated=len(records_to_process),
                is_partial_crawl=is_partial,
                completeness_disclaimer=disclaimer,
                total_topics_covered=len(covered_topics),
                covered_topics=covered_topics,
                intent_distribution=dict(site_intent_distribution),
                page_intent_evidence=page_intent_map,
                multi_intent_topics=multi_intent_topics,
                terminology_nature="OBSERVED_WEBSITE_EVIDENCE",
                facts=facts,
                analyses=analyses,
            )

            site_crawl.topic_coverage_intelligence = intel
            return intel

        except Exception as e:
            intel = SiteTopicCoverageIntelligence(
                status="error",
                error_message=f"Site topic coverage analysis failed: {e}",
                is_partial_crawl=is_partial,
                completeness_disclaimer="Topic coverage intelligence unavailable due to an analysis error.",
                total_pages_evaluated=0,
                facts=[f"Error during topic coverage analysis: {e}"],
                analyses=["INFERRED_FROM_ON_SITE_EVIDENCE: Analysis aborted due to processing exception."],
            )
            site_crawl.topic_coverage_intelligence = intel
            return intel
