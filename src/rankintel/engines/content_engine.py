"""
Content Intelligence Engine — Evaluates editorial body content, heading structure,
Title/H1 alignment, and duplicate fingerprints without redundant network fetches or LLMs.
"""
from __future__ import annotations
import re
import hashlib
from typing import List, Optional, Tuple, Set, Dict, Any
from bs4 import BeautifulSoup, Tag

from rankintel.models.schema import (
    ContentEvidence,
    ThinContentEvidence,
    TitleH1RelationshipEvidence,
    HeadingStructureEvidence,
    HeadingSectionDetail,
    ContentExtractionMethod,
    WordCountTier,
    TitleH1AlignmentStatus,
)

# Common stopwords for keyword overlap and lead content checks
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with",
    "would", "you", "your", "yours", "yourself", "yourselves"
}

BOILERPLATE_TAGS: Set[str] = {
    "script", "style", "nav", "footer", "header", "aside", "noscript",
    "svg", "canvas", "form", "dialog", "iframe"
}

BOILERPLATE_CLASS_OR_ID_PATTERN = re.compile(
    r"\b(sidebar|menu|footer|header|cookie|popup|modal|banner|nav|navigation|toolbar|widget-area)\b",
    re.IGNORECASE
)

PLACEHOLDER_PATTERN = re.compile(
    r"\b(lorem ipsum|under construction|coming soon|page intentionally left blank|"
    r"insert text here|sample text|dummy text|template placeholder)\b",
    re.IGNORECASE
)


