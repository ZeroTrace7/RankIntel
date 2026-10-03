"""
Cannibalization Analyzer — Deterministic on-site multi-page topic competition analysis (Layer A).
Evaluates potential cannibalization indicators strictly based on observable on-site evidence:
requires multiple independent evidence dimensions (topic overlap + DIRECT/SUPPORTED query mapping +
title/H1 overlap + intent alignment + main-content concept overlap) before emitting POTENTIAL_CANNIBALIZATION_SIGNAL.
Topic overlap alone is strictly protected from false positives.
Never claims actual ranking cannibalization; recommendations explicitly require external search validation.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
import re

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteCannibalizationIntelligence,
    PageCannibalizationEvidence,
    PotentialCannibalizationItem,
    CannibalizationSignalType,
    SearchSignalConfidence,
    SearchIntentCategory,
    PageQueryEvidence,
    PageIntentEvidence,
)
from rankintel.engines.search_signal_engine import normalize_term, STOPWORDS


def tokenize_text(text: str) -> List[str]:
    """Tokenizes text into normalized content tokens excluding common stopwords."""
    if not text:
        return []
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]


def compute_jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Calculates Jaccard token set similarity."""
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def extract_page_text_elements(raw_html: Optional[str]) -> Tuple[str, str, List[str], int]:
    """Extracts (title, h1, list_of_h2s, word_count) safely from raw_html."""
    if not raw_html:
        return "", "", [], 0
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")
        title = soup.title.string.strip() if (soup.title and soup.title.string) else ""
        h1_el = soup.find("h1")
        h1 = h1_el.get_text(strip=True) if h1_el else ""
        h2s = [h2.get_text(strip=True) for h2 in soup.find_all("h2") if h2.get_text(strip=True)]
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        text = soup.get_text(separator=" ", strip=True)
        words = len(re.findall(r"\b\w+\b", text))
        return title, h1, h2s, words
    except Exception:
        t_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        title = t_match.group(1).strip() if t_match else ""
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", raw_html, re.IGNORECASE | re.DOTALL)
        h1 = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip() if h1_match else ""
        h2_matches = re.findall(r"<h2[^>]*>(.*?)</h2>", raw_html, re.IGNORECASE | re.DOTALL)
        h2s = [re.sub(r"<[^>]+>", "", m).strip() for m in h2_matches]
        clean_text = re.sub(r"<[^>]+>", " ", raw_html)
        words = len(re.findall(r"\b\w+\b", clean_text))
        return title, h1, h2s, words


