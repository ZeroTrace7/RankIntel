"""
AI Answerability & Information Extraction Engine for RankIntel (Phase 10.2).

Evaluates whether important information on a crawled page is clearly structured,
understandable, and extractable for modern search engines and AI retrieval systems.

Strictly deterministic and evidence-driven. Zero external LLM/API queries.
Zero arbitrary AI/GEO scores or letter grades. Preserves existing health scores.
Incorporates 4 Phase 10.2 refinements:
1. Strict semantic verification for EXPLAINED topic classifications (no false positives).
2. Non-rigid heading support check (short answers are valid; UNSUPPORTED_HEADING requires genuine absence).
3. Conservative factual-statement extraction (extracts observable patterns without claiming truth verification).
4. Multi-type deduplication per underlying DOM passage (secondary_types on stable passage units).
"""
from __future__ import annotations
import re
import json
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag, NavigableString

from rankintel.models.schema import (
    AnswerableUnitType,
    ClarityStatus,
    TopicExplanationStatus,
    AnswerableInformationUnit,
    InformationClarityAssessment,
    TopicAnswerabilityLink,
    AnswerabilityEvidence,
    SiteAnswerabilityIntelligence,
    ContentEvidence,
    EntityEvidence,
    SearchSignalEvidence,
    PageTopicIntelligence,
    PageQueryEvidence,
    SchemaEvidence,
    RetrievalReadinessEvidence,
    CrawlRecord,
    SiteCrawlResult,
)


STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "is", "are", "was", "were",
    "be", "being", "have", "has", "had", "do", "does", "did", "our", "your",
    "their", "its", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "we", "us", "you", "they", "them",
}

BOILERPLATE_TAGS: Set[str] = {
    "script", "style", "nav", "footer", "header", "aside", "noscript",
    "svg", "canvas", "dialog", "iframe"
}

QUESTION_WORDS = ("what", "why", "how", "when", "where", "who", "which", "can", "does", "do", "is", "are", "will", "should")

SERVICE_KEYWORDS = (
    "service", "services", "solution", "solutions", "offering", "offerings",
    "capability", "capabilities", "testing service", "inspection service", "calibration service",
    "certification service", "consulting", "auditing", "advisory", "training"
)

REQUIREMENT_KEYWORDS = (
    "requirement", "requirements", "eligibility", "prerequisite", "prerequisites",
    "criteria", "documents required", "document required", "qualification", "qualifications", "mandatory"
)

COMPARISON_KEYWORDS = (
    "vs", "versus", "comparison", "difference between", "pros and cons",
    "advantages and disadvantages", "comparison between"
)

STANDARD_REGEX = re.compile(
    r"\b(?:ISO(?:\s*[/:]?\s*IEC)?\s*\d+(?:[-:]\d+)?(?::\d+)?|"
    r"IS\s*\d+(?::\d+)?|"
    r"IEC\s*\d+(?:[-:]\d+)?|"
    r"ASTM\s*[A-Z0-9]+|"
    r"BIS(?:\s+CRS|\s+ISI)?|"
    r"NABL|"
    r"ASME\s*[A-Z0-9]*|"
    r"CE\s*Mark(?:ing)?|"
    r"RoHS|WEEE|FCC|GMP|HACCP)\b",
    re.IGNORECASE
)

PERCENTAGE_STAT_REGEX = re.compile(r"\b\d+(?:\.\d+)?%\b")

EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")

DATE_POLICY_REGEX = re.compile(
    r"\b(?:effective\s+date|last\s+updated|published\s+on|valid\s+until|expiry\s+date|"
    r"privacy\s+policy|terms\s+of\s+service|terms\s+and\s+conditions|refund\s+policy)\b",
    re.IGNORECASE
)

COPULA_DEFINITION_REGEX = re.compile(
    r"^([A-Z][\w\s-]{1,50}?)\s+(?:is\s+(?:a|an|the)|are\s+(?:the)?|refers\s+to|is\s+defined\s+as|is\s+the\s+process\s+of)\s+([^.!?]+[.!?])",
    re.IGNORECASE
)


def clean_tokens(text: str) -> List[str]:
    """Tokenize text into lowercase content words excluding stopwords."""
    if not text:
        return []
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]


def bound_snippet(text: str, max_len: int = 350) -> str:
    """Safely truncate snippet text to prevent memory bloat."""
    if not text:
        return ""
    clean = " ".join(text.strip().split())
    if len(clean) <= max_len:
        return clean
    return clean[:max_len].rsplit(" ", 1)[0] + "..."


def get_dom_path(elem: Tag) -> str:
    """Generate a readable DOM selector path for an element."""
    path_parts = []
    curr = elem
    while curr and curr.name and curr.name != "[document]":
        part = curr.name
        elem_id = curr.get("id")
        if elem_id and isinstance(elem_id, str):
            part += f"#{elem_id}"
            path_parts.append(part)
            break
        classes = curr.get("class", [])
        if classes and isinstance(classes, list):
            part += f".{classes[0]}"
        path_parts.append(part)
        curr = curr.parent
    return " > ".join(reversed(path_parts[-4:])) if path_parts else "body"


def has_nosnippet_ancestor(elem: Tag) -> bool:
    """Check if the element or any ancestor has data-nosnippet attribute."""
    curr = elem
    while curr and curr.name:
        if curr.get("data-nosnippet") is not None or "data-nosnippet" in curr.attrs:
            return True
        curr = curr.parent
    return False


