"""
Search Signal Intelligence Engine — Deterministic, evidence-driven extraction,
structural location mapping, and normalization of search-relevant terms and concepts (Layer A).
Operates strictly in-memory on already-crawled HTML and evidence without external APIs or LLMs.
"""
from __future__ import annotations
import re
import json
from typing import List, Optional, Tuple, Set, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag

from rankintel.models.schema import (
    SearchSignalEvidence,
    SearchSignalItem,
    SearchSignalOccurrence,
    SearchSignalLocation,
    SearchSignalStatementType,
    SearchSignalConfidence,
    OnPageEvidence,
    ContentEvidence,
    EntityEvidence,
    ImageSEOEvidence,
)
from rankintel.engines.content_engine import ContentEngine, STOPWORDS


PUNCTUATION_STRIP_REGEX = re.compile(r"^[^\w]+|[^\w]+$")
WHITESPACE_COLLAPSE_REGEX = re.compile(r"\s+")
SPLIT_DELIMITERS_REGEX = re.compile(r"[\s\|\-–—•,:;/\\()\[\]{}]+")

# Common uninformative boilerplate alt/title phrases to disregard
GENERIC_IGNORE_TERMS: Set[str] = {
    "image", "img", "icon", "logo", "banner", "picture", "photo", "graphic",
    "home", "homepage", "welcome", "read more", "learn more", "click here",
    "view all", "contact us", "privacy policy", "terms of service", "menu",
    "navigation", "close", "open", "search", "submit", "button"
}


def normalize_term(term: str) -> str:
    """
    Safely and deterministically normalizes a term or phrase:
    - Lowercases text
    - Collapses internal whitespace
    - Strips edge punctuation
    - Replaces underscores with spaces
    - Avoids aggressive stemming or singularization to protect technical and brand terms.
    """
    if not term:
        return ""
    t = term.lower().strip()
    t = t.replace("_", " ")
    t = PUNCTUATION_STRIP_REGEX.sub("", t)
    t = WHITESPACE_COLLAPSE_REGEX.sub(" ", t).strip()
    return t


