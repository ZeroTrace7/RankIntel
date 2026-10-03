"""
Search Gap Analyzer — Deterministic on-site topic & concept coverage gap analysis (Layer A).
Evaluates observable coverage asymmetries and heading depth gaps between related crawled pages and topics.
Strictly relies on observable website evidence without external search volume, rankings, or keyword databases.
Never claims the website has a "missing keyword" or missed search demand.
Safeguards partial crawls so absence on crawled pages is never treated as proof of a site-wide gap.
All recommendations explicitly mandate external search validation before content expansion.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
import re

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteCannibalizationIntelligence,
    ObservableTopicGapItem,
    TopicGapType,
    PageQueryEvidence,
    QueryPageEvidence,
    TopicEvidence,
    TopicRelationship,
)
from rankintel.engines.search_signal_engine import normalize_term, STOPWORDS


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


class SearchGapAnalyzer:
    """
    Analyzes observable on-site concept coverage gaps and structural asymmetries
    across crawled pages and topic clusters. Operates strictly in-memory.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteCannibalizationIntelligence:
        """
        Processes crawl records and M9.1-M9.4 intelligence in site_crawl to detect
        observable on-site topic coverage gaps.
        Errors are explicitly captured and never silently swallowed.
        """
        is_partial = (
            (site_crawl.completeness_status != "CRAWL_COMPLETE")
            or (getattr(site_crawl, "remaining_frontier", 0) > 0)
            or (getattr(site_crawl, "pages_skipped", 0) > 0)
            or (getattr(site_crawl, "pages_blocked", 0) > 0)
        )
        disclaimer = (
            "Observed topic gaps reflect crawled pages only; absence of coverage for any concept in partial crawls does not indicate lack of content or intent on uncrawled pages of the website."
            if is_partial
            else "Observed topic gaps derived from complete crawl graph execution."
        )

        try:
            records = [
                rec for rec in site_crawl.crawl_records
                if (rec.status_code == 200 or rec.status_code is None) and rec.raw_html
            ]

            if len(records) < 2:
                # Single page or no records: cross-page gaps cannot be determined
                if not site_crawl.cannibalization_intelligence:
                    from rankintel.analyzers.cannibalization_analyzer import CannibalizationAnalyzer
                    return CannibalizationAnalyzer.analyze_site(site_crawl)
                return site_crawl.cannibalization_intelligence

            # In-memory evidence lookups
            query_map: Dict[str, PageQueryEvidence] = {}
            if site_crawl.query_page_intelligence and site_crawl.query_page_intelligence.page_query_evidence:
                query_map = site_crawl.query_page_intelligence.page_query_evidence

            # Collect concepts per page: page_url -> Set[normalized_concept]
            page_concepts: Dict[str, Set[str]] = defaultdict(set)
            page_concept_display: Dict[str, Dict[str, str]] = defaultdict(dict)
            for url, q_ev in query_map.items():
                for m in q_ev.mapped_concepts:
                    norm = m.normalized_concept
                    page_concepts[url].add(norm)
                    page_concept_display[url][norm] = m.concept

            # Page content word count and headings
            page_word_counts: Dict[str, int] = {}
            page_h2_counts: Dict[str, int] = {}
            page_h2_texts: Dict[str, List[str]] = defaultdict(list)

            if site_crawl.content_intelligence and site_crawl.content_intelligence.page_content_evidence:
                for url, cnt in site_crawl.content_intelligence.page_content_evidence.items():
                    page_word_counts[url] = cnt.main_content_word_count
                    page_h2_counts[url] = cnt.heading_structure.h2_count if cnt.heading_structure else 0
                    if cnt.heading_structure and cnt.heading_structure.heading_hierarchy:
                        page_h2_texts[url] = [
                            h.heading_text for h in cnt.heading_structure.heading_hierarchy
                            if h.level == 2
                        ]
            else:
                for rec in records:
                    url = rec.url
                    wc = getattr(rec, "word_count", None)
                    h2s = getattr(rec, "h2_tags", None)
                    if wc is None or h2s is None:
                        _, _, ext_h2s, ext_words = extract_page_text_elements(rec.raw_html)
                        page_word_counts[url] = wc if wc is not None else ext_words
                        page_h2_counts[url] = len(h2s) if h2s is not None else len(ext_h2s)
                        page_h2_texts[url] = h2s if h2s is not None else ext_h2s
                    else:
                        page_word_counts[url] = wc
                        page_h2_counts[url] = len(h2s)
                        page_h2_texts[url] = h2s

            # 1. Intra-Topic Concept Coverage Asymmetry
            # Identify topics with multiple supporting pages
            topic_pages: Dict[str, List[str]] = defaultdict(list)
            topic_display_names: Dict[str, str] = {}

            if site_crawl.topic_intelligence and site_crawl.topic_intelligence.topics:
                for t in site_crawl.topic_intelligence.topics:
                    norm = t.normalized_name
                    topic_display_names[norm] = t.topic_name
                    topic_pages[norm].extend(t.page_urls)

            if site_crawl.query_page_intelligence and site_crawl.query_page_intelligence.concept_relationships:
                for rel in site_crawl.query_page_intelligence.concept_relationships:
                    norm = rel.normalized_concept
                    if norm not in topic_display_names:
                        topic_display_names[norm] = rel.concept
                    topic_pages[norm].extend(rel.page_urls)

            observable_gaps: List[ObservableTopicGapItem] = []
            seen_gap_keys: Set[Tuple[str, str, str]] = set()

            for norm_topic, urls in topic_pages.items():
                display_topic = topic_display_names.get(norm_topic, norm_topic)
                unique_urls = sorted(list(set(urls)))
                if len(unique_urls) < 2:
                    continue

                # Compare pairs of pages covering this topic
                for i in range(len(unique_urls)):
                    for j in range(len(unique_urls)):
                        if i == j:
                            continue
                        u_source = unique_urls[i]   # Page with potential gap
                        u_related = unique_urls[j]  # Page with observed broader coverage

                        gap_key = (norm_topic, u_source, u_related)
                        if gap_key in seen_gap_keys:
                            continue

                        concepts_source = page_concepts.get(u_source, set())
                        concepts_related = page_concepts.get(u_related, set())

                        # Identify concepts present on related page but missing on source page
                        missing_norms = [c for c in concepts_related if c not in concepts_source and c != norm_topic]

                        if missing_norms and len(missing_norms) >= 2:
                            seen_gap_keys.add(gap_key)
                            # Convert to display strings
                            disp_missing = [
                                page_concept_display[u_related].get(c, c.replace("-", " "))
                                for c in missing_norms[:6]
                            ]
                            disp_covered = [
                                page_concept_display[u_source].get(c, c.replace("-", " "))
                                for c in list(concepts_source)[:6]
                            ]

                            rationale = (
                                f"OBSERVED_TOPIC_GAP: Related page '{u_related}' provides on-site coverage for concepts "
                                f"[{', '.join(disp_missing[:3])}] under topic '{display_topic}', which are unmentioned on '{u_source}'."
                            )

                            recommendation = (
                                f"REQUIRES_EXTERNAL_SEARCH_VALIDATION: Review whether concept '{disp_missing[0]}' represents target audience search "
                                f"queries before expanding coverage on '{u_source}'. Observable on-site evidence indicates related page '{u_related}' "
                                f"covers this concept while this page omits it."
                            )

                            item = ObservableTopicGapItem(
                                topic=display_topic,
                                normalized_topic=norm_topic,
                                source_url=u_source,
                                related_url=u_related,
                                gap_type=TopicGapType.OBSERVED_TOPIC_GAP,
                                covered_concepts=disp_covered,
                                missing_concepts=disp_missing,
                                gap_nature="OBSERVED_TOPIC_GAP",
                                rationale=rationale,
                                recommendation=recommendation,
                                provenance="search_gap_analyzer",
                            )
                            observable_gaps.append(item)

                            if len(observable_gaps) >= 10:
                                break
                    if len(observable_gaps) >= 10:
                        break
                if len(observable_gaps) >= 10:
                    break

            # 2. Structural Heading & Depth Asymmetry
            for norm_topic, urls in topic_pages.items():
                if len(observable_gaps) >= 15:
                    break
                display_topic = topic_display_names.get(norm_topic, norm_topic)
                unique_urls = sorted(list(set(urls)))
                if len(unique_urls) < 2:
                    continue

                for i in range(len(unique_urls)):
                    for j in range(len(unique_urls)):
                        if i == j or len(observable_gaps) >= 15:
                            continue
                        u_source = unique_urls[i]
                        u_related = unique_urls[j]

                        words_src = page_word_counts.get(u_source, 0)
                        words_rel = page_word_counts.get(u_related, 0)
                        h2_src = page_h2_counts.get(u_source, 0)
                        h2_rel = page_h2_counts.get(u_related, 0)

                        # Check for substantial depth asymmetry:
                        # Related page has deep coverage (>=3 H2s), source page has thin coverage (<=1 H2 or missing H2s)
                        if (h2_rel >= 3 and h2_src <= 1) and (words_rel >= 300 or words_rel >= 2 * max(words_src, 1) or h2_src == 0):
                            gap_key = (f"depth_{norm_topic}", u_source, u_related)
                            if gap_key in seen_gap_keys:
                                continue
                            seen_gap_keys.add(gap_key)

                            missing_h2s = [
                                h for h in page_h2_texts.get(u_related, [])
                                if h not in page_h2_texts.get(u_source, [])
                            ][:4]

                            rationale = (
                                f"CONTENT_DEPTH_ASYMMETRY: Page '{u_related}' exhibits {words_rel} words and {h2_rel} H2 sections for topic '{display_topic}', "
                                f"whereas related page '{u_source}' contains only {words_src} words and {h2_src} H2 heading(s)."
                            )

                            recommendation = (
                                f"REQUIRES_EXTERNAL_SEARCH_VALIDATION: Evaluate user search query expectations before expanding content depth on '{u_source}'. "
                                f"Observable on-site structure demonstrates comprehensive heading depth on sister page '{u_related}'."
                            )

                            item = ObservableTopicGapItem(
                                topic=display_topic,
                                normalized_topic=norm_topic,
                                source_url=u_source,
                                related_url=u_related,
                                gap_type=TopicGapType.CONTENT_DEPTH_ASYMMETRY,
                                covered_concepts=page_h2_texts.get(u_source, [])[:4],
                                missing_concepts=missing_h2s,
                                gap_nature="OBSERVED_TOPIC_GAP",
                                rationale=rationale,
                                recommendation=recommendation,
                                provenance="search_gap_analyzer",
                            )
                            observable_gaps.append(item)

            # 3. Formulate Facts, Analyses, Recommendations
            facts: List[str] = [
                f"Evaluated cross-page concept coverage across {len(records)} crawled pages.",
                f"Identified {len(observable_gaps)} observable on-site topic gap(s) and content depth asymmetries."
            ]
            analyses: List[str] = []

            if observable_gaps:
                gap_topics = sorted(list(set(g.topic for g in observable_gaps)))
                analyses.append(
                    f"OBSERVED_TOPIC_GAP: Observable content coverage asymmetries detected across topics [{', '.join(gap_topics[:3])}] between sister pages."
                )

            recommendations: List[str] = []
            if observable_gaps:
                recommendations.append(
                    "REQUIRES_EXTERNAL_SEARCH_VALIDATION: Confirm external search demand and target audience queries before creating new pages or expanding sub-topic sections."
                )

            # Integrate with site_crawl.cannibalization_intelligence
            existing_intel = getattr(site_crawl, "cannibalization_intelligence", None)
            existing_signals = existing_intel.potential_cannibalization_signals if existing_intel else []
            comp_count = existing_intel.competing_topics_count if existing_intel else 0

            combined_facts = (existing_intel.facts if existing_intel else []) + facts
            combined_analyses = (existing_intel.analyses if existing_intel else []) + analyses
            combined_recs = (existing_intel.recommendations if existing_intel else []) + recommendations

            # Deduplicate items in facts/analyses/recs
            def dedup(lst: List[str]) -> List[str]:
                seen = set()
                out = []
                for x in lst:
                    if x not in seen:
                        seen.add(x)
                        out.append(x)
                return out

            intel = SiteCannibalizationIntelligence(
                status="partial" if is_partial else "success",
                total_pages_evaluated=len(records),
                is_partial_crawl=is_partial,
                completeness_disclaimer=disclaimer,
                potential_cannibalization_signals=existing_signals,
                observable_topic_gaps=observable_gaps,
                competing_topics_count=comp_count,
                total_gaps_identified=len(observable_gaps),
                terminology_nature="OBSERVED_WEBSITE_EVIDENCE",
                facts=dedup(combined_facts),
                analyses=dedup(combined_analyses),
                recommendations=dedup(combined_recs),
            )

            site_crawl.cannibalization_intelligence = intel
            return intel

        except Exception as e:
            # Capture error explicitly; never silently swallow
            existing_intel = getattr(site_crawl, "cannibalization_intelligence", None)
            existing_signals = existing_intel.potential_cannibalization_signals if existing_intel else []

            error_intel = SiteCannibalizationIntelligence(
                status="error",
                error_message=f"Search gap analysis failed: {e}",
                is_partial_crawl=is_partial,
                completeness_disclaimer="Search gap intelligence unavailable due to an analysis error.",
                total_pages_evaluated=0,
                potential_cannibalization_signals=existing_signals,
                observable_topic_gaps=[],
                facts=[f"Error during search gap analysis: {e}"],
                analyses=["OBSERVED_WEBSITE_EVIDENCE: Gap analysis aborted due to processing exception."],
                recommendations=["Investigate analyzer exception diagnostics; retry crawl with valid DOM records."],
            )
            site_crawl.cannibalization_intelligence = error_intel
            return error_intel
