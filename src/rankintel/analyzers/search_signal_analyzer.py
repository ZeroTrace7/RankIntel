"""
Site Search Signal Analyzer — Cross-page multi-page crawl search signal intelligence (Layer A).
Aggregates recurring on-site concepts, maps cross-page terminology, and preserves
explicit boundaries between observed website terminology and external search query data.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
from urllib.parse import urlparse

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteSearchSignalIntelligence,
    SearchSignalEvidence,
    RecurringConceptItem,
    SearchSignalStatementType,
    SearchSignalLocation,
)
from rankintel.engines.search_signal_engine import SearchSignalEngine, normalize_term


class SiteSearchSignalAnalyzer:
    """
    Analyzes site-wide search signals and recurring concepts from CrawlRecord raw_html
    without initiating any network requests.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteSearchSignalIntelligence:
        """
        Processes all crawled HTML documents in site_crawl to aggregate recurring evidenced
        search concepts, prominent terms, and per-page signal profiles.
        """
        page_signal_evidence: Dict[str, SearchSignalEvidence] = {}

        # Aggregation structures: concept -> metadata
        concept_pages: Dict[str, Set[str]] = defaultdict(set)
        concept_prominent_pages: Dict[str, Set[str]] = defaultdict(set)
        concept_occurrences: Dict[str, int] = defaultdict(int)
        concept_locations: Dict[str, Set[str]] = defaultdict(set)
        concept_entity_meta: Dict[str, Tuple[bool, Optional[str]]] = {}
        concept_raw_forms: Dict[str, str] = {}

        records_to_process = [
            rec for rec in site_crawl.crawl_records
            if (rec.status_code == 200 or rec.status_code is None) and rec.raw_html
        ]

        # Extract per-page content & entity evidence if already populated on site_crawl
        content_map = {}
        if site_crawl.content_intelligence and site_crawl.content_intelligence.page_content_evidence:
            content_map = site_crawl.content_intelligence.page_content_evidence

        entity_map = {}
        if site_crawl.entity_intelligence and site_crawl.entity_intelligence.page_entity_evidence:
            entity_map = site_crawl.entity_intelligence.page_entity_evidence

        # Process each crawled page
        for rec in records_to_process:
            url = rec.url
            html = rec.raw_html
            cnt_ev = content_map.get(url)
            ent_ev = entity_map.get(url)

            # Evaluate per-page search signals
            page_ev = SearchSignalEngine.evaluate(
                raw_html=html,
                url=url,
                content_ev=cnt_ev,
                entity_ev=ent_ev,
            )
            page_signal_evidence[url] = page_ev

            # Aggregate terms for site-level analysis
            for sig in page_ev.signals:
                c = sig.term
                if not c or len(c) < 3:
                    continue
                concept_pages[c].add(url)
                concept_occurrences[c] += sig.total_occurrences
                for loc in sig.locations:
                    concept_locations[c].add(loc.value if hasattr(loc, "value") else str(loc))
                if sig.prominence_locations:
                    concept_prominent_pages[c].add(url)
                if sig.is_entity:
                    concept_entity_meta[c] = (True, sig.entity_type)
                if c not in concept_raw_forms or len(sig.raw_term) > len(concept_raw_forms[c]):
                    concept_raw_forms[c] = sig.raw_term

        # Identify recurring concepts:
        # A concept is recurring if it appears across >= 2 pages (or if total pages crawled == 1, appears >= 3 times)
        min_pages_threshold = 2 if len(records_to_process) > 1 else 1
        recurring_items: List[RecurringConceptItem] = []

        for c, pages in concept_pages.items():
            pages_count = len(pages)
            total_occ = concept_occurrences[c]
            if pages_count >= min_pages_threshold:
                is_ent, ent_type = concept_entity_meta.get(c, (False, None))
                recurring_items.append(
                    RecurringConceptItem(
                        concept=concept_raw_forms.get(c, c),
                        normalized_concept=c,
                        pages_count=pages_count,
                        page_urls=sorted(list(pages)),
                        prominent_pages=sorted(list(concept_prominent_pages[c])),
                        total_occurrences=total_occ,
                        observed_locations=sorted(list(concept_locations[c])),
                        is_entity=is_ent,
                        entity_type=ent_type,
                        signal_nature=SearchSignalStatementType.ANALYSIS,
                    )
                )

        # Sort recurring concepts: first by pages_count descending, then by total_occurrences descending
        recurring_items.sort(key=lambda item: (item.pages_count, item.total_occurrences), reverse=True)

        # Top evidenced terms across the site
        site_top_evidenced_terms: List[Dict[str, Any]] = []
        for item in recurring_items[:25]:
            site_top_evidenced_terms.append({
                "concept": item.concept,
                "normalized": item.normalized_concept,
                "pages_count": item.pages_count,
                "total_occurrences": item.total_occurrences,
                "is_entity": item.is_entity,
                "entity_type": item.entity_type,
            })

        # Generate strict FACT and ANALYSIS statements
        facts: List[str] = [
            f"Evaluated {len(records_to_process)} crawled pages for on-site search signals.",
            f"Discovered {len(concept_pages)} unique normalized terms across the crawl graph.",
            f"Identified {len(recurring_items)} recurring concepts evidenced across multiple page boundaries.",
        ]

        analyses: List[str] = []
        if recurring_items:
            top_3_names = [f"'{it.concept}' ({it.pages_count} pages)" for it in recurring_items[:3]]
            analyses.append(f"Primary recurring site terminology: {', '.join(top_3_names)}.")
            entity_recur = [it.concept for it in recurring_items if it.is_entity]
            if entity_recur:
                analyses.append(f"Entity concepts recurring across pages: {', '.join(entity_recur[:4])}.")

        intel = SiteSearchSignalIntelligence(
            total_pages_evaluated=len(records_to_process),
            total_unique_concepts=len(concept_pages),
            recurring_concepts_count=len(recurring_items),
            recurring_concepts=recurring_items[:50],  # Bounded to top 50
            site_top_evidenced_terms=site_top_evidenced_terms,
            page_signal_evidence=page_signal_evidence,
            terminology_nature="OBSERVED_WEBSITE_TERMINOLOGY",
            external_query_data_status="NOT_AVAILABLE_LAYER_A",
            facts=facts,
            analyses=analyses,
        )

        site_crawl.search_signal_intelligence = intel
        return intel
