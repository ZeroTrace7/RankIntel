"""
Topic Intelligence Engine — Deterministic on-site concept and topic grouping (Layer A).
Consumes M9.1 SearchSignalEvidence, Phase 8 ContentEvidence, and Phase 8 EntityEvidence.
Reuses in-memory evidence with zero duplicate HTTP requests and zero external search queries.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
import re

from rankintel.models.schema import (
    SearchSignalEvidence,
    SearchSignalItem,
    SearchSignalConfidence,
    SearchSignalLocation,
    ContentEvidence,
    EntityEvidence,
    DetectedEntity,
    TopicEvidence,
    TopicTermMembership,
    TopicMembershipType,
    TopicRelationship,
    TopicRelationshipType,
    PageTopicIntelligence,
)
from rankintel.engines.search_signal_engine import normalize_term

# Common stopwords to exclude from token overlap matching
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "is", "are", "was", "were",
    "be", "being", "have", "has", "had", "do", "does", "did", "our", "your",
    "their", "its", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "we", "us", "you", "they", "them",
}


def tokenize_term(term: str) -> List[str]:
    """Tokenize normalized term into content tokens without linguistic stemming."""
    if not term:
        return []
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", term.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]


def is_word_bounded_substring(needle: str, haystack: str) -> bool:
    """Deterministic check if needle appears as a whole-word bounded substring within haystack."""
    if not needle or not haystack or len(needle) >= len(haystack):
        return False
    pattern = r"(?:^|\b|\s)" + re.escape(needle) + r"(?:$|\b|\s)"
    return bool(re.search(pattern, haystack))


class TopicIntelligenceEngine:
    """
    Evaluates single-page topic intelligence by clustering observed search signals
    and entity evidence using transparent, reproducible rules.
    """

    @classmethod
    def evaluate(
        cls,
        search_signal_ev: Optional[SearchSignalEvidence] = None,
        content_ev: Optional[ContentEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
        url: str = "",
    ) -> PageTopicIntelligence:
        """
        Derives deterministic concept groups, term memberships, and topic relationships
        from observed single-page evidence.
        """
        try:
            if not search_signal_ev or not search_signal_ev.signals:
                return PageTopicIntelligence(
                    url=url,
                    engine_source="topic_intelligence_engine",
                    status="skipped" if search_signal_ev is None else "success",
                    total_topics_derived=0,
                    total_terms_mapped=0,
                    topics=[],
                    relationships=[],
                    facts=["No search signal evidence available for topic derivation on this page."]
                    if search_signal_ev
                    else ["Search signal evidence was not provided."],
                    analyses=[],
                )

            signals = search_signal_ev.signals
            signal_by_term: Dict[str, SearchSignalItem] = {s.term: s for s in signals if s.term}

            # Seed entity anchors from Phase 8 EntityEvidence
            entity_names: Set[str] = set()
            entity_type_map: Dict[str, str] = {}
            if entity_ev and entity_ev.detected_entities:
                for ent in entity_ev.detected_entities:
                    n_ent = normalize_term(ent.name)
                    if n_ent and len(n_ent) >= 3:
                        entity_names.add(n_ent)
                        entity_type_map[n_ent] = (
                            ent.entity_type.value if hasattr(ent.entity_type, "value") else str(ent.entity_type)
                        )

            # Determine candidate topic anchors deterministically:
            # 1. Entity names from structured data or content
            # 2. Terms in Title or H1
            # 3. Terms in H2 with occurrences >= 2
            # 4. Recurring terms with occurrences >= 3
            anchor_candidates: Set[str] = set()

            for ent_name in entity_names:
                anchor_candidates.add(ent_name)

            for s in signals:
                t = s.term
                if not t or len(t) < 3:
                    continue
                has_title_or_h1 = any(loc in {SearchSignalLocation.TITLE, SearchSignalLocation.H1} for loc in s.locations)
                has_h2 = SearchSignalLocation.H2 in s.locations
                if has_title_or_h1:
                    anchor_candidates.add(t)
                elif has_h2 and s.total_occurrences >= 2:
                    anchor_candidates.add(t)
                elif s.total_occurrences >= 3:
                    anchor_candidates.add(t)

            # If no anchors qualify, select top signals by occurrences
            if not anchor_candidates:
                top_sorted = sorted(signals, key=lambda s: (-s.total_occurrences, len(s.term)))
                for s in top_sorted[:5]:
                    if s.term and len(s.term) >= 3:
                        anchor_candidates.add(s.term)

            # Build cluster structures: anchor -> list of (term, membership_type)
            cluster_terms: Dict[str, List[Tuple[str, TopicMembershipType]]] = defaultdict(list)
            term_to_cluster: Dict[str, str] = {}

            # Initialize each anchor with appropriate membership
            for anchor in sorted(list(anchor_candidates)):
                m_type = TopicMembershipType.ENTITY_MEMBER if anchor in entity_names else TopicMembershipType.EXACT
                cluster_terms[anchor].append((anchor, m_type))
                term_to_cluster[anchor] = anchor

            # Sort remaining signals to assign to anchors
            remaining_signals = [s for s in signals if s.term and s.term not in anchor_candidates]
            remaining_signals.sort(key=lambda s: (-s.total_occurrences, len(s.term)))

            for s in remaining_signals:
                t = s.term
                if not t or len(t) < 3:
                    continue

                assigned = False

                # A. Entity match / containment
                for ent_name in sorted(list(entity_names)):
                    if ent_name in cluster_terms:
                        if is_word_bounded_substring(ent_name, t) or is_word_bounded_substring(t, ent_name):
                            cluster_terms[ent_name].append((t, TopicMembershipType.ENTITY_MEMBER))
                            term_to_cluster[t] = ent_name
                            assigned = True
                            break
                if assigned:
                    continue

                # B. Phrase containment with topic anchors
                for anchor in sorted(list(anchor_candidates), key=lambda a: -len(a)):
                    if is_word_bounded_substring(anchor, t) or is_word_bounded_substring(t, anchor):
                        cluster_terms[anchor].append((t, TopicMembershipType.PHRASE_CONTAINMENT))
                        term_to_cluster[t] = anchor
                        assigned = True
                        break
                if assigned:
                    continue

                # C. Conservative exact token overlap (NO linguistic stemming)
                t_tokens = set(tokenize_term(t))
                if len(t_tokens) >= 2:
                    for anchor in sorted(list(anchor_candidates)):
                        a_tokens = set(tokenize_term(anchor))
                        if len(a_tokens) >= 2:
                            inter = t_tokens.intersection(a_tokens)
                            union = t_tokens.union(a_tokens)
                            jaccard = len(inter) / len(union) if union else 0.0
                            if (len(inter) >= 2 and jaccard >= 0.5) or jaccard >= 0.6:
                                cluster_terms[anchor].append((t, TopicMembershipType.TOKEN_OVERLAP))
                                term_to_cluster[t] = anchor
                                assigned = True
                                break
                if assigned:
                    continue

                # D. If unassigned and has structural presence (H2/H3/Meta), establish new topic
                has_subhead = any(
                    loc in {SearchSignalLocation.H2, SearchSignalLocation.H3, SearchSignalLocation.META_DESCRIPTION}
                    for loc in s.locations
                )
                if has_subhead or s.total_occurrences >= 2:
                    cluster_terms[t].append((t, TopicMembershipType.EXACT))
                    term_to_cluster[t] = t

            # Build TopicEvidence objects
            derived_topics: List[TopicEvidence] = []
            for anchor, members in cluster_terms.items():
                if not members:
                    continue

                seen_member_terms = set()
                term_memberships: List[TopicTermMembership] = []
                total_topic_occurrences = 0
                topic_locations: Set[str] = set()
                title_or_h1 = False
                associated_ents: Set[str] = set()

                for m_term, m_type in members:
                    if m_term in seen_member_terms:
                        continue
                    seen_member_terms.add(m_term)

                    sig_item = signal_by_term.get(m_term)
                    occ_count = sig_item.total_occurrences if sig_item else 1
                    total_topic_occurrences += occ_count

                    loc_strs: List[str] = []
                    conf_str = "SUPPORTED"
                    if sig_item:
                        loc_strs = [
                            loc.value if hasattr(loc, "value") else str(loc)
                            for loc in sig_item.locations
                        ]
                        conf_str = (
                            sig_item.confidence.value
                            if hasattr(sig_item.confidence, "value")
                            else str(sig_item.confidence)
                        )
                        if sig_item.is_entity and sig_item.entity_type:
                            associated_ents.add(f"{sig_item.term} ({sig_item.entity_type})")
                    else:
                        loc_strs = ["UNKNOWN"]

                    for l_str in loc_strs:
                        topic_locations.add(l_str)
                        if l_str in {"TITLE", "H1"}:
                            title_or_h1 = True

                    term_memberships.append(
                        TopicTermMembership(
                            term=sig_item.raw_term if sig_item else m_term,
                            normalized_term=m_term,
                            membership_type=m_type,
                            occurrences_count=occ_count,
                            structural_locations=sorted(loc_strs),
                            confidence=conf_str,
                            provenance="search_signal_engine",
                        )
                    )

                display_name = anchor
                matching_sig = signal_by_term.get(anchor)
                if matching_sig and matching_sig.raw_term:
                    display_name = matching_sig.raw_term

                derived_topics.append(
                    TopicEvidence(
                        topic_name=display_name,
                        normalized_name=anchor,
                        topic_nature="DERIVED_CONCEPT_GROUP",
                        evidence_nature="ANALYSIS",
                        supporting_terms=term_memberships,
                        pages_count=1,
                        page_urls=[url] if url else [],
                        occurrences_count=total_topic_occurrences,
                        structural_presence_count=len(topic_locations),
                        title_or_h1_presence=title_or_h1,
                        observed_locations=sorted(list(topic_locations)),
                        associated_entities=sorted(list(associated_ents)),
                        provenance="topic_intelligence_engine",
                    )
                )

            # Sort derived topics deterministically:
            # 1. title_or_h1_presence (True first)
            # 2. occurrences_count descending
            # 3. structural_presence_count descending
            # 4. topic_name alphabetical
            derived_topics.sort(
                key=lambda t: (
                    not t.title_or_h1_presence,
                    -t.occurrences_count,
                    -t.structural_presence_count,
                    t.topic_name.lower(),
                )
            )

            # Detect deterministic inter-topic relationships (Correction #3: Evidence-gated SUBTOPIC_OF)
            relationships: List[TopicRelationship] = []
            rel_pairs_seen: Set[Tuple[str, str]] = set()

            for i in range(len(derived_topics)):
                for j in range(i + 1, len(derived_topics)):
                    top_a = derived_topics[i]
                    top_b = derived_topics[j]
                    name_a = top_a.normalized_name
                    name_b = top_b.normalized_name

                    pair_key = (min(name_a, name_b), max(name_a, name_b))
                    if pair_key in rel_pairs_seen:
                        continue

                    # Check for lexical containment
                    a_in_b = is_word_bounded_substring(name_a, name_b)
                    b_in_a = is_word_bounded_substring(name_b, name_a)

                    if a_in_b or b_in_a:
                        parent_top = top_a if a_in_b else top_b
                        child_top = top_b if a_in_b else top_a

                        # Strictly gated SUBTOPIC_OF:
                        # Requires BOTH lexical containment AND structural hierarchy
                        # (parent in TITLE/H1 and child in H2/H3/MAIN_CONTENT)
                        parent_has_header = "TITLE" in parent_top.observed_locations or "H1" in parent_top.observed_locations
                        child_has_body_or_subhead = any(
                            loc in {"H2", "H3", "MAIN_CONTENT"} for loc in child_top.observed_locations
                        )

                        if parent_has_header and child_has_body_or_subhead:
                            rel_type = TopicRelationshipType.SUBTOPIC_OF
                            supp = [
                                f"Lexical containment ('{child_top.normalized_name}' contains '{parent_top.normalized_name}')",
                                f"Structural hierarchy (Parent in Title/H1; Child in {', '.join(child_top.observed_locations)})",
                            ]
                        else:
                            rel_type = TopicRelationshipType.LEXICAL_OVERLAP
                            supp = [
                                f"Lexical containment observed without full structural hierarchy confirmation"
                            ]

                        relationships.append(
                            TopicRelationship(
                                topic_a=child_top.topic_name,
                                topic_b=parent_top.topic_name,
                                relationship_type=rel_type,
                                evidence_nature="ANALYSIS",
                                co_occurrence_pages_count=1,
                                supporting_evidence=supp,
                            )
                        )
                        rel_pairs_seen.add(pair_key)
                        continue

                    # Check for shared entity association
                    shared_ents = set(top_a.associated_entities).intersection(set(top_b.associated_entities))
                    if shared_ents:
                        relationships.append(
                            TopicRelationship(
                                topic_a=top_a.topic_name,
                                topic_b=top_b.topic_name,
                                relationship_type=TopicRelationshipType.SHARED_ENTITY,
                                evidence_nature="ANALYSIS",
                                co_occurrence_pages_count=1,
                                supporting_evidence=[f"Shared entity association: {', '.join(sorted(shared_ents))}"],
                            )
                        )
                        rel_pairs_seen.add(pair_key)
                        continue

                    # Check for structural co-occurrence in Title or H1
                    shared_locs = set(top_a.observed_locations).intersection(set(top_b.observed_locations))
                    if "H1" in shared_locs or "TITLE" in shared_locs:
                        relationships.append(
                            TopicRelationship(
                                topic_a=top_a.topic_name,
                                topic_b=top_b.topic_name,
                                relationship_type=TopicRelationshipType.CO_OCCURRENCE,
                                evidence_nature="ANALYSIS",
                                co_occurrence_pages_count=1,
                                supporting_evidence=[f"Co-occurred in primary heading/title structure: {', '.join(sorted(shared_locs))}"],
                            )
                        )
                        rel_pairs_seen.add(pair_key)

            # Generate strict FACT and ANALYSIS separation
            all_mapped_terms = set(term_to_cluster.keys())
            facts: List[str] = [
                f"Observed {len(signals)} on-site search signal terms across {len(search_signal_ev.heading_terms) + len(search_signal_ev.title_terms)} structural heading & title elements.",
                f"Evidenced {len(entity_names)} entity candidate anchors from structured schema and content signals.",
            ]

            analyses: List[str] = [
                f"Derived {len(derived_topics)} deterministic concept groups mapping {len(all_mapped_terms)} observed terms.",
                f"Identified {len(relationships)} inter-topic relationships across lexical overlap and structural co-occurrence.",
            ]
            if derived_topics:
                top_sample = [f"'{t.topic_name}' ({t.occurrences_count} mentions)" for t in derived_topics[:3]]
                analyses.append(f"Leading concept groups by observable telemetry: {', '.join(top_sample)}.")

            return PageTopicIntelligence(
                url=url,
                engine_source="topic_intelligence_engine",
                status="success",
                total_topics_derived=len(derived_topics),
                total_terms_mapped=len(all_mapped_terms),
                topics=derived_topics,
                relationships=relationships,
                facts=facts,
                analyses=analyses,
            )

        except Exception as e:
            # Explicit error handling: never silently fail
            return PageTopicIntelligence(
                url=url,
                engine_source="topic_intelligence_engine",
                status="error",
                error_message=f"Topic intelligence evaluation failed: {e}",
                total_topics_derived=0,
                total_terms_mapped=0,
                topics=[],
                relationships=[],
                facts=[f"Evaluation attempted on URL: {url}"],
                analyses=[f"Topic intelligence encountered an unhandled error: {e}"],
            )
