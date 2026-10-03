"""
Site Topic Analyzer — Cross-page multi-page crawl topic intelligence (Layer A).
Aggregates recurring on-site concept groups, tracks cross-page term memberships,
maps inter-topic relationships, and strictly handles partial crawl coverage with explicit disclaimers.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteTopicIntelligence,
    PageTopicIntelligence,
    TopicEvidence,
    TopicTermMembership,
    TopicRelationship,
    TopicRelationshipType,
    TopicMembershipType,
)
from rankintel.engines.topic_intelligence_engine import (
    TopicIntelligenceEngine,
    is_word_bounded_substring,
)


class SiteTopicAnalyzer:
    """
    Analyzes site-wide concept groups and topic relationships from multi-page crawl records
    without initiating any network requests.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteTopicIntelligence:
        """
        Processes crawl records in site_crawl to aggregate recurring observed concepts,
        synthesize site-wide topic telemetry, and preserve partial-crawl boundaries.
        """
        # Detect partial crawl status explicitly
        is_partial = (
            (site_crawl.completeness_status != "CRAWL_COMPLETE")
            or (getattr(site_crawl, "remaining_frontier", 0) > 0)
            or (getattr(site_crawl, "pages_skipped", 0) > 0)
            or (getattr(site_crawl, "pages_blocked", 0) > 0)
        )
        disclaimer = (
            "Observed topics reflect crawled pages only; absence of a topic in partial crawls does not indicate lack of coverage by the website."
            if is_partial
            else "Observed topics derived from complete crawl graph execution."
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

            content_map = {}
            if site_crawl.content_intelligence and site_crawl.content_intelligence.page_content_evidence:
                content_map = site_crawl.content_intelligence.page_content_evidence

            entity_map = {}
            if site_crawl.entity_intelligence and site_crawl.entity_intelligence.page_entity_evidence:
                entity_map = site_crawl.entity_intelligence.page_entity_evidence

            page_topic_intel_map: Dict[str, PageTopicIntelligence] = {}

            # Cross-page aggregation structures: normalized_name -> aggregated data
            topic_pages: Dict[str, Set[str]] = defaultdict(set)
            topic_occurrences: Dict[str, int] = defaultdict(int)
            topic_locations: Dict[str, Set[str]] = defaultdict(set)
            topic_title_h1: Dict[str, bool] = defaultdict(bool)
            topic_display_names: Dict[str, str] = {}
            topic_associated_entities: Dict[str, Set[str]] = defaultdict(set)
            topic_members: Dict[str, Dict[str, TopicTermMembership]] = defaultdict(dict)
            relationships_accum: List[TopicRelationship] = []

            # 1. Process each page to generate or retrieve PageTopicIntelligence
            for rec in records_to_process:
                url = rec.url
                sig_ev = signal_map.get(url)
                cnt_ev = content_map.get(url)
                ent_ev = entity_map.get(url)

                page_intel = TopicIntelligenceEngine.evaluate(
                    search_signal_ev=sig_ev,
                    content_ev=cnt_ev,
                    entity_ev=ent_ev,
                    url=url,
                )
                page_topic_intel_map[url] = page_intel

                # Accumulate topics across pages
                for top in page_intel.topics:
                    norm = top.normalized_name
                    topic_pages[norm].add(url)
                    topic_occurrences[norm] += top.occurrences_count
                    for loc in top.observed_locations:
                        topic_locations[norm].add(loc)
                    if top.title_or_h1_presence:
                        topic_title_h1[norm] = True
                    for ent in top.associated_entities:
                        topic_associated_entities[norm].add(ent)
                    if norm not in topic_display_names or len(top.topic_name) > len(topic_display_names[norm]):
                        topic_display_names[norm] = top.topic_name

                    # Merge supporting terms
                    for mem in top.supporting_terms:
                        m_norm = mem.normalized_term
                        if m_norm not in topic_members[norm]:
                            topic_members[norm][m_norm] = TopicTermMembership(
                                term=mem.term,
                                normalized_term=mem.normalized_term,
                                membership_type=mem.membership_type,
                                occurrences_count=mem.occurrences_count,
                                structural_locations=list(mem.structural_locations),
                                confidence=mem.confidence,
                                provenance=mem.provenance,
                            )
                        else:
                            existing = topic_members[norm][m_norm]
                            existing.occurrences_count += mem.occurrences_count
                            loc_set = set(existing.structural_locations).union(set(mem.structural_locations))
                            existing.structural_locations = sorted(list(loc_set))

                # Collect relationships
                for rel in page_intel.relationships:
                    relationships_accum.append(rel)

            # 2. Build aggregated Site TopicEvidence items
            site_topics: List[TopicEvidence] = []
            min_pages_threshold = 2 if len(records_to_process) > 1 else 1

            for norm, p_urls in topic_pages.items():
                p_count = len(p_urls)
                total_occ = topic_occurrences[norm]
                all_locs = sorted(list(topic_locations[norm]))
                has_th1 = topic_title_h1[norm]
                disp_name = topic_display_names.get(norm, norm)
                ent_list = sorted(list(topic_associated_entities[norm]))
                members_list = sorted(
                    list(topic_members[norm].values()),
                    key=lambda m: (-m.occurrences_count, m.term.lower()),
                )

                site_topics.append(
                    TopicEvidence(
                        topic_name=disp_name,
                        normalized_name=norm,
                        topic_nature="DERIVED_CONCEPT_GROUP",
                        evidence_nature="ANALYSIS",
                        supporting_terms=members_list,
                        pages_count=p_count,
                        page_urls=sorted(list(p_urls)),
                        occurrences_count=total_occ,
                        structural_presence_count=len(all_locs),
                        title_or_h1_presence=has_th1,
                        observed_locations=all_locs,
                        associated_entities=ent_list,
                        provenance="topic_intelligence_engine",
                    )
                )

            # Sort site topics deterministically:
            # 1. title_or_h1_presence (True first)
            # 2. pages_count descending
            # 3. occurrences_count descending
            # 4. topic_name alphabetical
            site_topics.sort(
                key=lambda t: (
                    not t.title_or_h1_presence,
                    -t.pages_count,
                    -t.occurrences_count,
                    t.topic_name.lower(),
                )
            )

            # Identify recurring observed concepts (Correction #4: telemetry labeling)
            recurring_topics = [
                t for t in site_topics
                if t.pages_count >= min_pages_threshold
            ]

            # Cross-page relationship deduplication and aggregation
            unique_relationships: List[TopicRelationship] = []
            rel_map: Dict[Tuple[str, str, str], TopicRelationship] = {}

            for rel in relationships_accum:
                k = (rel.topic_a, rel.topic_b, rel.relationship_type.value if hasattr(rel.relationship_type, "value") else str(rel.relationship_type))
                if k not in rel_map:
                    rel_map[k] = TopicRelationship(
                        topic_a=rel.topic_a,
                        topic_b=rel.topic_b,
                        relationship_type=rel.relationship_type,
                        evidence_nature="ANALYSIS",
                        co_occurrence_pages_count=rel.co_occurrence_pages_count,
                        supporting_evidence=list(rel.supporting_evidence),
                    )
                else:
                    rel_map[k].co_occurrence_pages_count += 1
                    for supp in rel.supporting_evidence:
                        if supp not in rel_map[k].supporting_evidence:
                            rel_map[k].supporting_evidence.append(supp)

            unique_relationships = list(rel_map.values())
            unique_relationships.sort(key=lambda r: (r.topic_a.lower(), r.topic_b.lower()))

            # Generate strict FACT and ANALYSIS separation
            facts: List[str] = [
                f"Evaluated {len(records_to_process)} crawled pages for on-site topic intelligence.",
                f"Aggregated {len(site_topics)} unique concept groups across all crawled documents.",
                f"Observed {len(recurring_topics)} recurring concepts appearing across multiple page boundaries."
                if len(records_to_process) > 1
                else f"Observed {len(recurring_topics)} concepts evidenced across primary structural elements.",
            ]

            analyses: List[str] = []
            if is_partial:
                analyses.append(f"Partial crawl detected ({site_crawl.pages_crawled} pages fetched). {disclaimer}")
            if recurring_topics:
                top_sample = [f"'{t.topic_name}' ({t.pages_count} pages, {t.occurrences_count} mentions)" for t in recurring_topics[:4]]
                analyses.append(f"Recurring observed concepts by telemetry: {', '.join(top_sample)}.")
            if unique_relationships:
                analyses.append(f"Mapped {len(unique_relationships)} inter-topic relationships across the crawl graph.")

            intel = SiteTopicIntelligence(
                status="success",
                total_pages_evaluated=len(records_to_process),
                is_partial_crawl=is_partial,
                completeness_disclaimer=disclaimer,
                total_topics_count=len(site_topics),
                recurring_topics_count=len(recurring_topics),
                topics=site_topics[:50],  # Bounded to top 50
                relationships=unique_relationships[:30],  # Bounded to top 30
                page_topic_intelligence=page_topic_intel_map,
                facts=facts,
                analyses=analyses,
            )

            site_crawl.topic_intelligence = intel
            return intel

        except Exception as e:
            # Explicit error handling (Correction #1: NEVER silently pass)
            intel = SiteTopicIntelligence(
                status="error",
                error_message=f"Site topic analysis failed: {e}",
                total_pages_evaluated=len(site_crawl.crawl_records),
                is_partial_crawl=is_partial,
                completeness_disclaimer="Site topic analysis encountered an unhandled error during aggregation.",
                facts=[f"Attempted aggregation on {len(site_crawl.crawl_records)} crawl records."],
                analyses=[f"Site topic analyzer error: {e}"],
            )
            site_crawl.topic_intelligence = intel
            return intel
