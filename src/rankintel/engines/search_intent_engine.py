"""
Search Intent Engine — Deterministic on-site search-intent signal analysis (Layer A).
Evaluates observable structural, lexical, schema, and layout signals to infer intent hypotheses.
Operates strictly in-memory on already-crawled HTML and evidence without external APIs,
search volume, CTR, rankings, or LLMs.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple, Any
from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    SearchIntentCategory,
    IntentEvidenceItem,
    PageIntentEvidence,
    SearchSignalConfidence,
    OnPageEvidence,
    SearchSignalEvidence,
    PageTopicIntelligence,
    PageQueryEvidence,
    ContentEvidence,
    EntityEvidence,
    SchemaEvidence,
)


class SearchIntentEngine:
    """
    Evaluates deterministic search-intent signals from observable single-page content.
    Applies multi-signal corroboration rules: individual isolated tokens (e.g. 'best', 'pricing',
    'review', generic 'contact us') are captured as evidence items only and never determine
    intent classification on their own without corroborating structural evidence.
    """

    # Informational patterns
    RE_INFO_HEADINGS = re.compile(
        r"^(what\s+is|what\s+are|how\s+to|how\s+does|how\s+do|why\s+is|why\s+do|why\s+does|"
        r"guide\s+to|overview\s+of|definition\s+of|introduction\s+to|understanding|"
        r"tutorial|instructions|basics\s+of|explained|step-by-step)",
        re.IGNORECASE,
    )
    RE_INFO_KEYWORDS = re.compile(
        r"\b(faq|faqs|frequently\s+asked\s+questions|guide|overview|definition|"
        r"tutorial|documentation|specifications|glossary|standards|methodology)\b",
        re.IGNORECASE,
    )
    RE_INFO_REFERENCE = re.compile(
        r"\b(company\s+details|director\s+details|registration\s+details|cin|din|incorporation|"
        r"trademark|records|database|search\s+records|registry)\b",
        re.IGNORECASE,
    )

    # Commercial evaluation patterns
    RE_COMM_VS = re.compile(r"\b[a-z0-9]+\s+(?:vs\.?|versus)\s+[a-z0-9]+\b", re.IGNORECASE)
    RE_COMM_EVAL = re.compile(
        r"\b(comparison|compare|feature\s+matrix|pricing\s+plans|pros\s+and\s+cons|"
        r"buyer'?s\s+guide|alternatives|evaluation\s+criteria)\b",
        re.IGNORECASE,
    )
    RE_COMM_ISOLATED = re.compile(
        r"\b(best|top|pricing|plans|review|reviews|features|ratings|benchmark)\b",
        re.IGNORECASE,
    )

    # Transactional action patterns (E-commerce vs B2B Lead Gen)
    RE_TRANS_ECOMM_CTA = re.compile(
        r"\b(add\s+to\s+cart|buy\s+now|order\s+now|checkout)\b",
        re.IGNORECASE,
    )
    RE_TRANS_LEAD_GEN_CTA = re.compile(
        r"\b(request\s+a\s+quote|get\s+a\s+quote|schedule\s+(?:an?\s+)?appointment|schedule\s+demo|"
        r"apply\s+online|inquire\s+now|request\s+pricing|get\s+started\s+now|book\s+now)\b",
        re.IGNORECASE,
    )
    RE_TRANS_ISOLATED = re.compile(
        r"\b(buy|order|purchase|cart|checkout|contact\s+us|sign\s+up|register|subscribe)\b",
        re.IGNORECASE,
    )

    # Local address/phone patterns
    RE_PIN_CODE = re.compile(r"\b\d{6}\b")  # India PIN code
    RE_ZIP_CODE = re.compile(r"\b\d{5}(?:-\d{4})?\b")  # US Zip
    RE_LOCAL_PHONE = re.compile(r"(?:\+91[-\s]?\d{2,5}[-\s]?\d{6,8}|\b0\d{2,4}[-\s]?\d{6,8}\b|\(\d{3}\)\s*\d{3}[-\s]\d{4})")
    RE_ADDRESS_TERMS = re.compile(
        r"\b(registered\s+office|head\s+office|branch\s+office|corporate\s+office|address\s*:|location\s*:|plot\s+no|sector\s+\d+|road|street|nagar|marg|industrial\s+area|testing\s+lab|calibration\s+center)\b",
        re.IGNORECASE,
    )

    @classmethod
    def evaluate(
        cls,
        url: str = "",
        raw_html: Optional[str] = None,
        on_page: Optional[OnPageEvidence] = None,
        search_signal_ev: Optional[SearchSignalEvidence] = None,
        topic_intel_ev: Optional[PageTopicIntelligence] = None,
        query_page_ev: Optional[PageQueryEvidence] = None,
        content_ev: Optional[ContentEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
        schema_ev: Optional[SchemaEvidence] = None,
    ) -> PageIntentEvidence:
        """
        Derives deterministic search-intent signals and corroboration from observable single-page evidence.
        """
        if not raw_html and not on_page and not search_signal_ev:
            return PageIntentEvidence(
                url=url,
                engine_source="search_intent_engine",
                status="skipped",
                error_message="No HTML or evidence provided for search intent evaluation.",
                primary_observed_intent_signal=SearchIntentCategory.UNSPECIFIED,
                facts=["No content or HTML provided for intent analysis."],
                analyses=["INFERRED_FROM_ON_SITE_EVIDENCE: Search intent cannot be inferred without observable content."],
            )

        evidence_items: List[IntentEvidenceItem] = []
        facts: List[str] = []
        analyses: List[str] = []
        corroboration_notes: List[str] = []

        # Structural signal points: {category: int}
        structural_signals: Dict[SearchIntentCategory, int] = {c: 0 for c in SearchIntentCategory}
        supporting_signals: Dict[SearchIntentCategory, int] = {c: 0 for c in SearchIntentCategory}

        soup = BeautifulSoup(raw_html, "html.parser") if raw_html else None

        # ----------------------------------------------------------------------
        # 1. Structural Schema Signals
        # ----------------------------------------------------------------------
        schema_types: List[str] = []
        if schema_ev and schema_ev.detected_types:
            schema_types = schema_ev.detected_types
        elif soup:
            # Check script ld+json
            for script in soup.find_all("script", type="application/ld+json"):
                if script.string:
                    for m in re.findall(r'"@type"\s*:\s*"([^"]+)"', script.string):
                        schema_types.append(m)

        for st in schema_types:
            norm_st = st.lower()
            if any(t in norm_st for t in ["faqpage", "howto", "techarticle", "article", "blogposting", "newsarticle"]):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.INFORMATIONAL,
                    signal_type="STRUCTURED_SCHEMA_TYPE",
                    evidence_term=st,
                    evidence_location="SCHEMA",
                    supporting_snippet=f"JSON-LD Schema declares @type: {st}",
                    confidence=SearchSignalConfidence.DIRECT,
                ))
                structural_signals[SearchIntentCategory.INFORMATIONAL] += 2
                facts.append(f"Structured data declares informational schema type '{st}'.")

            if any(t in norm_st for t in ["offer", "orderaction", "buyaction", "reserveaction"]):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.TRANSACTIONAL,
                    signal_type="STRUCTURED_SCHEMA_TYPE",
                    evidence_term=st,
                    evidence_location="SCHEMA",
                    supporting_snippet=f"JSON-LD Schema declares transactional @type: {st}",
                    confidence=SearchSignalConfidence.DIRECT,
                ))
                structural_signals[SearchIntentCategory.TRANSACTIONAL] += 2
                facts.append(f"Structured data declares transactional schema type '{st}'.")

            if any(t in norm_st for t in ["postaladdress", "localbusiness", "place", "geocoordinates"]):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.LOCAL,
                    signal_type="STRUCTURED_SCHEMA_TYPE",
                    evidence_term=st,
                    evidence_location="SCHEMA",
                    supporting_snippet=f"JSON-LD Schema declares geographic/local @type: {st}",
                    confidence=SearchSignalConfidence.DIRECT,
                ))
                structural_signals[SearchIntentCategory.LOCAL] += 2
                facts.append(f"Structured data declares local geographic schema type '{st}'.")

            if any(t in norm_st for t in ["website", "organization"]):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.NAVIGATIONAL,
                    signal_type="STRUCTURED_SCHEMA_TYPE",
                    evidence_term=st,
                    evidence_location="SCHEMA",
                    supporting_snippet=f"JSON-LD Schema declares organizational/brand @type: {st}",
                    confidence=SearchSignalConfidence.SUPPORTED,
                ))
                supporting_signals[SearchIntentCategory.NAVIGATIONAL] += 1

        # ----------------------------------------------------------------------
        # 2. On-Page Structural Elements (Headings, Tables, Forms, CTAs)
        # ----------------------------------------------------------------------
        all_headings: List[Tuple[str, str]] = []  # (tag, text)
        if soup:
            for h in soup.find_all(["h1", "h2", "h3"]):
                txt = h.get_text(strip=True)
                if txt:
                    all_headings.append((h.name.upper(), txt))
        elif on_page:
            for h1 in on_page.h1_text:
                all_headings.append(("H1", h1))
            for h2 in on_page.h2_text:
                all_headings.append(("H2", h2))
            for h3 in on_page.h3_text:
                all_headings.append(("H3", h3))

        info_heading_count = 0
        comm_heading_count = 0
        ref_heading_count = 0
        for tag, text in all_headings:
            # Informational check
            if cls.RE_INFO_HEADINGS.search(text):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.INFORMATIONAL,
                    signal_type="EXPLANATORY_HEADING",
                    evidence_term=text[:60],
                    evidence_location=tag,
                    supporting_snippet=f"Explanatory heading structure: '{text[:80]}'",
                    confidence=SearchSignalConfidence.DIRECT,
                ))
                structural_signals[SearchIntentCategory.INFORMATIONAL] += 2
                info_heading_count += 1
            elif cls.RE_INFO_REFERENCE.search(text):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.INFORMATIONAL_REFERENCE,
                    signal_type="REFERENCE_DB_HEADING",
                    evidence_term=text[:60],
                    evidence_location=tag,
                    supporting_snippet=f"Reference lookup heading: '{text[:80]}'",
                    confidence=SearchSignalConfidence.DIRECT,
                ))
                structural_signals[SearchIntentCategory.INFORMATIONAL_REFERENCE] += 2
                ref_heading_count += 1
            elif cls.RE_INFO_KEYWORDS.search(text):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.INFORMATIONAL,
                    signal_type="INFORMATIONAL_TOPIC_HEADING",
                    evidence_term=text[:60],
                    evidence_location=tag,
                    supporting_snippet=f"Informational keyword in heading: '{text[:80]}'",
                    confidence=SearchSignalConfidence.SUPPORTED,
                ))
                supporting_signals[SearchIntentCategory.INFORMATIONAL] += 1

            # Commercial check
            if cls.RE_COMM_VS.search(text) or cls.RE_COMM_EVAL.search(text):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.COMMERCIAL,
                    signal_type="COMPARISON_EVALUATION_HEADING",
                    evidence_term=text[:60],
                    evidence_location=tag,
                    supporting_snippet=f"Evaluation heading structure: '{text[:80]}'",
                    confidence=SearchSignalConfidence.DIRECT,
                ))
                structural_signals[SearchIntentCategory.COMMERCIAL] += 2
                comm_heading_count += 1
            elif cls.RE_COMM_ISOLATED.search(text):
                evidence_items.append(IntentEvidenceItem(
                    intent_category=SearchIntentCategory.COMMERCIAL,
                    signal_type="COMMERCIAL_TOKEN_EVIDENCE",
                    evidence_term=text[:60],
                    evidence_location=tag,
                    supporting_snippet=f"Commercial evaluation term in heading: '{text[:80]}'",
                    confidence=SearchSignalConfidence.WEAK,
                ))
                supporting_signals[SearchIntentCategory.COMMERCIAL] += 1

        if info_heading_count > 0:
            facts.append(f"Page contains {info_heading_count} heading(s) matching explanatory/educational syntax.")
        if comm_heading_count > 0:
            facts.append(f"Page contains {comm_heading_count} heading(s) matching comparison/evaluation syntax.")

        # DOM Table Structure (Comparison / Pricing Matrices)
        if soup:
            tables = soup.find_all("table")
            for tbl in tables:
                tbl_text = tbl.get_text(" ", strip=True).lower()
                if any(w in tbl_text for w in ["price", "pricing", "plan", "features", "comparison", "specification", "tier"]):
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.COMMERCIAL,
                        signal_type="COMPARISON_PRICING_TABLE",
                        evidence_term="table",
                        evidence_location="BODY_TABLE",
                        supporting_snippet=f"Structural evaluation table: {tbl_text[:80]}...",
                        confidence=SearchSignalConfidence.DIRECT,
                    ))
                    structural_signals[SearchIntentCategory.COMMERCIAL] += 2
                    facts.append("Page contains structural evaluation or comparison/pricing table.")
                    break

        # Transactional CTAs and Action Forms
        cta_count = 0
        form_count = 0
        if soup:
            # Check buttons and CTA anchors
            for elem in soup.find_all(["button", "a"]):
                elem_txt = elem.get_text(" ", strip=True)
                if cls.RE_TRANS_ECOMM_CTA.search(elem_txt):
                    match_str = cls.RE_TRANS_ECOMM_CTA.search(elem_txt).group(0)
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.TRANSACTIONAL_ECOMMERCE,
                        signal_type="ECOMMERCE_CALL_TO_ACTION",
                        evidence_term=match_str,
                        evidence_location=f"CTA_{elem.name.upper()}",
                        supporting_snippet=f"High-intent e-commerce action element: '{elem_txt[:60]}'",
                        confidence=SearchSignalConfidence.DIRECT,
                    ))
                    structural_signals[SearchIntentCategory.TRANSACTIONAL_ECOMMERCE] += 2
                    cta_count += 1
                elif cls.RE_TRANS_LEAD_GEN_CTA.search(elem_txt):
                    match_str = cls.RE_TRANS_LEAD_GEN_CTA.search(elem_txt).group(0)
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.TRANSACTIONAL_LEAD_GEN,
                        signal_type="LEAD_GEN_CALL_TO_ACTION",
                        evidence_term=match_str,
                        evidence_location=f"CTA_{elem.name.upper()}",
                        supporting_snippet=f"High-intent lead generation action element: '{elem_txt[:60]}'",
                        confidence=SearchSignalConfidence.DIRECT,
                    ))
                    structural_signals[SearchIntentCategory.TRANSACTIONAL_LEAD_GEN] += 2
                    cta_count += 1
                elif cls.RE_TRANS_ISOLATED.search(elem_txt):
                    # Captured as evidence item ONLY; not an automatic transactional classification
                    match_str = cls.RE_TRANS_ISOLATED.search(elem_txt).group(0)
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.TRANSACTIONAL,
                        signal_type="ISOLATED_ACTION_TOKEN",
                        evidence_term=match_str,
                        evidence_location=f"LINK_{elem.name.upper()}",
                        supporting_snippet=f"Isolated action link: '{elem_txt[:60]}'",
                        confidence=SearchSignalConfidence.WEAK,
                    ))
                    supporting_signals[SearchIntentCategory.TRANSACTIONAL] += 1

            # Check for transactional contact / quote / checkout forms
            for form in soup.find_all("form"):
                form_text = form.get_text(" ", strip=True).lower()
                form_inputs = [inp.get("name", "").lower() for inp in form.find_all(["input", "textarea", "select"])]
                inputs_str = " ".join(form_inputs)
                
                if any(w in form_text or w in inputs_str for w in ["checkout", "order", "cart"]):
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.TRANSACTIONAL_ECOMMERCE,
                        signal_type="ECOMMERCE_CHECKOUT_FORM",
                        evidence_term="form",
                        evidence_location="FORM_ELEMENT",
                        supporting_snippet=f"Interactive e-commerce submission form with fields: {', '.join(form_inputs[:4])}",
                        confidence=SearchSignalConfidence.DIRECT,
                    ))
                    structural_signals[SearchIntentCategory.TRANSACTIONAL_ECOMMERCE] += 2
                    form_count += 1
                    break
                elif any(w in form_text or w in inputs_str for w in ["quote", "inquiry", "message", "book", "schedule", "phone", "email"]):
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.TRANSACTIONAL_LEAD_GEN,
                        signal_type="LEAD_GEN_INQUIRY_FORM",
                        evidence_term="form",
                        evidence_location="FORM_ELEMENT",
                        supporting_snippet=f"Interactive inquiry/quote submission form with fields: {', '.join(form_inputs[:4])}",
                        confidence=SearchSignalConfidence.DIRECT,
                    ))
                    structural_signals[SearchIntentCategory.TRANSACTIONAL_LEAD_GEN] += 2
                    form_count += 1
                    break

        if cta_count > 0:
            facts.append(f"Page contains {cta_count} specific call-to-action button/element(s).")
        if form_count > 0:
            facts.append("Page contains interactive inquiry/transaction submission form.")

        # ----------------------------------------------------------------------
        # 3. Navigational & Brand Identity Signals
        # ----------------------------------------------------------------------
        parsed = urlparse(url)
        is_root_path = parsed.path in ("", "/", "/index.html", "/index.php")
        title_text = on_page.title if on_page else ""
        h1_text = on_page.h1_text[0] if (on_page and on_page.h1_text) else ""

        # Check for brand/homepage focus
        if is_root_path:
            evidence_items.append(IntentEvidenceItem(
                intent_category=SearchIntentCategory.NAVIGATIONAL,
                signal_type="ROOT_HOMEPAGE_STRUCTURE",
                evidence_term=parsed.netloc,
                evidence_location="URL_PATH",
                supporting_snippet=f"Root domain entrypoint: {url}",
                confidence=SearchSignalConfidence.SUPPORTED,
            ))
            supporting_signals[SearchIntentCategory.NAVIGATIONAL] += 1

            # If title or H1 corresponds to official brand name
            if entity_ev and entity_ev.detected_entities:
                org_names = [e.name.lower() for e in entity_ev.detected_entities if "organization" in str(e.entity_type).lower()]
                if any(org in title_text.lower() or org in h1_text.lower() for org in org_names):
                    evidence_items.append(IntentEvidenceItem(
                        intent_category=SearchIntentCategory.NAVIGATIONAL,
                        signal_type="OFFICIAL_BRAND_HOMEPAGE",
                        evidence_term="Brand Name in Title/H1",
                        evidence_location="TITLE_H1",
                        supporting_snippet=f"Homepage prominently identifies primary entity: {title_text[:60]}",
                        confidence=SearchSignalConfidence.DIRECT,
                    ))
                    structural_signals[SearchIntentCategory.NAVIGATIONAL] += 2
                    facts.append("Homepage Title/H1 correlates directly with verified organization entity.")

        # Check for dedicated navigational utility endpoints
        if any(p in parsed.path.lower() for p in ["/login", "/portal", "/signin", "/dashboard", "/account"]):
            evidence_items.append(IntentEvidenceItem(
                intent_category=SearchIntentCategory.NAVIGATIONAL,
                signal_type="PORTAL_LOGIN_ENDPOINT",
                evidence_term=parsed.path,
                evidence_location="URL_PATH",
                supporting_snippet=f"Dedicated utility/portal endpoint: {parsed.path}",
                confidence=SearchSignalConfidence.DIRECT,
            ))
            structural_signals[SearchIntentCategory.NAVIGATIONAL] += 2
            facts.append(f"URL path '{parsed.path}' corresponds to a dedicated user portal/login navigation destination.")

        # ----------------------------------------------------------------------
        # 4. Local Geographic Signals
        # ----------------------------------------------------------------------
        body_text = ""
        if soup:
            body_text = soup.get_text(" ", strip=True)
        elif content_ev and getattr(content_ev, "main_content_text_preview", None):
            body_text = content_ev.main_content_text_preview

        # Check Map Embeds
        if soup and soup.find("iframe", src=re.compile(r"google\.com/maps|openstreetmap", re.IGNORECASE)):
            evidence_items.append(IntentEvidenceItem(
                intent_category=SearchIntentCategory.LOCAL,
                signal_type="EMBEDDED_MAP",
                evidence_term="iframe map",
                evidence_location="BODY_IFRAME",
                supporting_snippet="Embedded interactive map detected in DOM.",
                confidence=SearchSignalConfidence.DIRECT,
            ))
            structural_signals[SearchIntentCategory.LOCAL] += 2
            facts.append("Page contains embedded geographic map.")

        # Check Physical Address Patterns
        if cls.RE_ADDRESS_TERMS.search(body_text) and (cls.RE_PIN_CODE.search(body_text) or cls.RE_ZIP_CODE.search(body_text)):
            match_addr = cls.RE_ADDRESS_TERMS.search(body_text).group(0)
            evidence_items.append(IntentEvidenceItem(
                intent_category=SearchIntentCategory.LOCAL,
                signal_type="PHYSICAL_ADDRESS_SIGNALS",
                evidence_term=match_addr,
                evidence_location="BODY_CONTENT",
                supporting_snippet=f"Physical address marker found: '{match_addr}' with postal code.",
                confidence=SearchSignalConfidence.DIRECT,
            ))
            structural_signals[SearchIntentCategory.LOCAL] += 2
            facts.append("Observable text contains formal physical address indicators and postal code.")

        if cls.RE_LOCAL_PHONE.search(body_text):
            phone_match = cls.RE_LOCAL_PHONE.search(body_text).group(0)
            evidence_items.append(IntentEvidenceItem(
                intent_category=SearchIntentCategory.LOCAL,
                signal_type="LOCAL_TELEPHONE_FORMAT",
                evidence_term=phone_match,
                evidence_location="BODY_CONTENT",
                supporting_snippet=f"Localized dialing format telephone number: '{phone_match}'",
                confidence=SearchSignalConfidence.SUPPORTED,
            ))
            supporting_signals[SearchIntentCategory.LOCAL] += 1

        # ----------------------------------------------------------------------
        # 5. Extract Associated Topics (from M9.2 and M9.3)
        # ----------------------------------------------------------------------
        associated_topics: List[str] = []
        if topic_intel_ev and topic_intel_ev.topics:
            for top in topic_intel_ev.topics[:6]:
                if top.topic_name and top.topic_name not in associated_topics:
                    associated_topics.append(top.topic_name)
        elif query_page_ev and query_page_ev.primary_concepts:
            for c in query_page_ev.primary_concepts[:6]:
                if c not in associated_topics:
                    associated_topics.append(c)

        # ----------------------------------------------------------------------
        # 6. Multi-Signal Corroboration & Intent Determination
        # ----------------------------------------------------------------------
        # Calculate composite score for each category:
        # A category qualifies as evidenced ONLY IF:
        # 1. It has at least one DIRECT structural signal (structural_signals >= 2), OR
        # 2. It has multiple corroborating supporting signals (supporting_signals >= 2).
        composite_scores: Dict[SearchIntentCategory, int] = {}
        intent_counts: Dict[str, int] = {}

        for cat in [
            SearchIntentCategory.INFORMATIONAL,
            SearchIntentCategory.INFORMATIONAL_REFERENCE,
            SearchIntentCategory.COMMERCIAL,
            SearchIntentCategory.TRANSACTIONAL,
            SearchIntentCategory.TRANSACTIONAL_ECOMMERCE,
            SearchIntentCategory.TRANSACTIONAL_LEAD_GEN,
            SearchIntentCategory.NAVIGATIONAL,
            SearchIntentCategory.LOCAL,
            SearchIntentCategory.LOCAL_SERVICE,
        ]:
            s_score = structural_signals[cat]
            sup_score = supporting_signals[cat]
            total_items = len([it for it in evidence_items if it.intent_category == cat])
            intent_counts[cat.value] = total_items

            if s_score >= 2 or sup_score >= 2:
                composite_scores[cat] = s_score + sup_score
                corroboration_notes.append(
                    f"Category '{cat.value}' satisfies corroboration threshold (structural: {s_score}, supporting: {sup_score})."
                )
            elif total_items > 0:
                corroboration_notes.append(
                    f"Category '{cat.value}' has {total_items} isolated evidence item(s) but does not meet multi-signal corroboration threshold."
                )

        # Determine primary and secondary intent signals
        primary_intent = SearchIntentCategory.UNSPECIFIED
        secondary_intents: List[SearchIntentCategory] = []

        if not composite_scores:
            primary_intent = SearchIntentCategory.UNSPECIFIED
            analyses.append(
                "INFERRED_FROM_ON_SITE_EVIDENCE: Observed signals do not cross multi-signal corroboration threshold; intent remains UNSPECIFIED."
            )
        else:
            sorted_cats = sorted(composite_scores.items(), key=lambda x: x[1], reverse=True)
            top_cat, top_score = sorted_cats[0]

            # Check if tied or close secondary
            if len(sorted_cats) > 1:
                second_cat, second_score = sorted_cats[1]
                if top_score == second_score and top_score >= 4:
                    primary_intent = SearchIntentCategory.MIXED
                    secondary_intents = [top_cat, second_cat]
                    analyses.append(
                        f"INFERRED_FROM_ON_SITE_EVIDENCE: Content exhibits balanced co-equal intent signals between '{top_cat.value}' and '{second_cat.value}' (classified as MIXED)."
                    )
                else:
                    primary_intent = top_cat
                    for sc, sc_score in sorted_cats[1:]:
                        if sc_score >= 2:
                            secondary_intents.append(sc)
                    analyses.append(
                        f"INFERRED_FROM_ON_SITE_EVIDENCE: Primary observed intent signal is '{primary_intent.value}' based on {top_score} corroborating evidence points."
                    )
                    if secondary_intents:
                        sec_str = ", ".join([s.value for s in secondary_intents])
                        analyses.append(
                            f"INFERRED_FROM_ON_SITE_EVIDENCE: Secondary observed intent signal(s): {sec_str}."
                        )
            else:
                primary_intent = top_cat
                analyses.append(
                    f"INFERRED_FROM_ON_SITE_EVIDENCE: Primary observed intent signal is '{primary_intent.value}' based on {top_score} corroborating evidence points."
                )

        # Topic-Intent Alignment Note
        if associated_topics and primary_intent != SearchIntentCategory.UNSPECIFIED:
            topics_sample = ", ".join(associated_topics[:3])
            analyses.append(
                f"INFERRED_FROM_ON_SITE_EVIDENCE: On-site topics [{topics_sample}] align predominantly with '{primary_intent.value}' intent signals on this page."
            )

        return PageIntentEvidence(
            url=url,
            engine_source="search_intent_engine",
            status="success",
            primary_observed_intent_signal=primary_intent,
            secondary_observed_intent_signals=secondary_intents,
            intent_counts=intent_counts,
            evidence_items=evidence_items,
            associated_topics=associated_topics,
            corroboration_notes=corroboration_notes,
            terminology_nature="INFERRED_FROM_ON_SITE_EVIDENCE",
            facts=facts,
            analyses=analyses,
        )
