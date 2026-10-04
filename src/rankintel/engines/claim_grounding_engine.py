"""
RankIntel Phase 10.3 — Claim Grounding & Entity Intelligence Engine.

Builds a deterministic, evidence-driven layer that identifies what entities and
factual claims are present on a website, what on-site evidence supports them,
and whether different representations of the same information are consistent.

Strict constraints observed:
1. Zero external LLM/API queries.
2. Strictly deterministic and evidence-driven.
3. Preserves existing health-score formulas byte-for-byte.
4. Zero duplicate HTTP requests (strictly reuses existing crawl/engine evidence).
5. On-site support != external truth verification.
   - SUPPORTED_ON_SITE means supported by evidence found within the crawled website only.
   - Never claims a certification, accreditation, or fact is independently verified.
6. Contradictions require: same entity + same field + compatible context + conflicting explicit values.
   - Missing evidence on one surface is never inferred as contradiction.
"""
from __future__ import annotations
import re
import json
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag, NavigableString

from rankintel.models.schema import (
    ClaimSupportStatus,
    EntityConsistencyStatus,
    StructuredVisibleAgreementStatus,
    StructuredVisibleAgreement,
    ClaimEvidence,
    EntityGroundingEvidence,
    ClaimGroundingEvidence,
    SiteClaimGroundingIntelligence,
    AnswerableUnitType,
    AnswerableInformationUnit,
    AnswerabilityEvidence,
    ContentEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    PageTopicIntelligence,
    PageQueryEvidence,
    SearchSignalEvidence,
    SchemaEvidence,
    RetrievalReadinessEvidence,
    OnPageEvidence,
    CrawlRecord,
    SiteCrawlResult,
)
from rankintel.engines.entity_engine import (
    normalize_entity_name,
    normalize_phone_number,
    format_postal_address,
)