class CannibalizationAnalyzer:
    """
    Analyzes cross-page competition and potential cannibalization signals from multi-page crawl evidence.
    Operates strictly in-memory without initiating any external network requests.
    """

    @classmethod
    def evaluate_page(
        cls,
        url: str,
        query_page_ev: Optional[PageQueryEvidence] = None,
        intent_ev: Optional[PageIntentEvidence] = None,
    ) -> PageCannibalizationEvidence:
        """
        Baseline single-page evaluation. Cross-page cannibalization requires multi-page
        crawl evidence with >= 2 crawled pages. Single-page audits return factual baseline.
        """
        facts = [
            f"Evaluated single page: {url}.",
            "Cross-page cannibalization analysis requires multi-page crawl evidence (>=2 pages)."
        ]
        analyses = [
            "OBSERVED_WEBSITE_EVIDENCE: Multi-page competition cannot be evaluated on an isolated single page."
        ]
        recommendations = [
            "Run a multi-page crawl audit (`--max-pages >= 2`) to evaluate cross-page topic overlap and potential cannibalization signals."
        ]
        return PageCannibalizationEvidence(
            url=url,
            engine_source="cannibalization_analyzer",
            status="success",
            potential_signals=[],
            observable_gaps=[],
            facts=facts,
            analyses=analyses,
            recommendations=recommendations,
        )

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteCannibalizationIntelligence:
        """
        Processes crawl records and M9.1-M9.4 intelligence in site_crawl to detect
        potential cannibalization signals with multi-dimensional evidence gating.
        Errors are explicitly captured and never silently swallowed.
        """
        is_partial = (
            (site_crawl.completeness_status != "CRAWL_COMPLETE")
            or (getattr(site_crawl, "remaining_frontier", 0) > 0)
            or (getattr(site_crawl, "pages_skipped", 0) > 0)
            or (getattr(site_crawl, "pages_blocked", 0) > 0)
        )
        disclaimer = (
            "Potential cannibalization analysis reflects crawled pages only; absence of overlapping pages in partial crawls does not prove absence of competition across uncrawled pages of the website."
            if is_partial
            else "Potential cannibalization analysis derived from complete crawl graph execution."
        )

        try:
            records = [
                rec for rec in site_crawl.crawl_records
                if (rec.status_code == 200 or rec.status_code is None) and rec.raw_html
            ]

            if len(records) < 2:
                facts = [
                    f"Crawl contained {len(records)} page(s). Multi-page cannibalization analysis requires at least 2 crawled pages."
                ]
                intel = SiteCannibalizationIntelligence(
                    status="partial" if is_partial else "success",
                    total_pages_evaluated=len(records),
                    is_partial_crawl=is_partial,
                    completeness_disclaimer=disclaimer,
                    potential_cannibalization_signals=[],
                    observable_topic_gaps=[],
                    competing_topics_count=0,
                    total_gaps_identified=0,
                    terminology_nature="OBSERVED_WEBSITE_EVIDENCE",
                    facts=facts,
                    analyses=["OBSERVED_TOPIC_OVERLAP: Insufficient crawled page count for cross-page competition analysis."],
                    recommendations=[],
                )
                if site_crawl.cannibalization_intelligence:
                    site_crawl.cannibalization_intelligence.potential_cannibalization_signals = intel.potential_cannibalization_signals
                    site_crawl.cannibalization_intelligence.competing_topics_count = intel.competing_topics_count
                else:
                    site_crawl.cannibalization_intelligence = intel
                return site_crawl.cannibalization_intelligence

            # Build in-memory lookups
            query_map: Dict[str, PageQueryEvidence] = {}
            if site_crawl.query_page_intelligence and site_crawl.query_page_intelligence.page_query_evidence:
                query_map = site_crawl.query_page_intelligence.page_query_evidence

            intent_map: Dict[str, PageIntentEvidence] = {}
            if site_crawl.topic_coverage_intelligence and site_crawl.topic_coverage_intelligence.page_intent_evidence:
                intent_map = site_crawl.topic_coverage_intelligence.page_intent_evidence

            # Extract title and H1 text per page
            page_titles: Dict[str, str] = {}
            page_h1s: Dict[str, str] = {}
            for rec in records:
                url = rec.url
                t = getattr(rec, "title", None)
                h1_list = getattr(rec, "h1_tags", None)
                if not t or not h1_list:
                    ext_t, ext_h1, _, _ = extract_page_text_elements(rec.raw_html)
                    page_titles[url] = t or ext_t
                    page_h1s[url] = (h1_list[0] if h1_list else ext_h1)
                else:
                    page_titles[url] = t
                    page_h1s[url] = h1_list[0]

            # 1. Candidate Topics from M9.2 & M9.3
            # Map topic -> list of supporting URLs with evidence strength
            topic_pages: Dict[str, List[Tuple[str, SearchSignalConfidence]]] = defaultdict(list)
            topic_display_names: Dict[str, str] = {}

            if site_crawl.query_page_intelligence and site_crawl.query_page_intelligence.concept_relationships:
                for rel in site_crawl.query_page_intelligence.concept_relationships:
                    norm = rel.normalized_concept
                    topic_display_names[norm] = rel.concept
                    for p_ev in rel.supporting_pages:
                        topic_pages[norm].append((p_ev.url, p_ev.evidence_strength))

            # Also check M9.2 topics if not already represented
            if site_crawl.topic_intelligence and site_crawl.topic_intelligence.topics:
                for t in site_crawl.topic_intelligence.topics:
                    norm = t.normalized_name
                    if norm not in topic_display_names:
                        topic_display_names[norm] = t.topic_name
                    for u in t.page_urls:
                        # Determine strength from query_map if present
                        strength = SearchSignalConfidence.SUPPORTED
                        if u in query_map:
                            for m in query_map[u].mapped_concepts:
                                if m.normalized_concept == norm:
                                    strength = m.evidence_strength
                                    break
                        if (u, strength) not in topic_pages[norm]:
                            topic_pages[norm].append((u, strength))

            # 2. Multi-Dimensional Evidence Gating for Cannibalization Signals
            potential_signals: List[PotentialCannibalizationItem] = []
            topic_overlap_analyses: List[str] = []
            seen_pairs: Set[Tuple[str, str, str]] = set()

            for norm_topic, pages_with_strength in topic_pages.items():
                display_topic = topic_display_names.get(norm_topic, norm_topic)
                # Deduplicate page entries
                unique_pages: Dict[str, SearchSignalConfidence] = {}
                for u, st in pages_with_strength:
                    if u not in unique_pages or st == SearchSignalConfidence.DIRECT:
                        unique_pages[u] = st

                if len(unique_pages) < 2:
                    continue

                urls = sorted(list(unique_pages.keys()))

                # Evaluate pairs
                for i in range(len(urls)):
                    for j in range(i + 1, len(urls)):
                        u1, u2 = urls[i], urls[j]
                        st1, st2 = unique_pages[u1], unique_pages[u2]

                        pair_key = (norm_topic, u1, u2)
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        # Dimension 1: Topic Evidence Strength
                        # Both pages must have DIRECT or SUPPORTED evidence (exclude WEAK or no mapping)
                        has_strong_evidence = (
                            st1 in (SearchSignalConfidence.DIRECT, SearchSignalConfidence.SUPPORTED)
                            and st2 in (SearchSignalConfidence.DIRECT, SearchSignalConfidence.SUPPORTED)
                        )
                        if not has_strong_evidence:
                            continue

                        # Dimension 2: Title & H1 Token Overlap
                        t1, t2 = page_titles.get(u1, ""), page_titles.get(u2, "")
                        h1_1, h1_2 = page_h1s.get(u1, ""), page_h1s.get(u2, "")

                        t1_toks = tokenize_text(t1)
                        t2_toks = tokenize_text(t2)
                        h1_toks = tokenize_text(h1_1)
                        h2_toks = tokenize_text(h1_2)

                        t_sim = compute_jaccard_similarity(t1_toks, t2_toks)
                        h_sim = compute_jaccard_similarity(h1_toks, h2_toks)

                        # Check for shared multi-word topic phrase in both titles
                        topic_toks = tokenize_text(display_topic)
                        multi_word_topic = len(topic_toks) >= 2
                        both_titles_contain_topic = (
                            multi_word_topic
                            and all(tok in t1_toks for tok in topic_toks)
                            and all(tok in t2_toks for tok in topic_toks)
                        )

                        # Substantial title/H1 overlap requirement:
                        # Jaccard >= 0.35 OR (multi-word topic in both titles AND Jaccard >= 0.20)
                        has_title_overlap = (
                            t_sim >= 0.35
                            or h_sim >= 0.35
                            or (both_titles_contain_topic and (t_sim >= 0.20 or h_sim >= 0.20))
                        )

                        if not has_title_overlap:
                            # Does NOT meet title overlap gate: record topic overlap neutrally
                            if len(topic_overlap_analyses) < 4:
                                topic_overlap_analyses.append(
                                    f"OBSERVED_TOPIC_OVERLAP: Topic '{display_topic}' referenced across '{u1}' and '{u2}' with distinct title/heading hierarchies (Title Jaccard: {t_sim:.2f}); represents differentiated context rather than competing targeting."
                                )
                            continue

                        # Dimension 3: Search Intent Alignment (from M9.4)
                        p_intent_1 = intent_map.get(u1)
                        p_intent_2 = intent_map.get(u2)

                        intent_1_cat = p_intent_1.primary_observed_intent_signal if p_intent_1 else SearchIntentCategory.UNSPECIFIED
                        intent_2_cat = p_intent_2.primary_observed_intent_signal if p_intent_2 else SearchIntentCategory.UNSPECIFIED

                        # Compare intents:
                        # Similar if exact match (excluding unspecified) or mutually commercial/transactional
                        intents_match = False
                        shared_intent_result = intent_1_cat

                        if intent_1_cat != SearchIntentCategory.UNSPECIFIED and intent_1_cat == intent_2_cat:
                            intents_match = True
                            shared_intent_result = intent_1_cat
                        elif {intent_1_cat, intent_2_cat} == {SearchIntentCategory.COMMERCIAL, SearchIntentCategory.TRANSACTIONAL}:
                            # Compatible commercial/transactional search intent
                            intents_match = True
                            shared_intent_result = SearchIntentCategory.COMMERCIAL

                        if not intents_match:
                            # Differing intents indicate deliberate funnel segmentation
                            # E.g. informational guide vs transactional quote page -> DO NOT FLAG CANNIBALIZATION
                            if len(topic_overlap_analyses) < 4:
                                i1_name = intent_1_cat.value if hasattr(intent_1_cat, "value") else str(intent_1_cat)
                                i2_name = intent_2_cat.value if hasattr(intent_2_cat, "value") else str(intent_2_cat)
                                topic_overlap_analyses.append(
                                    f"OBSERVED_INTENT_OVERLAP: Topic '{display_topic}' appears on '{u1}' ({i1_name}) and '{u2}' ({i2_name}). Differing intent categories represent legitimate intent segmentation; not flagged as cannibalization."
                                )
                            continue

                        # Dimension 4: Main-Content Concept Overlap
                        q1_concepts = set(
                            [m.normalized_concept for m in query_map[u1].mapped_concepts]
                            if u1 in query_map else []
                        )
                        q2_concepts = set(
                            [m.normalized_concept for m in query_map[u2].mapped_concepts]
                            if u2 in query_map else []
                        )
                        shared_concepts = sorted(list(q1_concepts & q2_concepts))

                        # At least 1 shared concept beyond the topic itself, or the topic itself plus common tokens
                        has_concept_overlap = (len(shared_concepts) >= 1)

                        if not has_concept_overlap:
                            continue

                        # ALL 4 DIMENSIONS SATISFIED -> Emit POTENTIAL_CANNIBALIZATION_SIGNAL
                        competing_urls = [u1, u2]
                        snippets = {
                            u1: f"Title: {t1 or 'None'} | H1: {h1_1 or 'None'}",
                            u2: f"Title: {t2 or 'None'} | H1: {h1_2 or 'None'}",
                        }
                        overall_strength = (
                            SearchSignalConfidence.DIRECT
                            if (st1 == SearchSignalConfidence.DIRECT and st2 == SearchSignalConfidence.DIRECT)
                            else SearchSignalConfidence.SUPPORTED
                        )

                        shared_concepts_display = [
                            c.replace("-", " ") for c in shared_concepts[:8]
                        ]

                        intent_val = shared_intent_result.value if hasattr(shared_intent_result, "value") else str(shared_intent_result)
                        rationale = (
                            f"POTENTIAL_CANNIBALIZATION_SIGNAL: Both pages exhibit {overall_strength.value} query mapping for topic '{display_topic}', "
                            f"share {t_sim:.0%} title similarity and {h_sim:.0%} H1 similarity, align on '{intent_val}' intent, "
                            f"and share main-content concepts [{', '.join(shared_concepts_display[:3])}]."
                        )

                        recommendation = (
                            f"REQUIRES_EXTERNAL_SEARCH_VALIDATION: Review Google Search Console queries and SERP rankings for '{u1}' and '{u2}' "
                            f"to verify whether search engines split impressions or alternate rankings for '{display_topic}'. "
                            f"If corroborated externally, evaluate consolidating content into a single authoritative asset or differentiating title tags and intent focus."
                        )

                        item = PotentialCannibalizationItem(
                            topic=display_topic,
                            normalized_topic=norm_topic,
                            competing_urls=competing_urls,
                            signal_type=CannibalizationSignalType.POTENTIAL_CANNIBALIZATION_SIGNAL,
                            evidence_strength=overall_strength,
                            shared_intent=shared_intent_result,
                            title_overlap_ratio=round(t_sim, 3),
                            h1_overlap_ratio=round(h_sim, 3),
                            shared_concepts=shared_concepts_display,
                            title_h1_snippets=snippets,
                            rationale=rationale,
                            recommendation=recommendation,
                            provenance="cannibalization_analyzer",
                        )
                        potential_signals.append(item)

                        if len(potential_signals) >= 15:
                            break
                    if len(potential_signals) >= 15:
                        break
                if len(potential_signals) >= 15:
                    break

            # 3. Formulate Facts and Analyses
            facts: List[str] = [
                f"Evaluated {len(records)} crawled pages across {len(topic_pages)} evidenced topic clusters.",
                f"Identified {len(potential_signals)} potential cannibalization signals satisfying the multi-dimensional evidence gate."
            ]
            analyses: List[str] = []

            if potential_signals:
                comp_topics = sorted(list(set(s.topic for s in potential_signals)))
                sample_topics = ", ".join(comp_topics[:3])
                analyses.append(
                    f"POTENTIAL_CANNIBALIZATION_SIGNAL: Multi-page competition detected across {len(potential_signals)} page pair(s) for topics [{sample_topics}] with shared intent and substantial title/H1 overlap."
                )

            analyses.extend(topic_overlap_analyses[:3])

            recommendations: List[str] = []
            if potential_signals:
                recommendations.append(
                    "REQUIRES_EXTERNAL_SEARCH_VALIDATION: Prioritize external verification in Google Search Console for flagged competing page pairs before making structural canonical or consolidation changes."
                )

            # Preserve or attach to site_crawl.cannibalization_intelligence
            existing_intel = getattr(site_crawl, "cannibalization_intelligence", None)
            existing_gaps = existing_intel.observable_topic_gaps if existing_intel else []
            existing_gaps_count = existing_intel.total_gaps_identified if existing_intel else 0

            intel = SiteCannibalizationIntelligence(
                status="partial" if is_partial else "success",
                total_pages_evaluated=len(records),
                is_partial_crawl=is_partial,
                completeness_disclaimer=disclaimer,
                potential_cannibalization_signals=potential_signals,
                observable_topic_gaps=existing_gaps,
                competing_topics_count=len(set(s.topic for s in potential_signals)),
                total_gaps_identified=existing_gaps_count,
                terminology_nature="OBSERVED_WEBSITE_EVIDENCE",
                facts=facts + (existing_intel.facts if existing_intel else []),
                analyses=analyses + (existing_intel.analyses if existing_intel else []),
                recommendations=recommendations + (existing_intel.recommendations if existing_intel else []),
            )

            site_crawl.cannibalization_intelligence = intel
            return intel

        except Exception as e:
            # Capture error explicitly; never silently swallow
            error_intel = SiteCannibalizationIntelligence(
                status="error",
                error_message=f"Cannibalization analysis failed: {e}",
                is_partial_crawl=is_partial,
                completeness_disclaimer="Cannibalization intelligence unavailable due to an analysis error.",
                total_pages_evaluated=0,
                potential_cannibalization_signals=[],
                observable_topic_gaps=[],
                facts=[f"Error during cannibalization analysis: {e}"],
                analyses=["OBSERVED_WEBSITE_EVIDENCE: Analysis aborted due to processing exception."],
                recommendations=["Investigate analyzer exception diagnostics; retry crawl with valid DOM records."],
            )
            site_crawl.cannibalization_intelligence = error_intel
            return error_intel
