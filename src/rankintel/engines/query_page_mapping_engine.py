"""
Query-Page Mapping Engine — Deterministic on-site concept to page mapping (Layer A).
Maps observed search-relevant concepts and derived topics to the crawled page providing evidence for them.
Operates strictly in-memory on already-crawled HTML and evidence without external APIs, search volume, or LLMs.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from urllib.parse import urlparse
import re

from rankintel.models.schema import (
    SearchSignalEvidence,
    SearchSignalItem,
    SearchSignalConfidence,
    SearchSignalLocation,
    PageTopicIntelligence,
    TopicEvidence,
    TopicTermMembership,
    ContentEvidence,
    EntityEvidence,
    OnPageEvidence,
    QueryPageEvidence,
    PageQueryEvidence,
)
from rankintel.engines.search_signal_engine import normalize_term, STOPWORDS


def tokenize_concept(text: str) -> List[str]:
    """Tokenize concept into content words excluding common stopwords."""
    if not text:
        return []
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]


class QueryPageMappingEngine:
    """
    Evaluates deterministic concept-to-page evidence mapping on a single crawled page.
    Triangulates M9.1 Search Signals, M9.2 Topic Intelligence, Phase 8 Content/Entity evidence,
    and on-page structure into strictly evidenced DIRECT / SUPPORTED / WEAK associations.
    """

    @classmethod
    def evaluate(
        cls,
        url: str = "",
        on_page: Optional[OnPageEvidence] = None,
        search_signal_ev: Optional[SearchSignalEvidence] = None,
        topic_intel_ev: Optional[PageTopicIntelligence] = None,
        content_ev: Optional[ContentEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
    ) -> PageQueryEvidence:
        """
        Derives deterministic concept-to-page mappings from observable single-page evidence.
        """
        try:
            if not search_signal_ev and not topic_intel_ev and not content_ev:
                return PageQueryEvidence(
                    url=url,
                    engine_source="query_page_mapping_engine",
                    status="skipped",
                    total_concepts_mapped=0,
                    direct_concepts_count=0,
                    supported_concepts_count=0,
                    weak_concepts_count=0,
                    mapped_concepts=[],
                    primary_concepts=[],
                    facts=["No search signal or topic evidence provided for query-page mapping."],
                    analyses=[],
                )

            signals = search_signal_ev.signals if (search_signal_ev and search_signal_ev.signals) else []
            topics = topic_intel_ev.topics if (topic_intel_ev and topic_intel_ev.topics) else []

            # In-memory index of signals by normalized term
            sig_by_term: Dict[str, SearchSignalItem] = {}
            for s in signals:
                if s.term:
                    sig_by_term[normalize_term(s.term)] = s

            # In-memory index of topics by normalized name
            topic_by_norm: Dict[str, TopicEvidence] = {}
            for t in topics:
                if t.normalized_name:
                    topic_by_norm[normalize_term(t.normalized_name)] = t

            # Extract detected entities from EntityEvidence
            entity_names: Set[str] = set()
            entity_type_map: Dict[str, str] = {}
            if entity_ev and entity_ev.detected_entities:
                for ent in entity_ev.detected_entities:
                    n_ent = normalize_term(ent.name)
                    if n_ent and len(n_ent) >= 2:
                        entity_names.add(n_ent)
                        entity_type_map[n_ent] = (
                            ent.entity_type.value if hasattr(ent.entity_type, "value") else str(ent.entity_type)
                        )

            # Extract URL path tokens
            parsed = urlparse(url)
            url_path_str = parsed.path.lower()
            url_path_tokens = set(tokenize_concept(url_path_str.replace("/", " ").replace("-", " ")))

            # Collect candidate concepts from:
            # 1. Derived topics (M9.2)
            # 2. Significant search signals (M9.1)
            # 3. Detected entities (Phase 8.2)
            candidate_concepts: Dict[str, Tuple[str, str]] = {}  # norm -> (display_name, nature)

            for t in topics:
                norm = normalize_term(t.normalized_name)
                if norm and len(norm) >= 3:
                    candidate_concepts[norm] = (t.topic_name, "EVIDENCED_TOPIC")

            for s in signals:
                norm = normalize_term(s.term)
                if not norm or len(norm) < 3:
                    continue
                # Include signals that have structural presence or repeated occurrence
                is_structural = any(
                    loc in {
                        SearchSignalLocation.TITLE,
                        SearchSignalLocation.H1,
                        SearchSignalLocation.H2,
                        SearchSignalLocation.H3,
                        SearchSignalLocation.STRUCTURED_DATA,
                        SearchSignalLocation.ENTITY,
                    }
                    for loc in s.locations
                )
                if is_structural or s.total_occurrences >= 2 or s.confidence == SearchSignalConfidence.DIRECT:
                    if norm not in candidate_concepts:
                        candidate_concepts[norm] = (s.raw_term or s.term, "OBSERVED_CONCEPT")

            for ent_norm in entity_names:
                if ent_norm and len(ent_norm) >= 3 and ent_norm not in candidate_concepts:
                    candidate_concepts[ent_norm] = (ent_norm.title(), "OBSERVED_CONCEPT")

            # Map each candidate concept to page evidence
            mapped_items: List[QueryPageEvidence] = []

            for norm_c, (disp_c, nature) in candidate_concepts.items():
                loc_set: Set[str] = set()
                snippets: List[str] = []
                associated_ents: List[str] = []
                schema_types: List[str] = []
                occurrences = 0
                has_th1 = False
                is_exact = False
                is_topic = False
                url_match = False

                # 1. Check Topic Membership
                matching_topic = topic_by_norm.get(norm_c)
                if matching_topic:
                    is_topic = True
                    occurrences += matching_topic.occurrences_count
                    for loc in matching_topic.observed_locations:
                        loc_set.add(loc)
                    if matching_topic.title_or_h1_presence:
                        has_th1 = True
                    for ent_str in matching_topic.associated_entities:
                        associated_ents.append(ent_str)
                    if matching_topic.supporting_terms:
                        member_samples = [m.term for m in matching_topic.supporting_terms[:3]]
                        snippets.append(
                            f"Derived topic cluster with {len(matching_topic.supporting_terms)} terms ({', '.join(member_samples)})"
                        )

                # 2. Check Search Signals
                matching_sig = sig_by_term.get(norm_c)
                if matching_sig:
                    is_exact = True
                    occurrences = max(occurrences, matching_sig.total_occurrences)
                    for loc in matching_sig.locations:
                        loc_val = loc.value if hasattr(loc, "value") else str(loc)
                        loc_set.add(loc_val)
                    if SearchSignalLocation.TITLE in matching_sig.locations or SearchSignalLocation.H1 in matching_sig.locations:
                        has_th1 = True
                    if matching_sig.is_entity and matching_sig.entity_type:
                        ent_label = f"{matching_sig.term} ({matching_sig.entity_type})"
                        if ent_label not in associated_ents:
                            associated_ents.append(ent_label)
                    for occ in matching_sig.occurrences[:3]:
                        loc_name = occ.location.value if hasattr(occ.location, "value") else str(occ.location)
                        raw_snip = occ.raw_text[:80].strip() if occ.raw_text else ""
                        if raw_snip:
                            snippets.append(f"{loc_name}: '{raw_snip}'")

                # 3. Check Entity Association
                if norm_c in entity_names:
                    loc_set.add("ENTITY")
                    ent_t = entity_type_map.get(norm_c, "Entity")
                    associated_ents.append(f"{disp_c} ({ent_t})")
                    snippets.append(f"Entity detected: '{disp_c}' of type {ent_t}")

                # 4. Check URL Path Evidence
                c_tokens = tokenize_concept(norm_c)
                if c_tokens and (all(tok in url_path_tokens for tok in c_tokens) or norm_c in url_path_str):
                    loc_set.add("URL_PATH")
                    url_match = True
                    snippets.append(f"URL path contains concept tokens: '{url_path_str}'")

                # 5. Check OnPage Metadata fallback
                if on_page:
                    if on_page.title and norm_c in on_page.title.lower():
                        loc_set.add("TITLE")
                        has_th1 = True
                    if on_page.h1_text and any(norm_c in h.lower() for h in on_page.h1_text):
                        loc_set.add("H1")
                        has_th1 = True

                # If no observable locations, skip ungrounded candidates
                if not loc_set:
                    continue

                # Ensure minimum occurrence count of 1
                occurrences = max(1, occurrences)

                # Determine Evidence Strength (DIRECT / SUPPORTED / WEAK)
                has_title = "TITLE" in loc_set
                has_h1 = "H1" in loc_set
                has_struct_data = "STRUCTURED_DATA" in loc_set
                has_entity = "ENTITY" in loc_set
                has_headings = bool(loc_set.intersection({"H2", "H3"}))
                has_main = "MAIN_CONTENT" in loc_set

                if has_title or has_h1 or (has_struct_data and occurrences >= 1) or (has_entity and has_th1):
                    strength = SearchSignalConfidence.DIRECT
                elif (has_headings and has_main) or (has_headings and url_match) or occurrences >= 2 or (is_topic and len(loc_set) >= 2):
                    strength = SearchSignalConfidence.SUPPORTED
                else:
                    strength = SearchSignalConfidence.WEAK

                # Bounded snippets (max 5)
                bounded_snippets = snippets[:5]

                mapped_items.append(
                    QueryPageEvidence(
                        concept=disp_c,
                        normalized_concept=norm_c,
                        concept_nature=nature,
                        url=url,
                        evidence_strength=strength,
                        evidence_locations=sorted(list(loc_set)),
                        occurrences_count=occurrences,
                        has_title_or_h1=has_th1,
                        is_exact_term_match=is_exact,
                        is_topic_membership=is_topic,
                        associated_entities=sorted(list(set(associated_ents))),
                        structured_data_types=sorted(list(set(schema_types))),
                        url_path_match=url_match,
                        supporting_snippets=bounded_snippets,
                        provenance="query_page_mapping_engine",
                    )
                )

            # Sort mapped concepts deterministically:
            # 1. DIRECT first, then SUPPORTED, then WEAK
            # 2. has_title_or_h1 (True first)
            # 3. occurrences_count descending
            # 4. evidence_locations count descending
            # 5. concept alphabetical
            def sort_key(item: QueryPageEvidence):
                strength_order = {
                    SearchSignalConfidence.DIRECT: 0,
                    SearchSignalConfidence.SUPPORTED: 1,
                    SearchSignalConfidence.WEAK: 2,
                }
                s_val = strength_order.get(item.evidence_strength, 3)
                return (
                    s_val,
                    not item.has_title_or_h1,
                    -item.occurrences_count,
                    -len(item.evidence_locations),
                    item.concept.lower(),
                )

            mapped_items.sort(key=sort_key)

            direct_count = sum(1 for m in mapped_items if m.evidence_strength == SearchSignalConfidence.DIRECT)
            supported_count = sum(1 for m in mapped_items if m.evidence_strength == SearchSignalConfidence.SUPPORTED)
            weak_count = sum(1 for m in mapped_items if m.evidence_strength == SearchSignalConfidence.WEAK)

            primary_concepts = [
                m.concept for m in mapped_items
                if m.evidence_strength == SearchSignalConfidence.DIRECT or m.has_title_or_h1
            ]

            facts: List[str] = [
                f"Mapped {len(mapped_items)} observed concepts with on-page evidence on {url}.",
                f"Identified {direct_count} DIRECT, {supported_count} SUPPORTED, and {weak_count} WEAK evidence concept associations.",
            ]
            if primary_concepts:
                facts.append(f"Primary structural concepts in Title/H1/Schema: {', '.join(primary_concepts[:4])}.")

            analyses: List[str] = [
                f"Concept-to-page evidence distribution: {direct_count} direct primary concepts, {supported_count} secondary supported concepts.",
            ]
            if mapped_items:
                top_sample = [f"'{m.concept}' ({m.evidence_strength.value})" for m in mapped_items[:4]]
                analyses.append(f"Leading mapped concepts: {', '.join(top_sample)}.")

            return PageQueryEvidence(
                url=url,
                engine_source="query_page_mapping_engine",
                status="success",
                total_concepts_mapped=len(mapped_items),
                direct_concepts_count=direct_count,
                supported_concepts_count=supported_count,
                weak_concepts_count=weak_count,
                mapped_concepts=mapped_items,
                primary_concepts=primary_concepts,
                facts=facts,
                analyses=analyses,
            )

        except Exception as e:
            return PageQueryEvidence(
                url=url,
                engine_source="query_page_mapping_engine",
                status="error",
                error_message=f"Query-page mapping failed: {e}",
                total_concepts_mapped=0,
                direct_concepts_count=0,
                supported_concepts_count=0,
                weak_concepts_count=0,
                mapped_concepts=[],
                primary_concepts=[],
                facts=[f"Evaluation attempted on URL: {url}"],
                analyses=[f"Query-page mapping encountered an error: {e}"],
            )