class AnswerabilityEngine:
    """
    Evaluates AI Answerability & Information Extraction on crawled pages.
    Deterministically identifies 14 observable information structures,
    evaluates clarity conditions, and links Phase 9 topics with explicit explanations.
    """

    @classmethod
    def evaluate_page(
        cls,
        url: str,
        raw_html: Optional[str] = None,
        rendered_html: Optional[str] = None,
        content_ev: Optional[ContentEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
        topic_ev: Optional[PageTopicIntelligence] = None,
        query_page_ev: Optional[PageQueryEvidence] = None,
        search_signal_ev: Optional[SearchSignalEvidence] = None,
        schema_ev: Optional[SchemaEvidence] = None,
        retrieval_readiness_ev: Optional[RetrievalReadinessEvidence] = None,
    ) -> AnswerabilityEvidence:
        """
        Evaluate a single page for answerable information units, structural clarity,
        and concept explanation linkage.
        """
        active_html = raw_html or rendered_html or ""
        if not active_html.strip():
            return AnswerabilityEvidence(
                url=url,
                engine_source="answerability_engine",
                total_units_detected=0,
                units_by_type={},
                units=[],
                clarity_assessment=InformationClarityAssessment(
                    heading_content_relationship=ClarityStatus.UNAVAILABLE,
                    heading_content_notes=["No HTML body available for answerability analysis."],
                    question_answer_patterns=ClarityStatus.UNAVAILABLE,
                    definition_patterns=ClarityStatus.UNAVAILABLE,
                    step_list_structure=ClarityStatus.UNAVAILABLE,
                    table_availability=ClarityStatus.UNAVAILABLE,
                ),
                topic_links=[],
                facts=["No HTML content was available for answerability evaluation."],
                analyses=["Answerability evaluation skipped due to missing HTML."],
            )

        soup = BeautifulSoup(active_html, "html.parser")
        source_label = "rendered_html" if rendered_html and not raw_html else "raw_html"

        # Unit registry keyed by stable passage fingerprint (Refinement 4: deduplication)
        passage_registry: Dict[str, AnswerableInformationUnit] = {}

        # 1. Structured Data Extractions (FAQPage, HowTo, Service, ContactPoint)
        cls._extract_schema_units(soup, passage_registry, url)

        # 2. DOM-level Extractions
        cls._extract_dom_units(soup, passage_registry, source_label, url)

        # 3. Text/Passage Extractions across Heading Sections
        cls._extract_heading_section_units(soup, passage_registry, source_label, url)

        # Final list of distinct units
        units = list(passage_registry.values())
        total_units = len(units)

        # Count primary and secondary unit types
        units_by_type: Dict[str, int] = {}
        for u in units:
            t_name = u.unit_type.value
            units_by_type[t_name] = units_by_type.get(t_name, 0) + 1

        # 4. Evaluate Structural Clarity Conditions
        clarity_assessment = cls._evaluate_clarity(
            soup=soup,
            units=units,
            content_ev=content_ev,
            retrieval_readiness_ev=retrieval_readiness_ev
        )

        # 5. Connect with Phase 9 Topics (Refinement 1 & 2)
        topic_links = cls._link_topics(
            topic_ev=topic_ev,
            query_page_ev=query_page_ev,
            search_signal_ev=search_signal_ev,
            entity_ev=entity_ev,
            soup=soup,
            units=units
        )

        explained_count = sum(1 for tl in topic_links if tl.status == TopicExplanationStatus.EXPLAINED)
        mentioned_count = sum(1 for tl in topic_links if tl.status == TopicExplanationStatus.MENTIONED_ONLY)
        unsupported_count = sum(1 for tl in topic_links if tl.status == TopicExplanationStatus.UNSUPPORTED_HEADING)

        # Observable Facts & Analyses
        facts: List[str] = [
            f"Detected {total_units} distinct observable information unit(s) across {len(units_by_type)} structural types.",
            f"Evaluated {len(topic_links)} topic(s): {explained_count} explained with explicit units, {mentioned_count} mentioned only, {unsupported_count} unsupported headings.",
        ]
        for t_type, count in sorted(units_by_type.items()):
            facts.append(f"Structure '{t_type}': {count} unit(s) observed.")

        analyses: List[str] = []
        if clarity_assessment.unsupported_concepts:
            analyses.append(f"Detected {len(clarity_assessment.unsupported_concepts)} concept heading(s) with genuinely absent supporting body content.")
        if clarity_assessment.buried_facts:
            analyses.append(f"Detected {len(clarity_assessment.buried_facts)} passage(s) with dense technical facts in unbroken paragraphs > 150 words.")
        if clarity_assessment.obscured_or_fragmented_items:
            analyses.append(f"Detected {len(clarity_assessment.obscured_or_fragmented_items)} answerable unit(s) enclosed in elements with 'data-nosnippet' attributes.")

        return AnswerabilityEvidence(
            url=url,
            engine_source="answerability_engine",
            total_units_detected=total_units,
            units_by_type=units_by_type,
            units=units,
            clarity_assessment=clarity_assessment,
            topic_links=topic_links,
            explained_topics_count=explained_count,
            mentioned_only_topics_count=mentioned_count,
            unsupported_heading_topics_count=unsupported_count,
            facts=facts,
            analyses=analyses,
        )

    # -------------------------------------------------------------------------
    # 1. Schema JSON-LD Extractions
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_schema_units(
        cls,
        soup: BeautifulSoup,
        registry: Dict[str, AnswerableInformationUnit],
        url: str,
    ) -> None:
        """Extract FAQPage, HowTo, Service, ContactPoint from JSON-LD scripts."""
        scripts = soup.find_all("script", type="application/ld+json")
        idx = 0
        for s in scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
            except Exception:
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Handle @graph
                graph_items = item.get("@graph", [item]) if "@graph" in item else [item]
                for node in graph_items:
                    if not isinstance(node, dict):
                        continue
                    n_type = str(node.get("@type", "")).strip()

                    # FAQPage Schema
                    if "FAQPage" in n_type:
                        main_entity = node.get("mainEntity", [])
                        if isinstance(main_entity, dict):
                            main_entity = [main_entity]
                        for q_idx, q_item in enumerate(main_entity):
                            if not isinstance(q_item, dict):
                                continue
                            q_text = str(q_item.get("name", "")).strip()
                            ans = q_item.get("acceptedAnswer", {})
                            a_text = ""
                            if isinstance(ans, dict):
                                a_text = str(ans.get("text", "")).strip()
                            if q_text and a_text:
                                snippet_clean = bound_snippet(f"Q: {q_text} | A: {a_text}")
                                passage_key = f"schema_faq_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                                cls._register_unit(
                                    registry=registry,
                                    passage_key=passage_key,
                                    unit_type=AnswerableUnitType.FAQ,
                                    snippet=snippet_clean,
                                    location="script[type='application/ld+json'] > FAQPage",
                                    structural_type="jsonld_faqpage",
                                    section_heading=q_text,
                                    supporting_context=f"FAQ Question: {q_text}",
                                    source="schema_jsonld",
                                    extraction_method="jsonld_faq_extractor",
                                    confidence="high",
                                    secondary_type=AnswerableUnitType.DIRECT_ANSWER,
                                )

                    # HowTo Schema
                    elif "HowTo" in n_type:
                        h_name = str(node.get("name", "How To Procedure")).strip()
                        steps = node.get("step", [])
                        if isinstance(steps, dict):
                            steps = [steps]
                        step_texts = []
                        for s_idx, st in enumerate(steps):
                            if isinstance(st, dict):
                                s_text = str(st.get("text") or st.get("name") or "").strip()
                                if s_text:
                                    step_texts.append(f"{s_idx + 1}. {s_text}")
                        if step_texts:
                            snippet_clean = bound_snippet(f"{h_name}: " + " | ".join(step_texts))
                            passage_key = f"schema_howto_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                            cls._register_unit(
                                registry=registry,
                                passage_key=passage_key,
                                unit_type=AnswerableUnitType.PROCEDURE_STEPS,
                                snippet=snippet_clean,
                                location="script[type='application/ld+json'] > HowTo",
                                structural_type="jsonld_howto",
                                section_heading=h_name,
                                supporting_context=f"HowTo: {h_name}",
                                source="schema_jsonld",
                                extraction_method="jsonld_howto_extractor",
                                confidence="high",
                            )

                    # Service Schema
                    elif any(k in n_type for k in ("Service", "Product", "ProfessionalService")):
                        s_name = str(node.get("name", "")).strip()
                        s_desc = str(node.get("description", "")).strip()
                        if s_name and s_desc:
                            snippet_clean = bound_snippet(f"{s_name}: {s_desc}")
                            passage_key = f"schema_svc_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                            cls._register_unit(
                                registry=registry,
                                passage_key=passage_key,
                                unit_type=AnswerableUnitType.SERVICE_DESCRIPTION,
                                snippet=snippet_clean,
                                location=f"script[type='application/ld+json'] > {n_type}",
                                structural_type="jsonld_service",
                                section_heading=s_name,
                                supporting_context=f"Service: {s_name}",
                                source="schema_jsonld",
                                extraction_method="jsonld_service_extractor",
                                confidence="high",
                            )

                    # ContactPoint / LocalBusiness Schema
                    elif any(k in n_type for k in ("ContactPoint", "LocalBusiness", "Organization")):
                        tel = node.get("telephone")
                        email = node.get("email")
                        addr = node.get("address")
                        contact_parts = []
                        if tel:
                            contact_parts.append(f"Phone: {tel}")
                        if email:
                            contact_parts.append(f"Email: {email}")
                        if isinstance(addr, dict):
                            street = addr.get("streetAddress", "")
                            locality = addr.get("addressLocality", "")
                            country = addr.get("addressCountry", "")
                            contact_parts.append(f"Address: {street}, {locality}, {country}".strip(", "))
                        elif isinstance(addr, str) and addr.strip():
                            contact_parts.append(f"Address: {addr}")
                        if contact_parts:
                            snippet_clean = bound_snippet(" | ".join(contact_parts))
                            passage_key = f"schema_contact_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                            cls._register_unit(
                                registry=registry,
                                passage_key=passage_key,
                                unit_type=AnswerableUnitType.LOCATION_CONTACT,
                                snippet=snippet_clean,
                                location=f"script[type='application/ld+json'] > {n_type}",
                                structural_type="jsonld_contact",
                                section_heading="Contact & Location",
                                supporting_context=f"Entity: {n_type}",
                                source="schema_jsonld",
                                extraction_method="jsonld_contact_extractor",
                                confidence="high",
                            )

    # -------------------------------------------------------------------------
    # 2. DOM-level Extractions (Tables, Lists, DL, Details/Summary)
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_dom_units(
        cls,
        soup: BeautifulSoup,
        registry: Dict[str, AnswerableInformationUnit],
        source_label: str,
        url: str,
    ) -> None:
        """Extract DOM-level structured elements (tables, lists, definition lists, accordion)."""
        body = soup.find("body") or soup

        # Strategy A: Tables (TABLE, SPECIFICATION, COMPARISON)
        for t_idx, table in enumerate(body.find_all("table")):
            if cls._is_boilerplate(table):
                continue
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            th_cells = [th.get_text(strip=True) for th in table.find_all("th") if th.get_text(strip=True)]
            row_samples = []
            for r in rows[:4]:
                tds = [td.get_text(strip=True) for td in r.find_all(["td", "th"]) if td.get_text(strip=True)]
                if tds:
                    row_samples.append(" | ".join(tds))

            if not row_samples:
                continue

            table_text = "\n".join(row_samples)
            snippet_clean = bound_snippet(table_text)
            dom_loc = get_dom_path(table)
            passage_key = f"table_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"

            h_prev = cls._find_preceding_heading(table)
            h_text = h_prev.get_text(strip=True) if h_prev else None
            h_lower = h_text.lower() if h_text else ""

            # Detect if table represents SPECIFICATION or COMPARISON
            headers_lower = " ".join(th_cells).lower()
            is_comparison = (
                any(k in headers_lower or k in h_lower for k in COMPARISON_KEYWORDS)
                or "vs" in headers_lower
                or "vs" in h_lower
            )
            is_spec = any(k in headers_lower or k in h_lower for k in ("parameter", "specification", "spec", "standard", "rating", "dimension", "value", "uncertainty"))

            primary_type = AnswerableUnitType.TABLE
            sec_types = []
            if is_comparison:
                primary_type = AnswerableUnitType.COMPARISON
                sec_types.append(AnswerableUnitType.TABLE)
            elif is_spec:
                primary_type = AnswerableUnitType.SPECIFICATION
                sec_types.append(AnswerableUnitType.TABLE)

            cls._register_unit(
                registry=registry,
                passage_key=passage_key,
                unit_type=primary_type,
                snippet=snippet_clean,
                location=dom_loc,
                structural_type=f"html_table_{len(rows)}rows",
                section_heading=h_text,
                supporting_context=f"Table with headers: {', '.join(th_cells[:5])}" if th_cells else None,
                source=source_label,
                extraction_method="dom_table_parser",
                confidence="high",
                secondary_type=sec_types[0] if sec_types else None,
            )

        # Strategy B: Definition Lists (<dl>, <dt>, <dd>)
        for dl_idx, dl in enumerate(body.find_all("dl")):
            if cls._is_boilerplate(dl):
                continue
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            if dts and dds:
                dl_items = []
                for dt, dd in zip(dts[:5], dds[:5]):
                    t_str = dt.get_text(strip=True)
                    d_str = dd.get_text(strip=True)
                    if t_str and d_str:
                        dl_items.append(f"{t_str}: {d_str}")
                if dl_items:
                    snippet_clean = bound_snippet("; ".join(dl_items))
                    passage_key = f"dl_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                    dom_loc = get_dom_path(dl)
                    h_prev = cls._find_preceding_heading(dl)
                    cls._register_unit(
                        registry=registry,
                        passage_key=passage_key,
                        unit_type=AnswerableUnitType.DEFINITION,
                        snippet=snippet_clean,
                        location=dom_loc,
                        structural_type="html_dl",
                        section_heading=h_prev.get_text(strip=True) if h_prev else None,
                        supporting_context="Definition List",
                        source=source_label,
                        extraction_method="dom_dl_parser",
                        confidence="high",
                    )

        # Strategy C: Details / Summary (<details><summary>)
        for det_idx, det in enumerate(body.find_all("details")):
            sum_elem = det.find("summary")
            if sum_elem:
                q_text = sum_elem.get_text(strip=True)
                ans_text = " ".join([c.get_text(strip=True) for c in det.children if c != sum_elem and isinstance(c, Tag)])
                if q_text and ans_text:
                    snippet_clean = bound_snippet(f"Q: {q_text} | A: {ans_text}")
                    passage_key = f"details_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                    cls._register_unit(
                        registry=registry,
                        passage_key=passage_key,
                        unit_type=AnswerableUnitType.FAQ,
                        snippet=snippet_clean,
                        location=get_dom_path(det),
                        structural_type="html_details_summary",
                        section_heading=q_text,
                        supporting_context=f"Summary: {q_text}",
                        source=source_label,
                        extraction_method="dom_details_parser",
                        confidence="high",
                        secondary_type=AnswerableUnitType.DIRECT_ANSWER,
                    )

        # Strategy D: Ordered Lists (<ol>) for Procedures / Steps
        for ol_idx, ol in enumerate(body.find_all("ol")):
            if cls._is_boilerplate(ol):
                continue
            lis = [li.get_text(strip=True) for li in ol.find_all("li") if li.get_text(strip=True)]
            if len(lis) >= 2:
                step_items = [f"{i + 1}. {li}" for i, li in enumerate(lis[:6])]
                snippet_clean = bound_snippet(" | ".join(step_items))
                passage_key = f"ol_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                dom_loc = get_dom_path(ol)
                h_prev = cls._find_preceding_heading(ol)
                h_text = h_prev.get_text(strip=True) if h_prev else None
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.PROCEDURE_STEPS,
                    snippet=snippet_clean,
                    location=dom_loc,
                    structural_type=f"html_ol_{len(lis)}items",
                    section_heading=h_text,
                    supporting_context=f"Ordered step sequence: {h_text}" if h_text else "Ordered steps",
                    source=source_label,
                    extraction_method="dom_ordered_list_parser",
                    confidence="high",
                )

        # Strategy E: Substantive Unordered Lists (<ul>)
        for ul_idx, ul in enumerate(body.find_all("ul")):
            if cls._is_boilerplate(ul):
                continue
            lis = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True)]
            if len(lis) >= 3:
                # Exclude purely short link menus
                avg_len = sum(len(li.split()) for li in lis) / len(lis)
                if avg_len >= 3:
                    snippet_clean = bound_snippet(" • " + " • ".join(lis[:6]))
                    passage_key = f"ul_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                    h_prev = cls._find_preceding_heading(ul)
                    h_text = h_prev.get_text(strip=True) if h_prev else None

                    # Check if preceded by a Requirements or Eligibility heading
                    is_req = False
                    if h_text:
                        h_lower = h_text.lower()
                        is_req = any(k in h_lower for k in REQUIREMENT_KEYWORDS)

                    primary_type = AnswerableUnitType.REQUIREMENTS_ELIGIBILITY if is_req else AnswerableUnitType.LIST
                    sec_type = AnswerableUnitType.LIST if is_req else None

                    cls._register_unit(
                        registry=registry,
                        passage_key=passage_key,
                        unit_type=primary_type,
                        snippet=snippet_clean,
                        location=get_dom_path(ul),
                        structural_type=f"html_ul_{len(lis)}items",
                        section_heading=h_text,
                        supporting_context=f"Unordered list: {h_text}" if h_text else "Bullet list",
                        source=source_label,
                        extraction_method="dom_unordered_list_parser",
                        confidence="high",
                        secondary_type=sec_type,
                    )

        # Strategy F: Code / Examples (<code>, <pre>, <blockquote>)
        for pre_idx, pre in enumerate(body.find_all(["pre", "blockquote"])):
            if cls._is_boilerplate(pre):
                continue
            pre_text = pre.get_text(strip=True)
            if len(pre_text.split()) >= 4:
                snippet_clean = bound_snippet(pre_text)
                passage_key = f"example_{hashlib.md5(snippet_clean.encode()).hexdigest()[:10]}"
                h_prev = cls._find_preceding_heading(pre)
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.EXAMPLE,
                    snippet=snippet_clean,
                    location=get_dom_path(pre),
                    structural_type=f"html_{pre.name}",
                    section_heading=h_prev.get_text(strip=True) if h_prev else None,
                    supporting_context=f"Example block ({pre.name})",
                    source=source_label,
                    extraction_method="dom_example_parser",
                    confidence="high",
                )

    # -------------------------------------------------------------------------
    # 3. Heading Section Extractions (Definitions, Direct Answers, Services, Facts)
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_heading_section_units(
        cls,
        soup: BeautifulSoup,
        registry: Dict[str, AnswerableInformationUnit],
        source_label: str,
        url: str,
    ) -> None:
        """Inspect headings and their immediate sibling content paragraphs."""
        body = soup.find("body") or soup
        headings = body.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))

        for h in headings:
            h_tag = h.name.lower()
            h_text = h.get_text(strip=True)
            if not h_text:
                continue

            h_lower = h_text.lower().strip()

            # Collect immediate sibling text until next heading
            sibling_paragraphs: List[Tag] = []
            curr = h.next_sibling
            while curr:
                if isinstance(curr, Tag):
                    if re.match(r"^h[1-6]$", curr.name, re.IGNORECASE):
                        break
                    if curr.name in ("p", "div", "section") and not cls._is_boilerplate(curr):
                        p_txt = curr.get_text(strip=True)
                        if p_txt and len(p_txt.split()) >= 3:
                            sibling_paragraphs.append(curr)
                            if len(sibling_paragraphs) >= 3:
                                break
                curr = curr.next_sibling

            if not sibling_paragraphs:
                continue

            first_p = sibling_paragraphs[0]
            first_p_text = first_p.get_text(separator=" ", strip=True)
            first_sentence = first_p_text.split(".")[0] if "." in first_p_text else first_p_text

            p_loc = get_dom_path(first_p)
            passage_key = f"section_{hashlib.md5(first_p_text[:120].encode()).hexdigest()[:10]}"

            # Check 1: Direct Answer to Question Heading
            is_question = h_lower.endswith("?") or any(h_lower.startswith(qw + " ") for qw in QUESTION_WORDS)
            if is_question and len(first_p_text.split()) >= 4:
                snippet_clean = bound_snippet(f"Q: {h_text} | A: {first_p_text}")
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.DIRECT_ANSWER,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="heading_question_answer",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Interrogative heading: '{h_text}'",
                    source=source_label,
                    extraction_method="dom_heading_question_answer",
                    confidence="high",
                )

            # Check 2: Definition in Section Heading or Lead Sentence
            is_def_heading = (
                h_lower.startswith("what is ")
                or h_lower.startswith("definition of ")
                or "meaning of " in h_lower
            )
            copula_match = COPULA_DEFINITION_REGEX.search(first_p_text)
            dfn_elem = first_p.find("dfn")

            if is_def_heading or copula_match or dfn_elem:
                def_term = h_text
                if copula_match:
                    def_term = copula_match.group(1).strip()
                snippet_clean = bound_snippet(first_sentence + ("." if not first_sentence.endswith(".") else ""))
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.DEFINITION,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="copula_definition" if copula_match else "heading_definition",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Definition of '{def_term}'",
                    source=source_label,
                    extraction_method="text_copula_definition_parser",
                    confidence="high" if is_def_heading else "medium",
                )

            # Check 3: Service Description Section
            is_service_heading = any(k in h_lower for k in SERVICE_KEYWORDS)
            if is_service_heading and len(first_p_text.split()) >= 10:
                snippet_clean = bound_snippet(f"{h_text}: {first_p_text}")
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.SERVICE_DESCRIPTION,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="service_section_paragraph",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Service Section: '{h_text}'",
                    source=source_label,
                    extraction_method="dom_service_section_parser",
                    confidence="high",
                )

            # Check 4: Requirements / Eligibility Section
            is_req_heading = any(k in h_lower for k in REQUIREMENT_KEYWORDS)
            if is_req_heading and len(first_p_text.split()) >= 8:
                snippet_clean = bound_snippet(f"{h_text}: {first_p_text}")
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.REQUIREMENTS_ELIGIBILITY,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="requirements_section_paragraph",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Requirements Section: '{h_text}'",
                    source=source_label,
                    extraction_method="dom_requirements_section_parser",
                    confidence="high",
                )

            # Check 5: Observable Factual Statements (Refinement 3: conservative extraction)
            std_match = STANDARD_REGEX.findall(first_p_text)
            pct_match = PERCENTAGE_STAT_REGEX.findall(first_p_text)
            if std_match or pct_match:
                found_tokens = list(set(std_match + pct_match))
                snippet_clean = bound_snippet(first_sentence + ("." if not first_sentence.endswith(".") else ""))
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.FACTUAL_STATEMENT,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="standard_or_metric_statement",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Observable standards/metrics: {', '.join(found_tokens[:4])}",
                    source=source_label,
                    extraction_method="regex_standard_metric_parser",
                    confidence="medium",
                )

            # Check 6: Contact Information in text
            emails = EMAIL_REGEX.findall(first_p_text)
            phones = PHONE_REGEX.findall(first_p_text)
            if emails or phones or "contact" in h_lower or "reach us" in h_lower or "address" in h_lower:
                if emails or phones:
                    contact_items = [f"Email: {e}" for e in emails[:2]] + [f"Phone: {p}" for p in phones[:2]]
                    snippet_clean = bound_snippet(" | ".join(contact_items))
                    cls._register_unit(
                        registry=registry,
                        passage_key=passage_key,
                        unit_type=AnswerableUnitType.LOCATION_CONTACT,
                        snippet=snippet_clean,
                        location=p_loc,
                        structural_type="contact_paragraph",
                        section_heading=h_text,
                        heading_level=h_tag,
                        supporting_context="Contact details in passage",
                        source=source_label,
                        extraction_method="regex_contact_parser",
                        confidence="high",
                    )

            # Check 7: Date or Policy Statement
            date_match = DATE_POLICY_REGEX.search(first_p_text)
            if date_match:
                snippet_clean = bound_snippet(first_sentence)
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=AnswerableUnitType.DATE_POLICY,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="date_or_policy_statement",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Policy signal: '{date_match.group(0)}'",
                    source=source_label,
                    extraction_method="regex_date_policy_parser",
                    confidence="medium",
                )

            # Check 8 (GAP-ANSWER-001): Generic substantive heading + paragraph
            # Captures feature cards, generic FAQ items without <details>, step blocks, etc.
            if passage_key not in registry and len(first_p_text.split()) >= 10:
                snippet_clean = bound_snippet(f"{h_text}: {first_p_text}")
                
                # If heading looks like a step ("Step 1", "Phase 2", "How to")
                is_step = bool(re.search(r'^(step|phase|stage)\s*\d+|how\s+to', h_lower))
                unit_t = AnswerableUnitType.PROCEDURE_STEPS if is_step else AnswerableUnitType.FACTUAL_STATEMENT
                
                cls._register_unit(
                    registry=registry,
                    passage_key=passage_key,
                    unit_type=unit_t,
                    snippet=snippet_clean,
                    location=p_loc,
                    structural_type="heading_paragraph_block",
                    section_heading=h_text,
                    heading_level=h_tag,
                    supporting_context=f"Descriptive block: '{h_text}'",
                    source=source_label,
                    extraction_method="dom_heading_paragraph_parser",
                    confidence="medium",
                )

    # -------------------------------------------------------------------------
    # Unit Registration with Deduplication (Refinement 4)
    # -------------------------------------------------------------------------
    @classmethod
    def _register_unit(
        cls,
        registry: Dict[str, AnswerableInformationUnit],
        passage_key: str,
        unit_type: AnswerableUnitType,
        snippet: str,
        location: str,
        structural_type: str,
        section_heading: Optional[str] = None,
        heading_level: Optional[str] = None,
        supporting_context: Optional[str] = None,
        source: str = "raw_html",
        extraction_method: str = "dom_structure",
        confidence: str = "high",
        secondary_type: Optional[AnswerableUnitType] = None,
    ) -> None:
        """
        Register an information unit. If passage_key already exists, preserve
        secondary classification on the existing unit instead of adding duplicate units.
        """
        if passage_key in registry:
            existing = registry[passage_key]
            # Add new unit_type to secondary_types if not already primary or in secondary
            if unit_type != existing.unit_type and unit_type not in existing.secondary_types:
                existing.secondary_types.append(unit_type)
            if secondary_type and secondary_type != existing.unit_type and secondary_type not in existing.secondary_types:
                existing.secondary_types.append(secondary_type)
            return

        sec_types = [secondary_type] if secondary_type and secondary_type != unit_type else []
        unit = AnswerableInformationUnit(
            unit_id=f"unit-{unit_type.value.lower()}-{len(registry)}",
            unit_type=unit_type,
            secondary_types=sec_types,
            section_heading=section_heading,
            heading_level=heading_level,
            snippet=snippet,
            content_location=location,
            structural_type=structural_type,
            supporting_context=supporting_context,
            is_explicit=True,
            source=source,
            extraction_method=extraction_method,
            bounded_evidence=snippet[:180],
            confidence=confidence,
        )
        registry[passage_key] = unit

    # -------------------------------------------------------------------------
    # 4. Clarity Assessment (Refinements 2 & 3)
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_clarity(
        cls,
        soup: BeautifulSoup,
        units: List[AnswerableInformationUnit],
        content_ev: Optional[ContentEvidence] = None,
        retrieval_readiness_ev: Optional[RetrievalReadinessEvidence] = None,
    ) -> InformationClarityAssessment:
        """
        Evaluate structural clarity conditions using neutral observational terminology.
        Refinement 2: treat word counts as supporting telemetry, not rigid proof of unsupported headings.
        """
        body = soup.find("body") or soup
        headings = body.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))

        # A. Heading -> Content Relationship
        h_notes: List[str] = []
        genuinely_empty_headings: List[str] = []
        short_answer_headings: List[str] = []

        for h in headings:
            h_text = h.get_text(strip=True)
            if not h_text:
                continue

            # Count words between this heading and the next heading
            words_in_sec = 0
            curr = h.next_sibling
            has_any_content = False
            while curr:
                if isinstance(curr, Tag):
                    if re.match(r"^h[1-6]$", curr.name, re.IGNORECASE):
                        break
                    if not cls._is_boilerplate(curr):
                        txt = curr.get_text(separator=" ", strip=True)
                        if txt:
                            has_any_content = True
                            words_in_sec += len(txt.split())
                curr = curr.next_sibling

            if not has_any_content or words_in_sec == 0:
                genuinely_empty_headings.append(h_text[:40])
            elif words_in_sec < 10:
                short_answer_headings.append(h_text[:40])

        total_h = len(headings)
        if total_h == 0:
            h_status = ClarityStatus.ABSENT
            h_notes.append("No headings detected on page.")
        elif genuinely_empty_headings:
            h_status = ClarityStatus.PARTIAL
            h_notes.append(f"{len(genuinely_empty_headings)} heading(s) have genuinely absent supporting content.")
            if short_answer_headings:
                h_notes.append(f"{len(short_answer_headings)} heading(s) have concise supporting copy (< 10 words).")
        else:
            h_status = ClarityStatus.OBSERVED
            h_notes.append(f"All {total_h} heading(s) are accompanied by observable body content.")

        # B. Question -> Answer Patterns
        qa_units = [u for u in units if u.unit_type in (AnswerableUnitType.FAQ, AnswerableUnitType.DIRECT_ANSWER)]
        qa_notes: List[str] = []
        if qa_units:
            qa_status = ClarityStatus.PRESENT
            qa_notes.append(f"Detected {len(qa_units)} question-and-answer / direct answer structure(s).")
        else:
            qa_status = ClarityStatus.ABSENT
            qa_notes.append("No explicit Q&A or interrogative direct answer structures observed.")

        # C. Definition Patterns
        def_units = [u for u in units if u.unit_type == AnswerableUnitType.DEFINITION]
        def_notes: List[str] = []
        if def_units:
            def_status = ClarityStatus.PRESENT
            def_notes.append(f"Detected {len(def_units)} explicit definition structure(s).")
        else:
            def_status = ClarityStatus.ABSENT
            def_notes.append("No explicit term definitions or definition lists observed.")

        # D. Step / Procedural Structure
        step_units = [u for u in units if u.unit_type == AnswerableUnitType.PROCEDURE_STEPS]
        step_notes: List[str] = []
        if step_units:
            step_status = ClarityStatus.PRESENT
            step_notes.append(f"Detected {len(step_units)} structured procedure/step sequence(s).")
        else:
            step_status = ClarityStatus.ABSENT
            step_notes.append("No ordered step sequences or structured how-to procedures observed.")

        # E. Table Availability for Structured Data
        table_units = [u for u in units if u.unit_type in (AnswerableUnitType.TABLE, AnswerableUnitType.SPECIFICATION, AnswerableUnitType.COMPARISON)]
        tbl_notes: List[str] = []
        if table_units:
            tbl_status = ClarityStatus.PRESENT
            tbl_notes.append(f"Detected {len(table_units)} tabular data structure(s) presenting specifications/comparisons.")
        else:
            tbl_status = ClarityStatus.ABSENT
            tbl_notes.append("No structured HTML tables observed for tabular specifications.")

        # F. Buried Facts in Walls of Text (> 150 words without formatting)
        buried_facts: List[str] = []
        p_tags = body.find_all("p")
        for p in p_tags:
            if cls._is_boilerplate(p):
                continue
            p_text = p.get_text(separator=" ", strip=True)
            words = p_text.split()
            if len(words) > 150:
                has_std = bool(STANDARD_REGEX.search(p_text))
                has_pct = bool(PERCENTAGE_STAT_REGEX.search(p_text))
                has_spec = any(w in p_text.lower() for w in ("dimension", "voltage", "rating", "capacity", "accuracy"))
                if has_std or has_pct or has_spec:
                    buried_facts.append(bound_snippet(f"Dense paragraph ({len(words)} words): {p_text}"))

        # G. Obscured / nosnippet Elements (Interaction with M10.1)
        obscured_items: List[str] = []
        for u in units:
            # Check if this unit is located in a DOM node that has data-nosnippet
            if "data-nosnippet" in u.content_location.lower():
                obscured_items.append(f"Unit '{u.unit_id}' obscured by data-nosnippet at {u.content_location}")

        return InformationClarityAssessment(
            heading_content_relationship=h_status,
            heading_content_notes=h_notes,
            question_answer_patterns=qa_status,
            question_answer_notes=qa_notes,
            definition_patterns=def_status,
            definition_notes=def_notes,
            step_list_structure=step_status,
            step_list_notes=step_notes,
            table_availability=tbl_status,
            table_notes=tbl_notes,
            unsupported_concepts=genuinely_empty_headings,
            buried_facts=buried_facts,
            obscured_or_fragmented_items=obscured_items,
        )

    # -------------------------------------------------------------------------
    # 5. Connect with Phase 9 Topics (Refinement 1 & 2)
    # -------------------------------------------------------------------------
    @classmethod
    def _link_topics(
        cls,
        topic_ev: Optional[PageTopicIntelligence],
        query_page_ev: Optional[PageQueryEvidence],
        search_signal_ev: Optional[SearchSignalEvidence],
        entity_ev: Optional[EntityEvidence],
        soup: BeautifulSoup,
        units: List[AnswerableInformationUnit],
    ) -> List[TopicAnswerabilityLink]:
        """
        Deterministically link Phase 9 topics/concepts to observable information units.
        Refinement 1: Strict semantic verification (require unit text or heading to actually address the topic).
        Refinement 2: UNSUPPORTED_HEADING requires genuinely absent supporting content.
        """
        candidate_topics: Set[str] = set()

        if topic_ev and topic_ev.topics:
            for t in topic_ev.topics:
                if t.topic_name:
                    candidate_topics.add(t.topic_name)

        if query_page_ev and query_page_ev.mapped_concepts:
            for c in query_page_ev.mapped_concepts:
                if c.concept:
                    candidate_topics.add(c.concept)

        if not candidate_topics and search_signal_ev and search_signal_ev.signals:
            for sig in search_signal_ev.signals[:8]:
                if sig.term and len(sig.term) >= 4:
                    candidate_topics.add(sig.term)

        if not candidate_topics and entity_ev and entity_ev.detected_entities:
            for ent in entity_ev.detected_entities[:6]:
                if ent.name and len(ent.name) >= 4:
                    candidate_topics.add(ent.name)

        links: List[TopicAnswerabilityLink] = []
        body = soup.find("body") or soup
        body_text_lower = body.get_text(separator=" ", strip=True).lower()
        headings = body.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))

        for topic in sorted(candidate_topics):
            topic_lower = topic.lower().strip()
            topic_tokens = clean_tokens(topic_lower)
            if not topic_tokens:
                continue

            # Check if topic appears in any heading
            matching_heading: Optional[Tag] = None
            for h in headings:
                h_text = h.get_text(strip=True)
                h_lower = h_text.lower()
                if topic_lower in h_lower or all(tok in h_lower for tok in topic_tokens):
                    matching_heading = h
                    break

            # Check if heading has genuinely absent supporting content (Refinement 2)
            heading_unsupported = False
            if matching_heading:
                curr = matching_heading.next_sibling
                has_body = False
                while curr:
                    if isinstance(curr, Tag):
                        if re.match(r"^h[1-6]$", curr.name, re.IGNORECASE):
                            break
                        if not cls._is_boilerplate(curr) and curr.get_text(strip=True):
                            has_body = True
                            break
                    curr = curr.next_sibling
                if not has_body:
                    heading_unsupported = True

            # Match units addressing this topic (Refinement 1: strict semantic check)
            matching_units: List[AnswerableInformationUnit] = []
            for u in units:
                snippet_lower = u.snippet.lower()
                u_head_lower = (u.section_heading or "").lower()

                # Semantic check: topic tokens must be present in snippet OR heading
                # AND if in heading, the snippet itself must have at least one topic token or substantive answer
                token_in_snippet = topic_lower in snippet_lower or any(tok in snippet_lower for tok in topic_tokens)
                token_in_heading = topic_lower in u_head_lower or all(tok in u_head_lower for tok in topic_tokens)

                if (token_in_snippet and token_in_heading) or (token_in_snippet and len(topic_tokens) <= 2):
                    matching_units.append(u)
                elif token_in_heading and len(u.snippet.split()) >= 6:
                    # Heading matches topic, and unit snippet provides substantive text under that heading
                    matching_units.append(u)

            if matching_units:
                # Top matching unit provides explanation
                best_unit = matching_units[0]
                unit_types = list(set([u.unit_type for u in matching_units]))
                links.append(TopicAnswerabilityLink(
                    topic_name=topic,
                    status=TopicExplanationStatus.EXPLAINED,
                    section_heading=best_unit.section_heading or (matching_heading.get_text(strip=True) if matching_heading else None),
                    associated_unit_ids=[u.unit_id for u in matching_units],
                    unit_types=unit_types,
                    explanation_snippet=best_unit.snippet,
                    is_explicit=best_unit.is_explicit,
                    evidence_notes=[f"Explained via {len(matching_units)} unit(s): {', '.join(t.value for t in unit_types)}"],
                ))
            elif heading_unsupported:
                links.append(TopicAnswerabilityLink(
                    topic_name=topic,
                    status=TopicExplanationStatus.UNSUPPORTED_HEADING,
                    section_heading=matching_heading.get_text(strip=True) if matching_heading else None,
                    associated_unit_ids=[],
                    unit_types=[],
                    explanation_snippet=None,
                    is_explicit=False,
                    evidence_notes=["Topic present in heading, but section has genuinely absent supporting content."],
                ))
            elif topic_lower in body_text_lower:
                links.append(TopicAnswerabilityLink(
                    topic_name=topic,
                    status=TopicExplanationStatus.MENTIONED_ONLY,
                    section_heading=matching_heading.get_text(strip=True) if matching_heading else None,
                    associated_unit_ids=[],
                    unit_types=[],
                    explanation_snippet=None,
                    is_explicit=False,
                    evidence_notes=["Topic observed in page body, but lacks dedicated answerable structure or explanation."],
                ))
            else:
                links.append(TopicAnswerabilityLink(
                    topic_name=topic,
                    status=TopicExplanationStatus.ABSENT,
                    section_heading=None,
                    associated_unit_ids=[],
                    unit_types=[],
                    explanation_snippet=None,
                    is_explicit=False,
                    evidence_notes=["Topic not observed in visible page content."],
                ))

        return links

    # -------------------------------------------------------------------------
    # Site-Wide Crawl Aggregator
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_site(cls, site_crawl: SiteCrawlResult) -> SiteAnswerabilityIntelligence:
        """
        Aggregate multi-page answerability intelligence across crawled records.
        """
        records = getattr(site_crawl, "crawl_records", [])
        total_pages = len(records)
        is_partial = (
            site_crawl.completeness_status != "CRAWL_COMPLETE"
            or site_crawl.remaining_frontier > 0
        )
        disclaimer = ""
        if is_partial:
            disclaimer = (
                f"Evaluation is partial: crawl completed with status '{site_crawl.completeness_status}'. "
                f"{site_crawl.remaining_frontier} frontier URLs remained unvisited."
            )

        pages_with_faq: List[str] = []
        pages_with_def: List[str] = []
        pages_with_steps: List[str] = []
        pages_with_tables: List[str] = []
        pages_with_unsupported: List[str] = []
        site_units_by_type: Dict[str, int] = {}
        total_site_units = 0
        page_evidence_map: Dict[str, AnswerabilityEvidence] = {}

        for rec in records:
            if getattr(rec, "answerability", None) is not None:
                ev = rec.answerability
            else:
                ev = cls.evaluate_page(
                    url=rec.url,
                    raw_html=rec.raw_html,
                    rendered_html=None,
                )
            page_evidence_map[rec.url] = ev
            total_site_units += ev.total_units_detected

            for t_name, count in ev.units_by_type.items():
                site_units_by_type[t_name] = site_units_by_type.get(t_name, 0) + count

            if ev.units_by_type.get(AnswerableUnitType.FAQ.value, 0) > 0:
                pages_with_faq.append(rec.url)
            if ev.units_by_type.get(AnswerableUnitType.DEFINITION.value, 0) > 0:
                pages_with_def.append(rec.url)
            if ev.units_by_type.get(AnswerableUnitType.PROCEDURE_STEPS.value, 0) > 0:
                pages_with_steps.append(rec.url)
            if (
                ev.units_by_type.get(AnswerableUnitType.TABLE.value, 0) > 0
                or ev.units_by_type.get(AnswerableUnitType.SPECIFICATION.value, 0) > 0
            ):
                pages_with_tables.append(rec.url)
            if ev.clarity_assessment.unsupported_concepts:
                pages_with_unsupported.append(rec.url)

        facts: List[str] = [
            f"Evaluated {total_pages} crawled page(s) for AI answerability and information extraction.",
            f"Total distinct observable information units detected: {total_site_units}.",
            f"Pages with FAQ structures: {len(pages_with_faq)}",
            f"Pages with explicit definitions: {len(pages_with_def)}",
            f"Pages with structured procedural steps: {len(pages_with_steps)}",
            f"Pages with tabular data/specifications: {len(pages_with_tables)}",
            f"Pages with unsupported concept headings: {len(pages_with_unsupported)}",
        ]

        analyses: List[str] = []
        if pages_with_faq:
            analyses.append(f"{len(pages_with_faq)} page(s) offer explicit Q&A structures readily extractable by AI retrieval.")
        if pages_with_tables:
            analyses.append(f"{len(pages_with_tables)} page(s) provide tabular structures for technical specifications or comparisons.")
        if pages_with_unsupported:
            analyses.append(f"{len(pages_with_unsupported)} page(s) exhibit empty headings lacking supporting body content.")

        intel = SiteAnswerabilityIntelligence(
            status="success",
            total_pages_evaluated=total_pages,
            is_partial_crawl=is_partial,
            completeness_disclaimer=disclaimer,
            total_site_units_detected=total_site_units,
            site_units_by_type=site_units_by_type,
            pages_with_faq=pages_with_faq,
            pages_with_definitions=pages_with_def,
            pages_with_steps=pages_with_steps,
            pages_with_tables=pages_with_tables,
            pages_with_unsupported_concepts=pages_with_unsupported,
            page_answerability_evidence=page_evidence_map,
            facts=facts,
            analyses=analyses,
        )

        site_crawl.answerability_intelligence = intel
        return intel

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------
    @classmethod
    def _is_boilerplate(cls, elem: Tag) -> bool:
        """Check if tag is in boilerplate tags or boilerplate containers."""
        if elem.name in BOILERPLATE_TAGS:
            return True
        curr = elem
        while curr and curr.name and curr.name != "[document]":
            if curr.name in BOILERPLATE_TAGS:
                return True
            cls_str = " ".join(curr.get("class", [])) if isinstance(curr.get("class"), list) else str(curr.get("class", ""))
            id_str = str(curr.get("id", ""))
            role_str = str(curr.get("role", "")).lower()
            if role_str in ("navigation", "banner", "contentinfo"):
                return True
            if re.search(r"\b(nav|navbar|sidebar|footer|header|menu|cookie)\b", cls_str, re.IGNORECASE):
                return True
            if re.search(r"\b(nav|navbar|sidebar|footer|header|menu|cookie)\b", id_str, re.IGNORECASE):
                return True
            curr = curr.parent
        return False

    @classmethod
    def _find_preceding_heading(cls, elem: Tag) -> Optional[Tag]:
        """Traverse previous siblings / ancestors to find the nearest preceding heading."""
        curr = elem.previous_sibling
        while curr:
            if isinstance(curr, Tag):
                if re.match(r"^h[1-6]$", curr.name, re.IGNORECASE):
                    return curr
                found_h = curr.find(re.compile(r"^h[1-6]$", re.IGNORECASE))
                if found_h:
                    return found_h
            curr = curr.previous_sibling
        if elem.parent and elem.parent.name and elem.parent.name != "[document]":
            return cls._find_preceding_heading(elem.parent)
        return None
