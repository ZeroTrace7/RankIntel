"""
Site Query-Page Analyzer — Cross-page multi-page crawl query-to-page intelligence (Layer A).
Aggregates concept-to-page mappings across all crawled pages, builds deterministic inverse
concept-to-page relationships, identifies multi-page coverage neutrally as POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP,
and strictly enforces partial crawl completeness boundaries.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteQueryPageIntelligence,
    PageQueryEvidence,
    QueryPageEvidence,
    QueryPageRelationship,
    SearchSignalConfidence,
)
from rankintel.engines.query_page_mapping_engine import QueryPageMappingEngine


class SiteQueryPageAnalyzer:
    """
    Analyzes site-wide concept-to-page and page-to-concept relationships from multi-page
    crawl records without initiating any network requests.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteQueryPageIntelligence:
        """
        Processes crawl records in site_crawl to aggregate concept-to-page mappings,
        build inverse concept-to-supporting-pages relationships, detect potential multi-page topic overlaps,
        and attach SiteQueryPageIntelligence to site_crawl.
        """
        is_partial = (
            (site_crawl.completeness_status != "CRAWL_COMPLETE")
            or (getattr(site_crawl, "remaining_frontier", 0) > 0)
            or (getattr(site_crawl, "pages_skipped", 0) > 0)
            or (getattr(site_crawl, "pages_blocked", 0) > 0)
        )
        disclaimer = (
            "Observed query-page mappings reflect crawled pages only; absence of a page/concept mapping in partial crawls does not indicate lack of coverage or relevance on uncrawled pages of the website."
            if is_partial
            else "Observed query-page mappings derived from complete crawl graph execution."
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

            content_map = {}
            if site_crawl.content_intelligence and site_crawl.content_intelligence.page_content_evidence:
                content_map = site_crawl.content_intelligence.page_content_evidence

            entity_map = {}
            if site_crawl.entity_intelligence and site_crawl.entity_intelligence.page_entity_evidence:
                entity_map = site_crawl.entity_intelligence.page_entity_evidence

            page_query_map: Dict[str, PageQueryEvidence] = {}

            # Inverse mapping structures: normalized_concept -> list of QueryPageEvidence
            concept_page_evidences: Dict[str, List[QueryPageEvidence]] = defaultdict(list)
            concept_display_names: Dict[str, str] = {}
            concept_natures: Dict[str, str] = {}

            # 1. Process each page to generate PageQueryEvidence
            for rec in records_to_process:
                url = rec.url
                sig_ev = signal_map.get(url)
                top_ev = topic_map.get(url)
                cnt_ev = content_map.get(url)
                ent_ev = entity_map.get(url)

                page_intel = QueryPageMappingEngine.evaluate(
                    url=url,
                    on_page=None,
                    search_signal_ev=sig_ev,
                    topic_intel_ev=top_ev,
                    content_ev=cnt_ev,
                    entity_ev=ent_ev,
                )
                page_query_map[url] = page_intel

                # Accumulate mapped concepts for inverse relationships
                for item in page_intel.mapped_concepts:
                    norm = item.normalized_concept
                    concept_page_evidences[norm].append(item)
                    if norm not in concept_display_names or len(item.concept) > len(concept_display_names[norm]):
                        concept_display_names[norm] = item.concept
                    if norm not in concept_natures:
                        concept_natures[norm] = item.concept_nature

            # 2. Build Inverse QueryPageRelationship items (Concept -> Supporting Pages)
            concept_relationships: List[QueryPageRelationship] = []
            overlaps: List[QueryPageRelationship] = []

            for norm, p_items in concept_page_evidences.items():
                disp_name = concept_display_names.get(norm, norm)
                nature = concept_natures.get(norm, "OBSERVED_CONCEPT")
                p_urls = [it.url for it in p_items]
                direct_pages = [it.url for it in p_items if it.evidence_strength == SearchSignalConfidence.DIRECT]
                supported_pages = [it.url for it in p_items if it.evidence_strength == SearchSignalConfidence.SUPPORTED]
                weak_pages = [it.url for it in p_items if it.evidence_strength == SearchSignalConfidence.WEAK]
                th1_pages = [it.url for it in p_items if it.has_title_or_h1]

                loc_set: Set[str] = set()
                ent_set: Set[str] = set()
                total_occurrences = 0

                for it in p_items:
                    total_occurrences += it.occurrences_count
                    for loc in it.evidence_locations:
                        loc_set.add(loc)
                    for ent in it.associated_entities:
                        ent_set.add(ent)

                # Sort supporting page evidences by strength and occurrences for bounded embedding (max 10 pages)
                def page_sort_key(it: QueryPageEvidence):
                    strength_order = {
                        SearchSignalConfidence.DIRECT: 0,
                        SearchSignalConfidence.SUPPORTED: 1,
                        SearchSignalConfidence.WEAK: 2,
                    }
                    return (
                        strength_order.get(it.evidence_strength, 3),
                        not it.has_title_or_h1,
                        -it.occurrences_count,
                    )

                sorted_p_items = sorted(p_items, key=page_sort_key)
                bounded_supporting_pages = sorted_p_items[:10]

                # 3. Detect Potential Multi-Page Topic Overlap Neutrally
                # Labeled as POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP (not cannibalization)
                overlap_status = None
                overlap_rationale = None

                is_multi_direct = len(direct_pages) >= 2
                is_multi_strong = (len(direct_pages) + len(supported_pages) >= 2) and (len(th1_pages) >= 1 or len(direct_pages) >= 1)

                if is_multi_direct or is_multi_strong:
                    overlap_status = "POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP"
                    overlap_rationale = (
                        f"Observed {len(p_urls)} crawled pages providing observable evidence for '{disp_name}': "
                        f"{len(direct_pages)} DIRECT, {len(supported_pages)} SUPPORTED, with {len(th1_pages)} pages featuring it in Title or H1."
                    )

                rel = QueryPageRelationship(
                    concept=disp_name,
                    normalized_concept=norm,
                    concept_nature=nature,
                    pages_count=len(p_urls),
                    page_urls=p_urls,
                    direct_pages=direct_pages,
                    supported_pages=supported_pages,
                    weak_pages=weak_pages,
                    evidence_locations=sorted(list(loc_set)),
                    total_occurrences=total_occurrences,
                    title_or_h1_pages=th1_pages,
                    associated_entities=sorted(list(ent_set)),
                    supporting_pages=bounded_supporting_pages,
                    overlap_status=overlap_status,
                    overlap_rationale=overlap_rationale,
                    provenance="query_page_mapping_engine",
                )
                concept_relationships.append(rel)
                if overlap_status:
                    overlaps.append(rel)

            # Sort relationships deterministically:
            # 1. Overlaps first
            # 2. direct_pages count descending
            # 3. pages_count descending
            # 4. total_occurrences descending
            # 5. concept alphabetical
            concept_relationships.sort(
                key=lambda r: (
                    r.overlap_status is None,
                    -len(r.direct_pages),
                    -r.pages_count,
                    -r.total_occurrences,
                    r.concept.lower(),
                )
            )

            overlaps.sort(
                key=lambda r: (
                    -len(r.direct_pages),
                    -r.pages_count,
                    -len(r.title_or_h1_pages),
                    r.concept.lower(),
                )
            )

            # 4. Synthesize Site-Wide Facts & Analyses
            facts: List[str] = [
                f"Evaluated {len(records_to_process)} crawled pages across {len(concept_relationships)} unique on-site evidenced concepts.",
                f"Identified {len(overlaps)} concepts with multi-page coverage across crawled pages.",
                f"Crawl completeness status: {site_crawl.completeness_status} (is_partial={is_partial}).",
            ]

            analyses: List[str] = [
                f"Neutral coverage assessment: {len(overlaps)} concepts exhibit POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP (multiple pages with DIRECT or SUPPORTED evidence).",
            ]
            if overlaps:
                overlap_samples = [f"'{r.concept}' ({len(r.direct_pages)} direct / {r.pages_count} pages)" for r in overlaps[:4]]
                analyses.append(f"Leading multi-page topic overlaps: {', '.join(overlap_samples)}.")

            intel = SiteQueryPageIntelligence(
                status="success",
                total_pages_evaluated=len(records_to_process),
                is_partial_crawl=is_partial,
                completeness_disclaimer=disclaimer,
                total_concepts_mapped=len(concept_relationships),
                multi_page_overlap_count=len(overlaps),
                concept_relationships=concept_relationships,
                page_query_evidence=page_query_map,
                overlaps=overlaps,
                terminology_nature="OBSERVED_WEBSITE_EVIDENCE",
                facts=facts,
                analyses=analyses,
            )

            site_crawl.query_page_intelligence = intel
            return intel

        except Exception as e:
            intel = SiteQueryPageIntelligence(
                status="error",
                error_message=f"Site query-page analysis failed: {e}",
                total_pages_evaluated=len(site_crawl.crawl_records),
                is_partial_crawl=is_partial,
                completeness_disclaimer="Query-page intelligence unavailable due to an evaluation error.",
                total_concepts_mapped=0,
                multi_page_overlap_count=0,
                concept_relationships=[],
                page_query_evidence={},
                overlaps=[],
                terminology_nature="OBSERVED_WEBSITE_EVIDENCE",
                facts=[f"Crawl records available: {len(site_crawl.crawl_records)}"],
                analyses=[f"Site query-page analyzer encountered an unhandled error: {e}"],
            )
            site_crawl.query_page_intelligence = intel
            return intel