class ContentEngine:
    """
    Focused, evidence-driven Content Intelligence Engine.
    Operates strictly on provided DOM / raw HTML without initiating network calls.
    """

    @classmethod
    def evaluate(
        cls,
        raw_html: Optional[str],
        url: str = "",
        title: Optional[str] = None,
        h1_list: Optional[List[str]] = None,
    ) -> ContentEvidence:
        """
        Evaluate page content for extraction, density, fingerprints, alignment, and heading structure.
        """
        if not raw_html or not raw_html.strip():
            thin_ev = ThinContentEvidence(
                word_count_tier=WordCountTier.UNAVAILABLE,
                is_empty_or_whitespace=True,
                facts=["Page has no HTML body to inspect."],
                recommendations=["Inspect page rendering: editorial content area contains 0 extracted words."]
            )
            return ContentEvidence(
                url=url,
                extraction_method=ContentExtractionMethod.UNAVAILABLE,
                thin_content=thin_ev,
                facts=["No HTML content was provided or response body was empty."],
                heading_structure=HeadingStructureEvidence(anomalies=["No headings found (empty document)."]),
                title_h1_relationship=TitleH1RelationshipEvidence(notes=["Title and H1 relationship unavailable due to empty HTML."]),
            )

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Main Content Text Extraction & Content/Word Counts
        main_text, method, raw_body_words = cls.extract_main_content(soup)
        words = main_text.split()
        word_count = len(words)
        char_count = len(main_text)
        preview = main_text[:250].strip()

        # Paragraph count & sentence count inside main content
        p_tags = soup.find_all("p")
        paragraph_count = len([p for p in p_tags if p.get_text(strip=True)])
        sentence_count = len(re.findall(r"[.!?]+(?:\s+|$)", main_text))

        boilerplate_ratio = round(
            word_count / max(1, raw_body_words), 3
        ) if raw_body_words > 0 else 1.0

        # Exact and Near-Duplicate Fingerprints
        exact_content_hash = cls.compute_exact_hash(main_text)
        html_hash = cls.compute_html_hash(raw_html)
        simhash_str = cls.compute_simhash(main_text)

        # 2. Thin/Low-Content Indicators
        thin_evidence = cls.evaluate_thin_content(
            word_count=word_count,
            raw_body_words=raw_body_words,
            boilerplate_ratio=boilerplate_ratio,
            paragraph_count=paragraph_count,
            main_text=main_text
        )

        # 3. Title ↔ H1 ↔ Main-Content Relationship Signals
        extracted_title = title or cls._extract_title(soup)
        extracted_h1s = h1_list if h1_list is not None else cls._extract_h1s(soup)
        alignment_evidence = cls.evaluate_title_h1_relationship(
            title=extracted_title,
            h1s=extracted_h1s,
            main_text=main_text,
            lead_words=words[:200]
        )

        # 4. Heading & Content Structure Signals
        heading_evidence = cls.evaluate_heading_structure(soup)

        facts = [
            f"Extraction method: {method.value} yielded {word_count} main content words ({raw_body_words} total body words).",
            f"Content-to-body ratio: {boilerplate_ratio * 100:.1f}%.",
            f"Exact main-content SHA-256: {exact_content_hash[:16]}..., Full HTML SHA-256: {html_hash[:16]}...",
            f"SimHash fingerprint: {simhash_str}."
        ]

        return ContentEvidence(
            url=url,
            engine_source="content_engine",
            extraction_method=method,
            main_content_text_preview=preview,
            main_content_word_count=word_count,
            main_content_char_count=char_count,
            total_body_word_count=raw_body_words,
            content_to_boilerplate_ratio=boilerplate_ratio,
            paragraph_count=paragraph_count,
            sentence_count=sentence_count,
            exact_content_hash=exact_content_hash,
            html_hash=html_hash,
            simhash=simhash_str,
            thin_content=thin_evidence,
            title_h1_relationship=alignment_evidence,
            heading_structure=heading_evidence,
            facts=facts,
        )

    # -------------------------------------------------------------------------
    # 1. Main / Content Text Extraction
    # -------------------------------------------------------------------------
    @classmethod
    def extract_main_content(cls, soup: BeautifulSoup) -> Tuple[str, ContentExtractionMethod, int]:
        """
        Extract main editorial text from HTML using semantic tags with heuristic pruning fallback.
        Returns: (main_text, extraction_method, total_body_word_count)
        """
        body = soup.find("body") or soup

        # Calculate total body words (with scripts/styles stripped)
        body_clone = BeautifulSoup(str(body), "html.parser")
        for tag in body_clone(["script", "style", "noscript"]):
            tag.extract()
        raw_body_text = body_clone.get_text(separator=" ", strip=True)
        total_body_words = len(raw_body_text.split())

        # Strategy A: Check semantic <main> tag
        main_elem = soup.find("main")
        if main_elem and isinstance(main_elem, Tag):
            extracted = cls._extract_clean_text_from_node(main_elem)
            if len(extracted.split()) >= 15:
                return extracted, ContentExtractionMethod.SEMANTIC_MAIN, total_body_words

        # Strategy B: Check role="main"
        role_main = soup.find(attrs={"role": "main"})
        if role_main and isinstance(role_main, Tag):
            extracted = cls._extract_clean_text_from_node(role_main)
            if len(extracted.split()) >= 15:
                return extracted, ContentExtractionMethod.ROLE_MAIN, total_body_words

        # Strategy C: Check semantic <article> tags
        articles = soup.find_all("article")
        if articles:
            article_texts = [cls._extract_clean_text_from_node(a) for a in articles]
            combined = " ".join([t for t in article_texts if t])
            if len(combined.split()) >= 15:
                return combined, ContentExtractionMethod.SEMANTIC_ARTICLE, total_body_words

        # Strategy D: Heuristic Body Pruning
        pruned_body = BeautifulSoup(str(body), "html.parser")
        # Strip boilerplate tags
        for t_name in BOILERPLATE_TAGS:
            for node in pruned_body.find_all(t_name):
                node.extract()

        # Strip elements matching boilerplate class/id or aria-hidden
        for elem in list(pruned_body.find_all(True)):
            if elem.get("aria-hidden") == "true":
                elem.extract()
                continue
            class_str = " ".join(elem.get("class", [])) if isinstance(elem.get("class"), list) else str(elem.get("class", ""))
            id_str = str(elem.get("id", ""))
            role_str = str(elem.get("role", "")).lower()

            if role_str in ("navigation", "banner", "contentinfo", "complementary"):
                elem.extract()
                continue

            if (class_str and BOILERPLATE_CLASS_OR_ID_PATTERN.search(class_str)) or \
               (id_str and BOILERPLATE_CLASS_OR_ID_PATTERN.search(id_str)):
                elem.extract()

        pruned_text = pruned_body.get_text(separator=" ", strip=True)
        cleaned_pruned = re.sub(r"\s+", " ", pruned_text).strip()
        if len(cleaned_pruned.split()) > 0:
            return cleaned_pruned, ContentExtractionMethod.HEURISTIC_PRUNED_BODY, total_body_words

        # Strategy E: Fallback to Raw Cleaned Body Text
        cleaned_raw = re.sub(r"\s+", " ", raw_body_text).strip()
        return cleaned_raw, ContentExtractionMethod.RAW_BODY_FALLBACK, total_body_words

    @classmethod
    def _extract_clean_text_from_node(cls, node: Tag) -> str:
        clone = BeautifulSoup(str(node), "html.parser")
        for t_name in BOILERPLATE_TAGS:
            for t in clone.find_all(t_name):
                t.extract()
        text = clone.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()

    # -------------------------------------------------------------------------
    # 2. Thin / Low-Content Factual Indicators
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_thin_content(
        cls,
        word_count: int,
        raw_body_words: int,
        boilerplate_ratio: float,
        paragraph_count: int,
        main_text: str
    ) -> ThinContentEvidence:
        """
        Factual telemetry regarding main content density and placeholder copy.
        Follows descriptive measurement buckets, avoiding arbitrary SEO grades.
        """
        # Determine descriptive telemetry bucket
        if word_count == 0:
            tier = WordCountTier.EMPTY
        elif word_count < 100:
            tier = WordCountTier.VERY_LOW
        elif word_count < 200:
            tier = WordCountTier.LOW  # Screaming Frog default low-content filter is <200
        elif word_count < 600:
            tier = WordCountTier.MODERATE
        else:
            tier = WordCountTier.SUBSTANTIVE

        is_empty = (word_count == 0)
        has_substantive = (word_count >= 300 and paragraph_count >= 2)
        boilerplate_dominated = (boilerplate_ratio < 0.20 and raw_body_words > 100)

        # Check placeholder patterns
        placeholder_snippets: List[str] = []
        for match in PLACEHOLDER_PATTERN.finditer(main_text):
            snippet = match.group(0)
            if snippet not in placeholder_snippets:
                placeholder_snippets.append(snippet)
        placeholder_detected = bool(placeholder_snippets)

        facts = [
            f"Main content contains {word_count} words across {paragraph_count} paragraphs.",
            f"Measurement bucket: {tier.value} (descriptive telemetry range, not a quality score).",
        ]
        if boilerplate_dominated:
            facts.append(f"Boilerplate accounts for {round((1.0 - boilerplate_ratio) * 100, 1)}% of total page body text.")
        if placeholder_detected:
            facts.append(f"Detected placeholder text patterns: {', '.join(placeholder_snippets)}.")

        recommendations: List[str] = []
        if is_empty:
            recommendations.append("Inspect page rendering: editorial content area contains 0 extracted words.")
        elif tier in (WordCountTier.VERY_LOW, WordCountTier.LOW):
            recommendations.append("Review whether page is intended as a navigation index, stub, or full content resource.")
        if placeholder_detected:
            recommendations.append("Remove template placeholder/dummy copy prior to indexing.")

        return ThinContentEvidence(
            word_count_tier=tier,
            has_substantive_content=has_substantive,
            is_empty_or_whitespace=is_empty,
            placeholder_text_detected=placeholder_detected,
            placeholder_snippets=placeholder_snippets,
            boilerplate_dominated=boilerplate_dominated,
            facts=facts,
            recommendations=recommendations,
        )

    # -------------------------------------------------------------------------
    # 3. Exact Duplicate & HTML Fingerprints
    # -------------------------------------------------------------------------
    @classmethod
    def compute_exact_hash(cls, text: str) -> str:
        """
        Computes SHA-256 of normalized main-content text.
        Explicitly used for exact duplicate main-content detection across pages.
        """
        normalized = cls.normalize_text_for_hashing(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def compute_html_hash(cls, raw_html: str) -> str:
        """
        Computes SHA-256 of normalized full-page HTML.
        Used to identify exact full-page duplicates (analogous to Screaming Frog HTML hash).
        """
        normalized = re.sub(r"\s+", " ", raw_html.strip().lower())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def normalize_text_for_hashing(cls, text: str) -> str:
        """Strip punctuation and collapse whitespace for robust duplicate hashing."""
        text_lower = text.lower()
        cleaned = re.sub(r"[^\w\s]", "", text_lower)
        return re.sub(r"\s+", " ", cleaned).strip()

    # -------------------------------------------------------------------------
    # 4. Near-Duplicate Detection (SimHash & Shingle Jaccard)
    # -------------------------------------------------------------------------
    @classmethod
    def compute_simhash(cls, text: str) -> str:
        """
        Computes a deterministic 64-bit Charikar SimHash fingerprint represented as a 16-character hex string.
        Uses 3-gram word shingles and standard MD5 token hashing.
        """
        words = [w for w in re.sub(r"[^\w\s]", "", text.lower()).split() if w]
        if not words:
            return "0000000000000000"

        # Generate 3-word shingles (or 1-word if fewer than 3 words)
        if len(words) >= 3:
            shingles = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]
        else:
            shingles = words

        # 64-dimensional bit accumulator
        v = [0] * 64
        for shingle in shingles:
            # 64-bit integer hash from MD5 digest
            h = int(hashlib.md5(shingle.encode("utf-8")).hexdigest()[:16], 16)
            for i in range(64):
                bit = (h >> i) & 1
                if bit == 1:
                    v[i] += 1
                else:
                    v[i] -= 1

        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= (1 << i)

        return f"{fingerprint:016x}"

    @classmethod
    def calculate_simhash_hamming(cls, hash_a: str, hash_b: str) -> int:
        """Computes bitwise Hamming distance between two 16-char hex SimHash strings."""
        try:
            val_a = int(hash_a, 16)
            val_b = int(hash_b, 16)
            xor_val = val_a ^ val_b
            return bin(xor_val).count("1")
        except Exception:
            return 64

    @classmethod
    def calculate_shingle_jaccard(cls, text_a: str, text_b: str, k: int = 3) -> float:
        """
        Computes exact Jaccard similarity across k-gram word sets.
        Returns a float between 0.0 and 1.0.
        """
        words_a = [w for w in re.sub(r"[^\w\s]", "", text_a.lower()).split() if w]
        words_b = [w for w in re.sub(r"[^\w\s]", "", text_b.lower()).split() if w]

        if not words_a or not words_b:
            return 0.0

        if len(words_a) < k or len(words_b) < k:
            set_a = set(words_a)
            set_b = set(words_b)
        else:
            set_a = set(tuple(words_a[i:i+k]) for i in range(len(words_a) - k + 1))
            set_b = set(tuple(words_b[i:i+k]) for i in range(len(words_b) - k + 1))

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return round(intersection / union, 4) if union > 0 else 0.0

    # -------------------------------------------------------------------------
    # 5. Title ↔ H1 ↔ Main-Content Relationship Signals
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_title_h1_relationship(
        cls,
        title: Optional[str],
        h1s: List[str],
        main_text: str,
        lead_words: List[str]
    ) -> TitleH1RelationshipEvidence:
        """
        FACT -> Analysis -> Recommendation.
        Observes Title, primary H1, and content keywords without automatic punitive actions.
        """
        clean_title = title.strip() if title else None
        primary_h1 = h1s[0].strip() if h1s and h1s[0] else None

        if not clean_title or not primary_h1:
            notes = []
            if not clean_title:
                notes.append("Page title tag is missing or empty.")
            if not primary_h1:
                notes.append("Primary H1 heading is missing or empty.")
            return TitleH1RelationshipEvidence(
                title_text=clean_title,
                h1_text=primary_h1,
                alignment_status=TitleH1AlignmentStatus.UNAVAILABLE,
                notes=notes
            )

        norm_title = re.sub(r"[^\w\s]", "", clean_title.lower())
        norm_h1 = re.sub(r"[^\w\s]", "", primary_h1.lower())

        exact_match = (norm_title == norm_h1)
        title_in_h1 = (norm_title in norm_h1 and len(norm_title) > 3)
        h1_in_title = (norm_h1 in norm_title and len(norm_h1) > 3)

        title_tokens = set(w for w in norm_title.split() if w and w not in STOPWORDS)
        h1_tokens = set(w for w in norm_h1.split() if w and w not in STOPWORDS)

        if not title_tokens or not h1_tokens:
            overlap_ratio = 1.0 if exact_match else 0.0
        else:
            overlap_ratio = round(len(title_tokens & h1_tokens) / len(title_tokens | h1_tokens), 3)

        # Keyword presence in lead 200 words and full content
        lead_token_set = set(w.lower() for w in lead_words if w.lower() not in STOPWORDS)
        full_token_set = set(w.lower() for w in re.sub(r"[^\w\s]", "", main_text).split() if w.lower() not in STOPWORDS)

        combined_key_tokens = title_tokens | h1_tokens
        if combined_key_tokens:
            lead_present = len(combined_key_tokens & lead_token_set)
            full_present = len(combined_key_tokens & full_token_set)
            lead_ratio = round(lead_present / len(combined_key_tokens), 3)
            full_ratio = round(full_present / len(combined_key_tokens), 3)
        else:
            lead_ratio = 0.0
            full_ratio = 0.0

        # Alignment status determination
        if exact_match or overlap_ratio >= 0.60 or (title_in_h1 and overlap_ratio >= 0.40) or (h1_in_title and overlap_ratio >= 0.40):
            alignment_status = TitleH1AlignmentStatus.STRONG_ALIGNMENT
        elif overlap_ratio >= 0.25 or (lead_ratio >= 0.50):
            alignment_status = TitleH1AlignmentStatus.MODERATE_ALIGNMENT
        elif overlap_ratio > 0.0 or full_ratio >= 0.30:
            alignment_status = TitleH1AlignmentStatus.WEAK_ALIGNMENT
        else:
            alignment_status = TitleH1AlignmentStatus.MISALIGNED

        notes = [
            f"Title: '{clean_title}', H1: '{primary_h1}'.",
            f"Token overlap: {overlap_ratio * 100:.1f}%.",
            f"Title/H1 key terms in lead content: {lead_ratio * 100:.1f}%, full content: {full_ratio * 100:.1f}%.",
            f"Alignment observation: {alignment_status.value}."
        ]

        return TitleH1RelationshipEvidence(
            title_text=clean_title,
            h1_text=primary_h1,
            title_h1_exact_match=exact_match,
            title_in_h1=title_in_h1,
            h1_in_title=h1_in_title,
            token_overlap_ratio=overlap_ratio,
            lead_content_keyword_ratio=lead_ratio,
            full_content_keyword_ratio=full_ratio,
            alignment_status=alignment_status,
            notes=notes,
        )

    # -------------------------------------------------------------------------
    # 6. Heading & Content Structure Signals
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_heading_structure(cls, soup: BeautifulSoup) -> HeadingStructureEvidence:
        """
        Observes heading hierarchy, sequence order, skips, and section distribution.
        """
        headings = soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))
        h_counts: Dict[str, int] = {f"h{i}": 0 for i in range(1, 7)}
        h1_texts: List[str] = []
        empty_headings: List[str] = []
        anomalies: List[str] = []

        heading_sequence: List[Tuple[int, str]] = []

        for h in headings:
            tag_name = h.name.lower()
            h_counts[tag_name] += 1
            level = int(tag_name[1])
            text = h.get_text(strip=True)

            if tag_name == "h1" and text:
                h1_texts.append(text)

            if not text:
                empty_headings.append(f"<{tag_name}> (empty text)")

            heading_sequence.append((level, text))

        # Check hierarchy skips
        skips: List[str] = []
        prev_level: Optional[int] = None
        for level, text in heading_sequence:
            if prev_level is not None:
                if level > prev_level + 1:
                    skip_desc = f"Heading skip: <h{prev_level}> to <h{level}> ('{text[:30]}...')"
                    skips.append(skip_desc)
            prev_level = level

        hierarchy_valid = (len(skips) == 0 and h_counts["h1"] > 0)

        # Multiple H1s detection
        multiple_h1 = (h_counts["h1"] > 1)
        if multiple_h1:
            anomalies.append(f"Multiple H1 headings detected ({h_counts['h1']} tags).")
        if h_counts["h1"] == 0:
            anomalies.append("No H1 heading detected on page.")
        if empty_headings:
            anomalies.append(f"Detected {len(empty_headings)} empty heading tags.")
        if skips:
            anomalies.extend(skips)

        # Section word count distribution
        sections, empty_sections_count = cls._measure_heading_sections(soup)
        avg_section_words = round(
            sum(s.word_count for s in sections) / len(sections), 1
        ) if sections else 0.0

        return HeadingStructureEvidence(
            total_headings=len(headings),
            h1_count=h_counts["h1"],
            h2_count=h_counts["h2"],
            h3_count=h_counts["h3"],
            h4_count=h_counts["h4"],
            h5_count=h_counts["h5"],
            h6_count=h_counts["h6"],
            heading_hierarchy_valid=hierarchy_valid,
            heading_skips=skips,
            multiple_h1_detected=multiple_h1,
            h1_texts=h1_texts,
            empty_headings_count=len(empty_headings),
            empty_headings=empty_headings,
            empty_sections_count=empty_sections_count,
            average_words_per_section=avg_section_words,
            sections=sections[:15],  # Retain top 15 sections for telemetry preservation
            anomalies=anomalies,
        )

    @classmethod
    def _measure_heading_sections(cls, soup: BeautifulSoup) -> Tuple[List[HeadingSectionDetail], int]:
        """
        Segments content by headings and measures words in each section.
        Detects empty sections (headings immediately followed by another heading with 0 body words).
        """
        body = soup.find("body") or soup
        headings = body.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))
        sections: List[HeadingSectionDetail] = []
        empty_sections = 0

        for h in headings:
            h_text = h.get_text(strip=True)
            words_in_sec = 0

            # Traverse siblings until next heading
            curr = h.next_sibling
            while curr:
                if isinstance(curr, Tag):
                    if re.match(r"^h[1-6]$", curr.name, re.IGNORECASE):
                        break
                    if curr.name not in BOILERPLATE_TAGS:
                        sec_text = curr.get_text(separator=" ", strip=True)
                        words_in_sec += len(sec_text.split())
                curr = curr.next_sibling

            if words_in_sec == 0:
                empty_sections += 1

            sections.append(HeadingSectionDetail(
                heading_tag=h.name.lower(),
                heading_text=h_text[:50],
                word_count=words_in_sec
            ))

        return sections, empty_sections

    # -------------------------------------------------------------------------
    # Helper extraction
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> Optional[str]:
        t_tag = soup.find("title")
        return t_tag.get_text(strip=True) if t_tag else None

    @classmethod
    def _extract_h1s(cls, soup: BeautifulSoup) -> List[str]:
        return [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