class SearchSignalEngine:
    """
    Dedicated Search Signal Intelligence Engine (Layer A).
    Extracts strictly evidenced, deterministic search signals from on-site content,
    structural tags, named entities, and metadata.
    """

    @classmethod
    def evaluate(
        cls,
        raw_html: Optional[str],
        url: str = "",
        on_page: Optional[OnPageEvidence] = None,
        content_ev: Optional[ContentEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
        image_seo_ev: Optional[ImageSEOEvidence] = None,
    ) -> SearchSignalEvidence:
        """
        Extract and synthesize search-relevant signals from available page evidence.
        """
        if not raw_html or not raw_html.strip():
            return SearchSignalEvidence(
                url=url,
                engine_source="search_signal_engine",
                status="skipped",
                facts=["No HTML content provided for search signal extraction."],
                analyses=["Page search signal analysis unavailable due to missing HTML body."],
            )

        soup = BeautifulSoup(raw_html, "html.parser")

        # In-memory accumulators
        term_map: Dict[str, Dict[str, Any]] = {}
        title_terms_list: List[str] = []
        meta_desc_terms_list: List[str] = []
        heading_terms_list: List[str] = []
        url_path_terms_list: List[str] = []
        image_alt_terms_list: List[str] = []
        structured_data_terms_list: List[str] = []
        entity_terms_list: List[Dict[str, Any]] = []
        main_content_top_terms_list: List[Dict[str, Any]] = []

        # Helper to register an observed signal
        def register_signal(
            raw_t: str,
            loc: SearchSignalLocation,
            category: str,
            raw_snippet: str = "",
            is_entity: bool = False,
            entity_type: Optional[str] = None,
        ):
            norm = normalize_term(raw_t)
            if not norm or len(norm) < 2:
                return
            if norm in STOPWORDS or norm in GENERIC_IGNORE_TERMS:
                return

            if norm not in term_map:
                term_map[norm] = {
                    "term": norm,
                    "raw_term": raw_t.strip(),
                    "category": category,
                    "locations": set(),
                    "occurrences": [],
                    "total_occurrences": 0,
                    "prominence_locations": set(),
                    "is_entity": is_entity,
                    "entity_type": entity_type,
                }
            entry = term_map[norm]
            entry["locations"].add(loc)
            entry["total_occurrences"] += 1
            if loc in (SearchSignalLocation.TITLE, SearchSignalLocation.H1, SearchSignalLocation.META_DESCRIPTION):
                entry["prominence_locations"].add(loc.value.lower())
            if is_entity and not entry["is_entity"]:
                entry["is_entity"] = True
                entry["entity_type"] = entity_type

            # Bounded occurrence recording (up to 5 occurrences per term)
            if len(entry["occurrences"]) < 5:
                entry["occurrences"].append(
                    SearchSignalOccurrence(
                        location=loc,
                        raw_text=raw_snippet[:150].strip() if raw_snippet else raw_t.strip(),
                        count=1,
                        attribute_or_tag=loc.value.lower(),
                    )
                )

        # ----------------------------------------------------------------------
        # 1. Title Terms
        # ----------------------------------------------------------------------
        title_val = ""
        if on_page and on_page.title:
            title_val = on_page.title
        else:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title_val = title_tag.string.strip()

        if title_val:
            # Segment title by delimiters (e.g., "Acme Solutions | Industrial Testing")
            segments = [s.strip() for s in re.split(r"[|–—•\-:]", title_val) if s.strip()]
            for seg in segments:
                norm_seg = normalize_term(seg)
                if norm_seg and norm_seg not in STOPWORDS and len(norm_seg.split()) <= 5:
                    register_signal(seg, SearchSignalLocation.TITLE, "title_term", raw_snippet=title_val)
                    if norm_seg not in title_terms_list:
                        title_terms_list.append(norm_seg)

            # Also record individual significant words from title
            tokens = [t for t in SPLIT_DELIMITERS_REGEX.split(title_val) if t]
            for tok in tokens:
                norm_tok = normalize_term(tok)
                if norm_tok and len(norm_tok) >= 3 and norm_tok not in STOPWORDS:
                    register_signal(tok, SearchSignalLocation.TITLE, "title_term", raw_snippet=title_val)
                    if norm_tok not in title_terms_list:
                        title_terms_list.append(norm_tok)

        # ----------------------------------------------------------------------
        # 2. Meta Description Terms
        # ----------------------------------------------------------------------
        desc_val = ""
        if on_page and on_page.meta_description:
            desc_val = on_page.meta_description
        else:
            meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            if meta_tag and meta_tag.get("content"):
                desc_val = meta_tag["content"].strip()

        if desc_val:
            # Extract key phrases/tokens from meta description
            desc_tokens = [t for t in SPLIT_DELIMITERS_REGEX.split(desc_val) if t]
            for tok in desc_tokens:
                norm_tok = normalize_term(tok)
                if norm_tok and len(norm_tok) >= 3 and norm_tok not in STOPWORDS:
                    register_signal(tok, SearchSignalLocation.META_DESCRIPTION, "meta_description_term", raw_snippet=desc_val)
                    if norm_tok not in meta_desc_terms_list:
                        meta_desc_terms_list.append(norm_tok)

        # ----------------------------------------------------------------------
        # 3. Headings Terms (H1, H2, H3)
        # ----------------------------------------------------------------------
        for level, tag_name, loc_enum in [
            (1, "h1", SearchSignalLocation.H1),
            (2, "h2", SearchSignalLocation.H2),
            (3, "h3", SearchSignalLocation.H3),
        ]:
            headings = soup.find_all(tag_name)
            for h in headings:
                h_text = h.get_text(separator=" ", strip=True)
                if not h_text:
                    continue
                # Register full heading phrase if concise
                norm_h = normalize_term(h_text)
                if norm_h and norm_h not in STOPWORDS and len(norm_h.split()) <= 6:
                    register_signal(h_text, loc_enum, f"heading_{tag_name}_term", raw_snippet=h_text)
                    if norm_h not in heading_terms_list:
                        heading_terms_list.append(norm_h)

                # Individual significant tokens
                for tok in SPLIT_DELIMITERS_REGEX.split(h_text):
                    norm_tok = normalize_term(tok)
                    if norm_tok and len(norm_tok) >= 3 and norm_tok not in STOPWORDS:
                        register_signal(tok, loc_enum, f"heading_{tag_name}_term", raw_snippet=h_text)
                        if norm_tok not in heading_terms_list:
                            heading_terms_list.append(norm_tok)

        # ----------------------------------------------------------------------
        # 4. Main Editorial Content Terms (Strictly Scoped)
        # ----------------------------------------------------------------------
        # Content terms are extracted strictly from the main editorial content established
        # by ContentEngine (M8.1), preventing boilerplate/footer noise from leaking into signals.
        editorial_text = ""
        if content_ev and content_ev.main_content_text_preview:
            # We also extract full text from soup if available using ContentEngine's main content extractor
            editorial_text, _, _ = ContentEngine.extract_main_content(soup)
            if not editorial_text:
                editorial_text = content_ev.main_content_text_preview
        else:
            editorial_text, _, _ = ContentEngine.extract_main_content(soup)

        if editorial_text:
            content_words = [normalize_term(w) for w in SPLIT_DELIMITERS_REGEX.split(editorial_text) if w]
            content_words = [w for w in content_words if w and len(w) >= 3 and w not in STOPWORDS and w not in GENERIC_IGNORE_TERMS]

            # Word frequency counts
            word_freq: Dict[str, int] = {}
            for w in content_words:
                word_freq[w] = word_freq.get(w, 0) + 1

            # Two-word phrases
            phrase_freq: Dict[str, int] = {}
            raw_tokens = editorial_text.split()
            for i in range(len(raw_tokens) - 1):
                w1 = normalize_term(raw_tokens[i])
                w2 = normalize_term(raw_tokens[i + 1])
                if w1 and w2 and w1 not in STOPWORDS and w2 not in STOPWORDS:
                    phrase = f"{w1} {w2}"
                    phrase_freq[phrase] = phrase_freq.get(phrase, 0) + 1

            # Register repeated words (frequency >= 2)
            sorted_words = sorted(word_freq.items(), key=lambda kv: kv[1], reverse=True)
            for w, count in sorted_words[:30]:
                if count >= 2:
                    register_signal(w, SearchSignalLocation.MAIN_CONTENT, "main_content_term", raw_snippet=f"Appears {count} times in main content")
                    # Increment total occurrences if already registered
                    if w in term_map:
                        term_map[w]["total_occurrences"] += (count - 1)
                    main_content_top_terms_list.append({"term": w, "frequency": count})

            # Register repeated 2-word phrases (frequency >= 2)
            sorted_phrases = sorted(phrase_freq.items(), key=lambda kv: kv[1], reverse=True)
            for p, count in sorted_phrases[:15]:
                if count >= 2:
                    register_signal(p, SearchSignalLocation.MAIN_CONTENT, "main_content_phrase", raw_snippet=f"Phrase appears {count} times in main content")
                    if p in term_map:
                        term_map[p]["total_occurrences"] += (count - 1)
                    main_content_top_terms_list.append({"term": p, "frequency": count})

        # ----------------------------------------------------------------------
        # 5. Entity Reuse & JSON-LD Structured Data Terms
        # ----------------------------------------------------------------------
        # Reuse pre-extracted entities from EntityEvidence if provided
        if entity_ev and entity_ev.detected_entities:
            for ent in entity_ev.detected_entities:
                ent_name = ent.name.strip()
                ent_type_str = ent.entity_type.value if hasattr(ent.entity_type, "value") else str(ent.entity_type)
                register_signal(
                    ent_name,
                    SearchSignalLocation.ENTITY,
                    f"entity_{ent_type_str.lower()}",
                    raw_snippet=f"Entity ({ent_type_str}): {ent_name}",
                    is_entity=True,
                    entity_type=ent_type_str,
                )
                entity_terms_list.append({
                    "entity_name": ent_name,
                    "entity_type": ent_type_str,
                    "confidence": "high",
                })
        else:
            # Parse structured data JSON-LD directly for entities and schema terms
            for script in soup.find_all("script", type="application/ld+json"):
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        name = it.get("name")
                        stype = it.get("@type", "Schema")
                        if name and isinstance(name, str):
                            register_signal(
                                name,
                                SearchSignalLocation.STRUCTURED_DATA,
                                "structured_data_entity",
                                raw_snippet=f"Schema @type: {stype}",
                                is_entity=True,
                                entity_type=stype,
                            )
                            structured_data_terms_list.append(normalize_term(name))
                        desc = it.get("description")
                        if desc and isinstance(desc, str):
                            for tok in SPLIT_DELIMITERS_REGEX.split(desc):
                                norm_tok = normalize_term(tok)
                                if norm_tok and len(norm_tok) >= 3 and norm_tok not in STOPWORDS:
                                    register_signal(tok, SearchSignalLocation.STRUCTURED_DATA, "structured_data_term", raw_snippet=desc[:100])
                                    structured_data_terms_list.append(norm_tok)
                except Exception:
                    pass

        # ----------------------------------------------------------------------
        # 6. URL Path Terms
        # ----------------------------------------------------------------------
        if url:
            path = urlparse(url).path
            clean_path = re.sub(r"\.[a-zA-Z0-9]+$", "", path)  # strip extension
            segments = [s for s in clean_path.split("/") if s]
            for seg in segments:
                # Segment may contain hyphens: e.g. "industrial-testing-equipment"
                tokens = [t for t in re.split(r"[-_]", seg) if t]
                for tok in tokens:
                    norm_tok = normalize_term(tok)
                    if norm_tok and len(norm_tok) >= 3 and norm_tok not in STOPWORDS and not norm_tok.isdigit():
                        register_signal(tok, SearchSignalLocation.URL_PATH, "url_path_term", raw_snippet=path)
                        if norm_tok not in url_path_terms_list:
                            url_path_terms_list.append(norm_tok)

        # ----------------------------------------------------------------------
        # 7. Image Alt Text Terms
        # ----------------------------------------------------------------------
        if image_seo_ev and image_seo_ev.images:
            for img in image_seo_ev.images:
                if img.alt_text and img.alt_text.strip():
                    alt = img.alt_text.strip()
                    norm_alt = normalize_term(alt)
                    if norm_alt and norm_alt not in GENERIC_IGNORE_TERMS and norm_alt not in STOPWORDS:
                        register_signal(alt, SearchSignalLocation.IMAGE_ALT, "image_alt_term", raw_snippet=alt)
                        if norm_alt not in image_alt_terms_list:
                            image_alt_terms_list.append(norm_alt)
        else:
            for img in soup.find_all("img"):
                alt = img.get("alt")
                if alt and alt.strip():
                    norm_alt = normalize_term(alt)
                    if norm_alt and norm_alt not in GENERIC_IGNORE_TERMS and norm_alt not in STOPWORDS:
                        register_signal(alt, SearchSignalLocation.IMAGE_ALT, "image_alt_term", raw_snippet=alt.strip())
                        if norm_alt not in image_alt_terms_list:
                            image_alt_terms_list.append(norm_alt)

        # ----------------------------------------------------------------------
        # 8. Compile Signal Items & Assign Typed Confidence
        # ----------------------------------------------------------------------
        signals: List[SearchSignalItem] = []
        for norm_term, data in term_map.items():
            locs = list(data["locations"])
            prominence = list(data["prominence_locations"])
            total_occ = data["total_occurrences"]
            is_ent = data["is_entity"]

            # Typed confidence determination:
            # DIRECT: observed directly in primary structural elements (Title, H1, Meta, Schema, Entity)
            # SUPPORTED: observed in multiple structural locations or repeated within main editorial content
            # WEAK: isolated peripheral mention (e.g. single occurrence in URL or alt text only)
            if (
                SearchSignalLocation.TITLE in locs
                or SearchSignalLocation.H1 in locs
                or SearchSignalLocation.META_DESCRIPTION in locs
                or is_ent
            ):
                conf = SearchSignalConfidence.DIRECT
            elif len(locs) >= 2 or total_occ >= 3:
                conf = SearchSignalConfidence.SUPPORTED
            else:
                conf = SearchSignalConfidence.WEAK

            signals.append(
                SearchSignalItem(
                    term=norm_term,
                    raw_term=data["raw_term"],
                    signal_type=SearchSignalStatementType.FACT,
                    category=data["category"],
                    locations=locs,
                    occurrences=data["occurrences"],
                    total_occurrences=total_occ,
                    prominence_locations=prominence,
                    is_entity=is_ent,
                    entity_type=data["entity_type"],
                    confidence=conf,
                    provenance="search_signal_engine",
                )
            )

        # Sort signals by prominence and total occurrences
        signals.sort(key=lambda s: (len(s.prominence_locations) > 0, s.confidence == SearchSignalConfidence.DIRECT, s.total_occurrences), reverse=True)

        # ----------------------------------------------------------------------
        # 9. Formulate Strict FACT & ANALYSIS Statements
        # ----------------------------------------------------------------------
        facts: List[str] = [
            f"Observed {len(signals)} search-relevant signal terms across on-site structural elements.",
        ]
        if title_terms_list:
            facts.append(f"Title tag evidences terms: {', '.join(title_terms_list[:6])}.")
        if heading_terms_list:
            facts.append(f"Heading tags (H1-H3) evidence terms: {', '.join(heading_terms_list[:6])}.")
        if entity_terms_list:
            facts.append(f"Detected {len(entity_terms_list)} entity signals ({', '.join([e['entity_name'] for e in entity_terms_list[:3]])}).")

        analyses: List[str] = []
        prominent_terms = [s.term for s in signals if len(s.locations) >= 2 and s.confidence == SearchSignalConfidence.DIRECT]
        if prominent_terms:
            analyses.append(f"Multi-location co-occurrence observed for key terms: {', '.join(prominent_terms[:5])}.")

        # Check Title vs H1 alignment for search signals
        title_set = set(title_terms_list)
        h1_signals = [s.term for s in signals if SearchSignalLocation.H1 in s.locations]
        h1_set = set(h1_signals)
        overlap = title_set & h1_set
        if overlap:
            analyses.append(f"Title and H1 share {len(overlap)} core evidenced terms: {', '.join(list(overlap)[:4])}.")
        elif title_set and h1_set:
            analyses.append("Title and H1 do not share any directly evidenced lexical terms.")

        return SearchSignalEvidence(
            url=url,
            engine_source="search_signal_engine",
            status="success",
            total_signals_detected=len(signals),
            unique_terms_count=len(signals),
            signals=signals,
            title_terms=title_terms_list,
            meta_description_terms=meta_desc_terms_list,
            heading_terms=heading_terms_list,
            main_content_top_terms=main_content_top_terms_list[:20],
            entity_terms=entity_terms_list,
            url_path_terms=url_path_terms_list,
            image_alt_terms=image_alt_terms_list,
            structured_data_terms=list(set(structured_data_terms_list)),
            facts=facts,
            analyses=analyses,
        )