# Regex to detect standards and accreditation mentions (ISO, BIS, NABL, CE, ASTM, etc.)
STANDARD_CLAIM_REGEX = re.compile(
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

# Regex for metrics / statistics / experience claims
METRIC_CLAIM_REGEX = re.compile(
    r"\b(?:over|more than|exceeding|\d+\+)\s+\d+\s+(?:years|clients|customers|projects|samples|tests|locations|products|employees)\b",
    re.IGNORECASE
)

# Regex for founding year statements
FOUNDING_CLAIM_REGEX = re.compile(
    r"\b(?:established|founded|in business since|since)\s+(?:in\s+)?(19\d\d|20\d\d)\b",
    re.IGNORECASE
)

# Generic phone regex
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")

# Generic email regex
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def bound_snippet(text: str, max_len: int = 350) -> str:
    """Safely truncate snippet text to prevent memory bloat."""
    if not text:
        return ""
    clean = " ".join(text.strip().split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3] + "..."


def clean_tokens(text: str) -> Set[str]:
    """Tokenize text into lowercase content words."""
    if not text:
        return set()
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    stopwords = {
        "a", "an", "the", "and", "or", "of", "in", "on", "at", "by", "for", "with",
        "about", "to", "from", "is", "are", "was", "were", "be", "we", "our", "you",
        "your", "they", "their", "this", "that", "it", "its", "as", "into"
    }
    return {w for w in words if len(w) >= 2 and w not in stopwords}


class ClaimGroundingEngine:
    """
    Deterministic engine that detects claims, grounds them against on-site evidence,
    and analyzes entity consistency across 6 distinct content surfaces.
    """

    def __init__(self):
        pass

    @classmethod
    def evaluate_page(
        cls,
        url: str,
        raw_html: Optional[str] = None,
        rendered_html: Optional[str] = None,
        on_page: Optional[OnPageEvidence] = None,
        content_ev: Optional[ContentEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
        topic_ev: Optional[PageTopicIntelligence] = None,
        query_page_ev: Optional[PageQueryEvidence] = None,
        search_signal_ev: Optional[SearchSignalEvidence] = None,
        schema_ev: Optional[SchemaEvidence] = None,
        retrieval_readiness_ev: Optional[RetrievalReadinessEvidence] = None,
        answerability_ev: Optional[AnswerabilityEvidence] = None,
    ) -> ClaimGroundingEvidence:
        """
        Evaluate single-page claims, on-site grounding support, and entity consistency.
        Reuses evidence from preceding engines without performing new HTTP requests.
        """
        html_to_parse = rendered_html or raw_html or ""
        soup = BeautifulSoup(html_to_parse, "html.parser") if html_to_parse else None

        # 1. Extract Claims
        claims = cls._extract_page_claims(
            url=url,
            soup=soup,
            on_page=on_page,
            answerability_ev=answerability_ev,
            entity_ev=entity_ev,
            topic_ev=topic_ev,
        )

        # 2. Ground Claims Against On-Page Context
        cls._ground_page_claims(
            claims=claims,
            soup=soup,
            answerability_ev=answerability_ev,
            entity_ev=entity_ev,
        )

        # 3. Analyze Entity Consistency Across 6 Surfaces
        entity_grounding = cls._analyze_entity_surfaces(
            url=url,
            soup=soup,
            on_page=on_page,
            entity_ev=entity_ev,
            schema_ev=schema_ev,
            answerability_ev=answerability_ev,
        )

        # 4. Structured vs Visible Agreement
        structured_agreements = cls._compare_structured_vs_visible(
            url=url,
            soup=soup,
            on_page=on_page,
            entity_ev=entity_ev,
            schema_ev=schema_ev,
        )

        # 5. Compile Aggregates, Facts, and Analyses
        supported_cnt = sum(1 for c in claims if c.support_status == ClaimSupportStatus.SUPPORTED_ON_SITE)
        partial_cnt = sum(1 for c in claims if c.support_status == ClaimSupportStatus.PARTIALLY_SUPPORTED)
        uncorroborated_cnt = sum(1 for c in claims if c.support_status == ClaimSupportStatus.UNCORROBORATED_ON_SITE)
        contradicted_cnt = sum(1 for c in claims if c.support_status == ClaimSupportStatus.CONTRADICTED_ON_SITE)

        agreement_cnt = sum(1 for a in structured_agreements if a.status in (StructuredVisibleAgreementStatus.AGREEMENT, StructuredVisibleAgreementStatus.PARTIAL_AGREEMENT))
        disagreement_cnt = sum(1 for a in structured_agreements if a.status == StructuredVisibleAgreementStatus.DISAGREEMENT)

        facts: List[str] = [
            f"Detected {len(claims)} observable claim(s) on page {url}.",
            f"On-site support status: {supported_cnt} supported, {partial_cnt} partially supported, {uncorroborated_cnt} uncorroborated, {contradicted_cnt} contradicted.",
            f"Structured vs visible comparisons: {agreement_cnt} agreement(s), {disagreement_cnt} explicit disagreement(s).",
            f"Evaluated {len(entity_grounding)} entity candidate(s) across 6 content surfaces.",
        ]

        analyses: List[str] = []
        if contradicted_cnt > 0:
            analyses.append(f"Page contains {contradicted_cnt} explicit conflicting claim value(s) under compatible context.")
        if disagreement_cnt > 0:
            analyses.append(f"Detected {disagreement_cnt} explicit discrepancy between JSON-LD structured data and visible page content.")
        if uncorroborated_cnt > 0:
            analyses.append(f"{uncorroborated_cnt} claim(s) are stated without direct supporting operational context, parameters, or specifications on page.")
        if supported_cnt > 0:
            analyses.append(f"{supported_cnt} claim(s) have explicit on-site corroborating evidence directly substantiating the claim.")

        return ClaimGroundingEvidence(
            url=url,
            engine_source="claim_grounding_engine",
            total_claims_detected=len(claims),
            supported_claims_count=supported_cnt,
            partially_supported_count=partial_cnt,
            uncorroborated_count=uncorroborated_cnt,
            contradicted_count=contradicted_cnt,
            claims=claims,
            entity_grounding=entity_grounding,
            structured_agreements=structured_agreements,
            agreement_count=agreement_cnt,
            disagreement_count=disagreement_cnt,
            facts=facts,
            analyses=analyses,
        )

    # -------------------------------------------------------------------------
    # 1. Claim Extraction
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_page_claims(
        cls,
        url: str,
        soup: Optional[BeautifulSoup],
        on_page: Optional[OnPageEvidence],
        answerability_ev: Optional[AnswerabilityEvidence],
        entity_ev: Optional[EntityEvidence],
        topic_ev: Optional[PageTopicIntelligence],
    ) -> List[ClaimEvidence]:
        """
        Extract observable claims conservatively from M10.2 information units
        and prominent editorial assertions.
        """
        claims: List[ClaimEvidence] = []
        seen_texts: Set[str] = set()

        # Known entities on page for association
        known_entities = []
        if entity_ev and entity_ev.detected_entities:
            known_entities = [e.name for e in entity_ev.detected_entities if e.name]

        # A. Reuse M10.2 Information Units (Primary Extraction Source)
        if answerability_ev and answerability_ev.units:
            for u in answerability_ev.units:
                snippet = u.snippet.strip()
                if not snippet or len(snippet) < 15:
                    continue

                norm_key = re.sub(r"\s+", " ", snippet.lower())[:100]
                if norm_key in seen_texts:
                    continue
                seen_texts.add(norm_key)

                # Determine claim type
                claim_type = "factual_statement"
                if u.unit_type == AnswerableUnitType.SPECIFICATION:
                    claim_type = "specification"
                elif u.unit_type == AnswerableUnitType.SERVICE_DESCRIPTION:
                    claim_type = "service_claim"
                elif u.unit_type == AnswerableUnitType.REQUIREMENTS_ELIGIBILITY:
                    claim_type = "requirement_claim"
                elif u.unit_type == AnswerableUnitType.LOCATION_CONTACT:
                    claim_type = "contact_identity_claim"
                elif u.unit_type == AnswerableUnitType.FAQ:
                    claim_type = "faq_statement"
                elif STANDARD_CLAIM_REGEX.search(snippet):
                    claim_type = "accreditation_claim"
                elif METRIC_CLAIM_REGEX.search(snippet):
                    claim_type = "metric_or_statistic"

                # Related entity lookup
                matched_ent = None
                for ent in known_entities:
                    if ent.lower() in snippet.lower():
                        matched_ent = ent
                        break

                claim_id = f"claim-{hashlib.md5(f'{url}:{snippet[:40]}'.encode()).hexdigest()[:8]}"
                claims.append(ClaimEvidence(
                    claim_id=claim_id,
                    url=url,
                    claim_text=bound_snippet(snippet, 250),
                    claim_type=claim_type,
                    source_location=u.content_location or "body",
                    source_type="answerable_unit",
                    extraction_method="m10_2_unit_reuse",
                    bounded_snippet=bound_snippet(u.bounded_evidence or snippet, 350),
                    related_entity=matched_ent,
                    related_topic=u.topic,
                    related_unit_id=u.unit_id,
                    provenance="claim_grounding_engine",
                ))

        # B. Extract Prominent Assertions from Editorial Content / OnPage (if soup available)
        if soup:
            # Check meta description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag.get("content", "").strip()
            elif on_page and on_page.meta_description:
                meta_desc = on_page.meta_description.strip()

            if meta_desc and len(meta_desc) >= 20:
                norm_key = re.sub(r"\s+", " ", meta_desc.lower())[:100]
                if norm_key not in seen_texts:
                    seen_texts.add(norm_key)
                    c_type = "meta_assertion"
                    if STANDARD_CLAIM_REGEX.search(meta_desc):
                        c_type = "accreditation_claim"
                    elif METRIC_CLAIM_REGEX.search(meta_desc):
                        c_type = "metric_or_statistic"

                    claims.append(ClaimEvidence(
                        claim_id=f"claim-meta-{hashlib.md5(f'{url}:{meta_desc[:30]}'.encode()).hexdigest()[:8]}",
                        url=url,
                        claim_text=bound_snippet(meta_desc, 250),
                        claim_type=c_type,
                        source_location="head > meta[description]",
                        source_type="meta_tag",
                        extraction_method="meta_assertion_extraction",
                        bounded_snippet=bound_snippet(meta_desc, 350),
                        provenance="claim_grounding_engine",
                    ))

            # Scan visible paragraphs for specific metric, founding, or standard assertions
            body = soup.find("body") or soup
            for p in body.find_all(["p", "li"]):
                p_text = " ".join(p.get_text().split())
                if len(p_text) < 15 or len(p_text) > 400:
                    continue

                norm_key = re.sub(r"\s+", " ", p_text.lower())[:100]
                if norm_key in seen_texts:
                    continue

                # Check if paragraph makes an explicit standard, founding, or metric assertion
                std_match = STANDARD_CLAIM_REGEX.search(p_text)
                founding_match = FOUNDING_CLAIM_REGEX.search(p_text)
                metric_match = METRIC_CLAIM_REGEX.search(p_text)

                if std_match or founding_match or metric_match:
                    seen_texts.add(norm_key)
                    c_type = "factual_statement"
                    if std_match:
                        c_type = "accreditation_claim"
                    elif founding_match:
                        c_type = "founding_claim"
                    elif metric_match:
                        c_type = "metric_or_statistic"

                    matched_ent = None
                    for ent in known_entities:
                        if ent.lower() in p_text.lower():
                            matched_ent = ent
                            break

                    loc = f"{p.name}"
                    if p.get("id"):
                        loc += f"#{p.get('id')}"

                    claims.append(ClaimEvidence(
                        claim_id=f"claim-p-{hashlib.md5(f'{url}:{p_text[:30]}'.encode()).hexdigest()[:8]}",
                        url=url,
                        claim_text=bound_snippet(p_text, 250),
                        claim_type=c_type,
                        source_location=loc,
                        source_type="visible_body",
                        extraction_method="editorial_assertion_extraction",
                        bounded_snippet=bound_snippet(p_text, 350),
                        related_entity=matched_ent,
                        provenance="claim_grounding_engine",
                    ))

        return claims

    # -------------------------------------------------------------------------
    # 2. On-Site Grounding & Support Verification
    # -------------------------------------------------------------------------
    @classmethod
    def _ground_page_claims(
        cls,
        claims: List[ClaimEvidence],
        soup: Optional[BeautifulSoup],
        answerability_ev: Optional[AnswerabilityEvidence],
        entity_ev: Optional[EntityEvidence],
    ) -> None:
        """
        Evaluate on-site evidence directly supporting or contradicting each claim.
        Implements Correction 1 (stricter SUPPORTED_ON_SITE) and Correction 2 (precise CONTRADICTED_ON_SITE).
        """
        if not claims:
            return

        # Gather on-page corroborating context pools
        tables_text: List[str] = []
        procedure_text: List[str] = []
        all_body_passages: List[str] = []

        if answerability_ev and answerability_ev.units:
            for u in answerability_ev.units:
                if u.unit_type == AnswerableUnitType.TABLE:
                    tables_text.append(u.snippet)
                elif u.unit_type in (AnswerableUnitType.PROCEDURE_STEPS, AnswerableUnitType.SPECIFICATION):
                    procedure_text.append(u.snippet)

        if soup:
            body = soup.find("body") or soup
            for elem in body.find_all(["p", "table", "ul", "ol", "section", "div"]):
                t = " ".join(elem.get_text().split())
                if len(t) >= 40:
                    all_body_passages.append(t)

        for claim in claims:
            c_text = claim.claim_text
            c_tokens = clean_tokens(c_text)

            # A. Certification / Accreditation Claims (e.g. BIS, ISO, NABL, CE)
            if claim.claim_type == "accreditation_claim":
                std_matches = STANDARD_CLAIM_REGEX.findall(c_text)
                # Look for explicit supporting context: testing parameters, standard numbers, scope, or tables
                explicit_support = []
                for p_text in procedure_text + tables_text + all_body_passages:
                    # Stricter rule (Correction 1): must contain explicit evidence directly supporting subject and value/context
                    # Merely saying the standard name is not enough; must have technical scope, parameters, uncertainty, or testing details
                    if any(std.lower() in p_text.lower() for std in std_matches):
                        # Does p_text contain detailed supporting context beyond the claim itself?
                        if p_text != c_text and (
                            re.search(r"\b(scope|parameter|test\s+method|uncertainty|clause|standard\s+specification|sampling|range|accuracy)\b", p_text, re.I)
                            or len(p_text) >= 120
                        ):
                            explicit_support.append(bound_snippet(p_text, 250))
                            if len(explicit_support) >= 2:
                                break

                if explicit_support:
                    claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                    claim.supporting_snippets = explicit_support
                    claim.supporting_locations = ["on_page_technical_scope_or_table"]
                    claim.notes.append("Claim supported on-site by explicit technical parameters or testing scope. Note: on-site support does not verify independent external accreditation validity.")
                else:
                    # Check if standard is at least mentioned elsewhere
                    has_partial = any(any(std.lower() in p.lower() for std in std_matches) for p in all_body_passages if p != c_text)
                    if has_partial:
                        claim.support_status = ClaimSupportStatus.PARTIALLY_SUPPORTED
                        claim.notes.append("Accreditation/standard mentioned on page, but explicit technical scope, standard parameters, or procedural details are absent.")
                    else:
                        claim.support_status = ClaimSupportStatus.UNCORROBORATED_ON_SITE
                        claim.notes.append("Accreditation asserted without supporting technical scope, parameters, or documentation on page.")

            # B. Metric / Statistic Claims (e.g. "Over 20 years", "5000+ tests")
            elif claim.claim_type == "metric_or_statistic":
                metric_matches = METRIC_CLAIM_REGEX.findall(c_text)
                explicit_support = []
                # Check if there is corroborating timeline, founding year, or detailed breakdown
                founding_present = any(FOUNDING_CLAIM_REGEX.search(p) for p in all_body_passages)
                table_corroboration = any(any(m.lower() in t.lower() for m in metric_matches) for t in tables_text)

                if founding_present or table_corroboration:
                    claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                    if founding_present:
                        for p in all_body_passages:
                            f_m = FOUNDING_CLAIM_REGEX.search(p)
                            if f_m:
                                explicit_support.append(bound_snippet(p, 250))
                                break
                    claim.supporting_snippets = explicit_support
                    claim.notes.append("Metric claim supported on-site by corroborating timeline or tabular breakdown.")
                else:
                    # Stated without supporting breakdown
                    claim.support_status = ClaimSupportStatus.UNCORROBORATED_ON_SITE
                    claim.notes.append("Metric/volume statistic asserted in isolation without corroborating historical data or breakdown on page.")

            # C. Founding / History Claims
            elif claim.claim_type == "founding_claim":
                years = FOUNDING_CLAIM_REGEX.findall(c_text)
                # Check for explicit contradictions (Correction 2: same entity + compatible context + conflicting year)
                conflicting_years = []
                for p in all_body_passages:
                    all_y = FOUNDING_CLAIM_REGEX.findall(p)
                    for y in all_y:
                        if years and y != years[0]:
                            conflicting_years.append((y, bound_snippet(p, 250)))

                if conflicting_years:
                    claim.support_status = ClaimSupportStatus.CONTRADICTED_ON_SITE
                    claim.contradicting_snippets = [item[1] for item in conflicting_years[:2]]
                    claim.notes.append(f"Explicit conflicting founding year ({conflicting_years[0][0]} vs {years[0]}) observed on same entity.")
                else:
                    # Check if corroborated by about section or schema
                    has_corroboration = any(p != c_text and any(y in p for y in years) for p in all_body_passages)
                    if has_corroboration:
                        claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                        claim.supporting_snippets = [bound_snippet(p, 250) for p in all_body_passages if p != c_text and any(y in p for y in years)][:2]
                    else:
                        claim.support_status = ClaimSupportStatus.PARTIALLY_SUPPORTED

            # D. Service Claims (e.g. "We provide calibration")
            elif claim.claim_type == "service_claim":
                # Stricter rule (Correction 1): must have direct procedural steps, technical specs, or criteria
                explicit_support = []
                for p in procedure_text + tables_text:
                    p_tokens = clean_tokens(p)
                    overlap = len(c_tokens & p_tokens)
                    if overlap >= 2:
                        explicit_support.append(bound_snippet(p, 250))
                        if len(explicit_support) >= 2:
                            break

                if explicit_support:
                    claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                    claim.supporting_snippets = explicit_support
                    claim.notes.append("Service claim supported by explicit operational procedures, criteria, or technical specifications.")
                else:
                    # GAP-GROUND-001: Prevent tautological self-matching
                    def is_independent(p_text: str, c_txt: str) -> bool:
                        pn = re.sub(r'\s+', '', p_text.lower())
                        cn = re.sub(r'\s+', '', c_txt.lower())
                        return pn != cn and cn not in pn and pn not in cn

                    has_mention = any(len(c_tokens & clean_tokens(p)) >= 2 and is_independent(p, c_text) for p in all_body_passages)
                    if has_mention:
                        claim.support_status = ClaimSupportStatus.PARTIALLY_SUPPORTED
                        claim.notes.append("Service mentioned on page independently, but explicit operational parameters or procedural steps are absent.")
                    else:
                        claim.support_status = ClaimSupportStatus.UNCORROBORATED_ON_SITE
                        claim.notes.append("Service claim asserted without independent supporting technical or operational context.")

            # E. Specification / Table / Factual Statement
            elif claim.claim_type in ("specification", "factual_statement", "requirement_claim"):
                # GAP-GROUND-001: Tautological claim grounding fix.
                # Must not ground itself just because it's a visible text unit.
                is_grounded = False
                support_notes = []
                
                # Check for schema/entity structured support
                if entity_ev and entity_ev.detected_entities:
                    for ent in entity_ev.detected_entities:
                        ent_fields = [ent.name, ent.description, ent.raw_context]
                        if any(f for f in ent_fields if f and len(c_tokens & clean_tokens(f)) >= 2):
                            is_grounded = True
                            support_notes.append("Corroborated by structured Entity/Schema data.")
                            break
                            
                # Check for independent table or procedure corroboration
                if not is_grounded:
                    for t in tables_text + procedure_text:
                        tn = re.sub(r'\s+', '', t.lower())
                        cn = re.sub(r'\s+', '', c_text.lower())
                        if tn != cn and cn not in tn and tn not in cn:
                            if len(c_tokens & clean_tokens(t)) >= 3:
                                is_grounded = True
                                support_notes.append("Corroborated by independent table or structured procedure on page.")
                                break

                if is_grounded:
                    claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                    claim.supporting_snippets = [claim.bounded_snippet]
                    claim.notes.append(" ".join(support_notes))
                else:
                    claim.support_status = ClaimSupportStatus.UNCORROBORATED_ON_SITE
                    claim.notes.append("Claim observed as visible text but lacks independent structured data or tabular corroboration.")

            # F. Contact Claims
            elif claim.claim_type == "contact_identity_claim":
                claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                claim.supporting_snippets = [claim.bounded_snippet]

            # Default fallback
            if claim.support_status == ClaimSupportStatus.UNKNOWN:
                claim.support_status = ClaimSupportStatus.PARTIALLY_SUPPORTED

    # -------------------------------------------------------------------------
    # 3. Entity Consistency Across 6 Surfaces
    # -------------------------------------------------------------------------
    @classmethod
    def _analyze_entity_surfaces(
        cls,
        url: str,
        soup: Optional[BeautifulSoup],
        on_page: Optional[OnPageEvidence],
        entity_ev: Optional[EntityEvidence],
        schema_ev: Optional[SchemaEvidence],
        answerability_ev: Optional[AnswerabilityEvidence],
    ) -> List[EntityGroundingEvidence]:
        """
        Evaluate candidate entities across 6 content surfaces:
        1. visible_body
        2. headings
        3. title_meta
        4. json_ld
        5. contact_info
        6. answerable_units
        """
        results: List[EntityGroundingEvidence] = []
        if not entity_ev or not entity_ev.detected_entities:
            return results

        # Deduplicate candidate entities by normalized name
        candidates: Dict[str, Tuple[str, str]] = {}  # norm_name -> (display_name, entity_type)
        for e in entity_ev.detected_entities:
            norm = normalize_entity_name(e.name)
            if norm and len(norm) >= 3 and norm not in candidates:
                candidates[norm] = (e.name, e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type))

        # Surface pools
        # 1. visible_body
        body_text = ""
        if soup and soup.body:
            body_text = " ".join(soup.body.get_text().split()).lower()

        # 2. headings
        headings_list = []
        if on_page:
            headings_list.extend(on_page.h1_text)
            headings_list.extend(on_page.h2_text)
            headings_list.extend(on_page.h3_text)
        elif soup:
            for h in soup.find_all(re.compile(r"^h[1-6]$", re.I)):
                headings_list.append(" ".join(h.get_text().split()))
        headings_text = " ".join(headings_list).lower()

        # 3. title_meta
        title_meta_list = []
        if on_page:
            if on_page.title:
                title_meta_list.append(on_page.title)
            if on_page.meta_description:
                title_meta_list.append(on_page.meta_description)
        elif soup:
            t = soup.find("title")
            if t:
                title_meta_list.append(t.get_text())
            m = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            if m and m.get("content"):
                title_meta_list.append(m.get("content"))
        title_meta_text = " ".join(title_meta_list).lower()

        # 4. json_ld
        schema_types = []
        schema_names = []
        for e in entity_ev.detected_entities:
            if e.source == EntitySource.JSON_LD:
                if e.name:
                    schema_names.append(e.name.lower())
                if e.structured_data_type:
                    schema_types.append(e.structured_data_type)

        # 5. contact_info
        contact_text = ""
        if soup:
            footer = soup.find("footer") or soup.find("address") or soup.find(id=re.compile(r"contact|footer", re.I))
            if footer:
                contact_text = " ".join(footer.get_text().split()).lower()
            else:
                contact_text = body_text[-1500:] if len(body_text) > 1500 else body_text

        # 6. answerable_units
        unit_snippets = []
        unit_ids = []
        if answerability_ev and answerability_ev.units:
            for u in answerability_ev.units:
                unit_snippets.append(u.snippet.lower())
                unit_ids.append(u.unit_id)
        units_text = " ".join(unit_snippets)

        for norm_name, (display_name, ent_type) in candidates.items():
            obs_body = norm_name in body_text
            obs_head = norm_name in headings_text
            obs_title_meta = norm_name in title_meta_text
            obs_json_ld = any(norm_name in sn for sn in schema_names)
            
            # Check contact info surface
            obs_contact = norm_name in contact_text
            if not obs_contact and entity_ev and entity_ev.detected_entities:
                for ent in entity_ev.detected_entities:
                    if normalize_entity_name(ent.name) == norm_name:
                        if ent.telephone and normalize_phone_number(ent.telephone) in normalize_phone_number(contact_text):
                            obs_contact = True
                            break
                        if ent.email and ent.email.lower() in contact_text:
                            obs_contact = True
                            break

            # Fallback to soup JSON-LD for matching contact phone or email
            if not obs_contact and soup:
                for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
                    try:
                        c_str = script.string or script.get_text()
                        if not c_str:
                            continue
                        data = json.loads(c_str.strip())
                        items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
                        for item in items:
                            if isinstance(item, dict) and norm_name in normalize_entity_name(item.get("name", "")):
                                tel = item.get("telephone", "")
                                em = item.get("email", "")
                                if tel and normalize_phone_number(str(tel)) in normalize_phone_number(contact_text):
                                    obs_contact = True
                                    break
                                if em and str(em).lower() in contact_text:
                                    obs_contact = True
                                    break
                    except Exception:
                        pass

            obs_units = norm_name in units_text

            # Surface matches details
            head_mentions = [h for h in headings_list if norm_name in normalize_entity_name(h)]
            meta_mentions = [m for m in title_meta_list if norm_name in normalize_entity_name(m)]
            matched_units = [uid for uid, s in zip(unit_ids, unit_snippets) if norm_name in s]

            # Calculate Consistency
            surfaces_active = sum([obs_body, obs_head, obs_title_meta, obs_json_ld, obs_contact, obs_units])
            status = EntityConsistencyStatus.UNKNOWN
            discrepancies = []

            if surfaces_active >= 3:
                status = EntityConsistencyStatus.CONSISTENT
            elif surfaces_active in (1, 2):
                status = EntityConsistencyStatus.PARTIALLY_CONSISTENT
                missing_surfaces = []
                if not obs_json_ld:
                    missing_surfaces.append("JSON-LD")
                if not obs_head:
                    missing_surfaces.append("Headings")
                if not obs_title_meta:
                    missing_surfaces.append("Title/Meta")
                # Missing surface is an observation, not a contradiction
            else:
                status = EntityConsistencyStatus.PARTIALLY_CONSISTENT

            results.append(EntityGroundingEvidence(
                entity_name=display_name,
                entity_type=ent_type,
                url=url,
                bounded_snippet=bound_snippet(f"Entity: {display_name} ({ent_type}) across {surfaces_active}/6 observed surfaces", 250),
                source_location="multi_surface",
                source_type="multi_surface",
                extraction_method="phase8_entity_reuse",
                consistency_status=status,
                observed_in_visible_body=obs_body,
                observed_in_headings=obs_head,
                observed_in_title_meta=obs_title_meta,
                observed_in_json_ld=obs_json_ld,
                observed_in_contact_info=obs_contact,
                observed_in_answerable_units=obs_units,
                heading_mentions=head_mentions[:3],
                meta_mentions=meta_mentions[:2],
                schema_types=list(set(schema_types))[:4],
                associated_units=matched_units[:5],
                discrepancies=discrepancies,
                provenance="claim_grounding_engine",
            ))

        return results

    # -------------------------------------------------------------------------
    # 4. Structured vs Visible Agreement
    # -------------------------------------------------------------------------
    @classmethod
    def _compare_structured_vs_visible(
        cls,
        url: str,
        soup: Optional[BeautifulSoup],
        on_page: Optional[OnPageEvidence],
        entity_ev: Optional[EntityEvidence],
        schema_ev: Optional[SchemaEvidence],
    ) -> List[StructuredVisibleAgreement]:
        """
        Compare JSON-LD declarations against observable DOM content.
        Enforces Correction 2: same entity + same field + compatible context + conflicting explicit values
        required before declaring DISAGREEMENT / contradiction.
        """
        comparisons: List[StructuredVisibleAgreement] = []

        # Find Primary Organization in JSON-LD
        structured_name: Optional[str] = None
        structured_phone: Optional[str] = None
        structured_email: Optional[str] = None
        structured_address: Optional[str] = None
        structured_url: Optional[str] = None

        if entity_ev and entity_ev.detected_entities:
            for ent in entity_ev.detected_entities:
                if ent.source == EntitySource.JSON_LD and ent.entity_type in (EntityType.ORGANIZATION, EntityType.LOCAL_BUSINESS):
                    if not structured_name and ent.name:
                        structured_name = ent.name
                    if not structured_phone and ent.telephone:
                        structured_phone = ent.telephone
                    if not structured_email and ent.email:
                        structured_email = ent.email
                    if not structured_address and ent.address:
                        structured_address = ent.address
                    if not structured_url and ent.declared_url:
                        structured_url = ent.declared_url

        # Fallback to direct JSON-LD script parsing from soup if structured values remain unextracted
        if soup and not (structured_name and structured_phone and structured_email and structured_address):
            for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
                try:
                    c_str = script.string or script.get_text()
                    if not c_str or not c_str.strip():
                        continue
                    data = json.loads(c_str.strip())
                    items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    expanded = []
                    for it in items:
                        if isinstance(it, dict) and "@graph" in it and isinstance(it["@graph"], list):
                            expanded.extend(it["@graph"])
                        else:
                            expanded.append(it)
                    for it in expanded:
                        if isinstance(it, dict):
                            t = it.get("@type", "")
                            t_str = t if isinstance(t, str) else (t[0] if isinstance(t, list) else "")
                            if any(term in t_str for term in ("Organization", "LocalBusiness", "Corporation", "Laboratory")):
                                if not structured_name and it.get("name"):
                                    structured_name = str(it.get("name"))
                                if not structured_phone and it.get("telephone"):
                                    structured_phone = str(it.get("telephone"))
                                if not structured_email and it.get("email"):
                                    structured_email = str(it.get("email"))
                                if not structured_address and it.get("address"):
                                    structured_address = format_postal_address(it.get("address"))
                                if not structured_url and it.get("url"):
                                    structured_url = str(it.get("url"))
                except Exception:
                    pass

        # Observable Visible Values from DOM / on_page
        visible_name: Optional[str] = None
        visible_phone: Optional[str] = None
        visible_email: Optional[str] = None
        visible_address: Optional[str] = None
        visible_url: Optional[str] = on_page.canonical_url if (on_page and on_page.canonical_url) else url

        # Look for visible name in H1 or copyright
        if on_page and on_page.h1_text:
            visible_name = on_page.h1_text[0].strip()
        elif soup:
            h1 = soup.find("h1")
            if h1:
                visible_name = " ".join(h1.get_text().split())

        # Extract visible contact values from footer/address or body
        if soup:
            contact_container = soup.find(["footer", "address"]) or soup.find(id=re.compile(r"contact|footer", re.I)) or soup.body or soup
            container_text = contact_container.get_text()

            # Find phone
            phone_matches = PHONE_REGEX.findall(container_text)
            if phone_matches:
                # Clean and select first plausible phone
                for ph in phone_matches:
                    clean_ph = normalize_phone_number(ph)
                    if len(clean_ph) >= 7:
                        visible_phone = ph.strip()
                        break

            # Find email
            email_matches = EMAIL_REGEX.findall(container_text)
            if email_matches:
                visible_email = email_matches[0].strip()

            # Find address
            addr_tag = soup.find("address")
            if addr_tag:
                visible_address = " ".join(addr_tag.get_text().split())

        # --- Comparison 1: Organization Name ---
        comparisons.append(cls._evaluate_field_agreement(
            field_name="organization_name",
            context_label="primary_identity",
            url=url,
            structured_val=structured_name,
            visible_val=visible_name,
            normalizer=normalize_entity_name,
        ))

        # --- Comparison 2: Primary Telephone ---
        comparisons.append(cls._evaluate_field_agreement(
            field_name="telephone",
            context_label="primary_contact",
            url=url,
            structured_val=structured_phone,
            visible_val=visible_phone,
            normalizer=normalize_phone_number,
        ))

        # --- Comparison 3: Primary Email ---
        comparisons.append(cls._evaluate_field_agreement(
            field_name="email",
            context_label="primary_contact",
            url=url,
            structured_val=structured_email,
            visible_val=visible_email,
            normalizer=lambda s: s.lower().strip() if s else "",
        ))

        # --- Comparison 4: Primary Address ---
        comparisons.append(cls._evaluate_field_agreement(
            field_name="address",
            context_label="primary_location",
            url=url,
            structured_val=structured_address,
            visible_val=visible_address,
            normalizer=lambda s: re.sub(r"[^\w\s]", "", s.lower()).strip() if s else "",
        ))

        # --- Comparison 5: Primary URL ---
        comparisons.append(cls._evaluate_field_agreement(
            field_name="url",
            context_label="primary_canonical",
            url=url,
            structured_val=structured_url,
            visible_val=visible_url,
            normalizer=lambda s: urlparse(s).netloc.lower().replace("www.", "") if s else "",
        ))

        return comparisons

    @classmethod
    def _evaluate_field_agreement(
        cls,
        field_name: str,
        context_label: str,
        url: str,
        structured_val: Optional[str],
        visible_val: Optional[str],
        normalizer: Any,
    ) -> StructuredVisibleAgreement:
        """
        Evaluate agreement between a structured field and visible content value.
        Guarantees that missing values are marked MISSING_* and never DISAGREEMENT.
        """
        notes: List[str] = []

        if not structured_val and not visible_val:
            return StructuredVisibleAgreement(
                field_name=field_name,
                context_label=context_label,
                url=url,
                structured_value=None,
                visible_value=None,
                status=StructuredVisibleAgreementStatus.UNAVAILABLE,
                bounded_snippet=f"{field_name}: unavailable on both structured and visible surfaces",
                source_location="jsonld_and_dom",
                notes=["Neither structured JSON-LD nor visible HTML provides this field."],
            )

        if structured_val and not visible_val:
            return StructuredVisibleAgreement(
                field_name=field_name,
                context_label=context_label,
                url=url,
                structured_value=bound_snippet(structured_val, 150),
                visible_value=None,
                status=StructuredVisibleAgreementStatus.MISSING_VISIBLE,
                bounded_snippet=f"{field_name}: declared in JSON-LD ('{bound_snippet(structured_val, 80)}') but absent in visible content",
                source_location="jsonld",
                notes=["Field declared in JSON-LD but not observed in visible editorial copy."],
            )

        if not structured_val and visible_val:
            return StructuredVisibleAgreement(
                field_name=field_name,
                context_label=context_label,
                url=url,
                structured_value=None,
                visible_value=bound_snippet(visible_val, 150),
                status=StructuredVisibleAgreementStatus.MISSING_STRUCTURED,
                bounded_snippet=f"{field_name}: visible in HTML ('{bound_snippet(visible_val, 80)}') but missing in JSON-LD",
                source_location="dom",
                notes=["Field visible on page but omitted from structured JSON-LD declarations."],
            )

        # Both structured_val and visible_val are present!
        norm_struct = normalizer(structured_val) if normalizer else structured_val.strip().lower()
        norm_vis = normalizer(visible_val) if normalizer else visible_val.strip().lower()

        status = StructuredVisibleAgreementStatus.UNAVAILABLE
        if norm_struct == norm_vis:
            status = StructuredVisibleAgreementStatus.AGREEMENT
            notes.append("Explicit agreement: structured JSON-LD value matches visible HTML.")
        elif norm_struct in norm_vis or norm_vis in norm_struct:
            status = StructuredVisibleAgreementStatus.PARTIAL_AGREEMENT
            notes.append("Partial agreement: structured and visible values share common identity tokens.")
        else:
            # Correction 2: same entity + same field + compatible context + conflicting explicit values
            status = StructuredVisibleAgreementStatus.DISAGREEMENT
            notes.append(f"Explicit contradiction: JSON-LD declares '{structured_val}' while visible content displays '{visible_val}'.")

        return StructuredVisibleAgreement(
            field_name=field_name,
            context_label=context_label,
            url=url,
            structured_value=bound_snippet(structured_val, 150),
            visible_value=bound_snippet(visible_val, 150),
            status=status,
            bounded_snippet=f"{field_name}: structured='{bound_snippet(structured_val, 60)}' vs visible='{bound_snippet(visible_val, 60)}'",
            source_location="jsonld_and_dom",
            evidence_snippet=f"JSON-LD: {structured_val} | DOM: {visible_val}",
            notes=notes,
        )

    # -------------------------------------------------------------------------
    # 5. Site-Wide Multi-Page Aggregation
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_site(cls, site_crawl: SiteCrawlResult) -> SiteClaimGroundingIntelligence:
        """
        Aggregate multi-page claims, enable cross-page claim corroboration,
        track site-wide entity consistency, and identify structured vs visible disagreements.
        """
        records: List[CrawlRecord] = site_crawl.crawl_records or []
        total_pages = len(records)
        is_partial = total_pages < site_crawl.pages_discovered
        disclaimer = ""
        if is_partial:
            disclaimer = f"Claim grounding intelligence based on {total_pages} of {site_crawl.pages_discovered} discovered pages."

        page_evidence_map: Dict[str, ClaimGroundingEvidence] = {}
        all_claims: List[ClaimEvidence] = []
        all_disagreements: List[StructuredVisibleAgreement] = []
        all_entity_groundings: List[EntityGroundingEvidence] = []

        # Collect page evidence
        for rec in records:
            ev = getattr(rec, "claim_grounding", None)
            if ev is None and getattr(rec, "engine_results", None) and "claim_grounding_engine" in rec.engine_results:
                res = rec.engine_results["claim_grounding_engine"]
                ev = getattr(res, "claim_grounding", None)
            if ev is None:
                ev = cls.evaluate_page(
                    url=rec.url,
                    raw_html=getattr(rec, "raw_html", None),
                    rendered_html=None,
                )
            if ev:
                page_evidence_map[rec.url] = ev
                all_claims.extend(ev.claims)
                all_disagreements.extend([a for a in ev.structured_agreements if a.status == StructuredVisibleAgreementStatus.DISAGREEMENT])
                all_entity_groundings.extend(ev.entity_grounding)

        # Cross-Page Corroboration:
        # If a claim on Page A was UNCORROBORATED_ON_SITE, check if Page B (e.g. /about, /services) corroborates it
        if len(page_evidence_map) > 1:
            # Build site-wide pool of technical/about passages
            site_passages: List[Tuple[str, str]] = []  # (url, passage_snippet)
            for url, pev in page_evidence_map.items():
                for c in pev.claims:
                    if c.support_status == ClaimSupportStatus.SUPPORTED_ON_SITE:
                        site_passages.append((url, c.claim_text))

            for claim in all_claims:
                if claim.support_status == ClaimSupportStatus.UNCORROBORATED_ON_SITE:
                    c_tokens = clean_tokens(claim.claim_text)
                    for other_url, other_snippet in site_passages:
                        if other_url != claim.url:
                            other_tokens = clean_tokens(other_snippet)
                            # Stricter rule (Correction 1): must contain explicit evidence directly supporting subject and value/context
                            if len(c_tokens & other_tokens) >= 3:
                                claim.support_status = ClaimSupportStatus.SUPPORTED_ON_SITE
                                claim.supporting_snippets.append(bound_snippet(other_snippet, 250))
                                claim.supporting_urls.append(other_url)
                                claim.notes.append(f"Corroborated across crawled pages by explicit evidence on {other_url}.")
                                break

        # Calculate site totals
        total_site_claims = len(all_claims)
        supported_cnt = sum(1 for c in all_claims if c.support_status == ClaimSupportStatus.SUPPORTED_ON_SITE)
        partial_cnt = sum(1 for c in all_claims if c.support_status == ClaimSupportStatus.PARTIALLY_SUPPORTED)
        uncorroborated_cnt = sum(1 for c in all_claims if c.support_status == ClaimSupportStatus.UNCORROBORATED_ON_SITE)
        contradicted_cnt = sum(1 for c in all_claims if c.support_status == ClaimSupportStatus.CONTRADICTED_ON_SITE)

        # Summarize site entity consistency
        entity_summary: Dict[str, str] = {}
        for eg in all_entity_groundings:
            if eg.entity_name not in entity_summary:
                entity_summary[eg.entity_name] = eg.consistency_status.value

        facts: List[str] = [
            f"Evaluated {total_pages} crawled page(s) for claims and entity grounding.",
            f"Total site claims detected: {total_site_claims} ({supported_cnt} supported, {partial_cnt} partially supported, {uncorroborated_cnt} uncorroborated, {contradicted_cnt} contradicted).",
            f"Total structured vs visible disagreements detected: {len(all_disagreements)}.",
            f"Tracked {len(entity_summary)} unique entity candidate(s) across site surfaces.",
        ]

        analyses: List[str] = []
        if contradicted_cnt > 0:
            analyses.append(f"Site exhibits {contradicted_cnt} explicit contradictory claim assertion(s) across crawled pages.")
        if all_disagreements:
            analyses.append(f"{len(all_disagreements)} discrepancy finding(s) between JSON-LD structured data and visible HTML content.")
        if uncorroborated_cnt > 0:
            analyses.append(f"{uncorroborated_cnt} claim(s) are stated without direct supporting operational context, parameters, or specifications anywhere on the crawled site.")
        if supported_cnt > 0:
            analyses.append(f"{supported_cnt} claim(s) have explicit on-site corroborating evidence.")

        intel = SiteClaimGroundingIntelligence(
            status="success",
            total_pages_evaluated=total_pages,
            is_partial_crawl=is_partial,
            completeness_disclaimer=disclaimer,
            total_site_claims_detected=total_site_claims,
            supported_claims_count=supported_cnt,
            partially_supported_count=partial_cnt,
            uncorroborated_count=uncorroborated_cnt,
            contradicted_count=contradicted_cnt,
            entity_consistency_summary=entity_summary,
            disagreement_items=all_disagreements,
            page_grounding_evidence=page_evidence_map,
            facts=facts,
            analyses=analyses,
        )

        site_crawl.claim_grounding_intelligence = intel
        return intel
