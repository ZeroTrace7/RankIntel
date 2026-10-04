"""
External Visibility Intelligence Engine (Phase 10.5).
Executes controlled, evidence-driven external AI/search queries against benchmark targets,
preserves exact observations, classifies citations and mentions, and connects evidence
to on-site M8/M9/M10 artifacts without claiming universal AI rankings.
"""
from __future__ import annotations
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from rankintel.models.schema import (
    ExternalVisibilityProvider,
    ExternalVisibilityProviderType,
    ExternalVisibilityStatus,
    CitationRelationship,
    CitationContentMatchStatus,
    QueryInformationNeedCategory,
    ControlledVisibilityQuery,
    ExternalCitationObservation,
    ExternalMentionObservation,
    ExternalAnswerEvidence,
    ExternalAIObservation,
    ExternalVisibilityEvidence,
    SiteExternalVisibilityIntelligence,
    SiteCrawlResult,
    OnPageEvidence,
    EntityEvidence,
    PageTopicIntelligence,
    AnswerabilityEvidence,
    ClaimGroundingEvidence,
)
from rankintel.providers.base import BaseExternalVisibilityAdapter
from rankintel.providers.registry import ProviderRegistry


class ControlledQueryGenerator:
    """
    Deterministically generates up to 10 controlled visibility queries derived from
    on-site Phase 8 entities, Phase 9 topics, M10.2 answerable units, and M10.3 claims.
    Enforces per-site budget limits and deduplication.
    """

    @classmethod
    def generate_queries(
        cls,
        target_url: str,
        domain: str,
        entity_evidence: Optional[EntityEvidence] = None,
        topic_evidence: Optional[PageTopicIntelligence] = None,
        answerability_evidence: Optional[AnswerabilityEvidence] = None,
        claim_evidence: Optional[ClaimGroundingEvidence] = None,
        max_queries: int = 10,
        trials_count: int = 1,
    ) -> List[ControlledVisibilityQuery]:
        """
        Constructs deterministic queries across the 10 observable information-need categories.
        """
        clean_domain = cls._clean_domain(domain or target_url)
        root_name = clean_domain.split(".")[0].title() if clean_domain else "Company"

        # 1. Extract candidate entity name
        entity_name = root_name
        if entity_evidence and entity_evidence.detected_entities:
            orgs = [e for e in entity_evidence.detected_entities if e.entity_type.value == "ORGANIZATION"]
            if orgs:
                entity_name = orgs[0].name
            else:
                entity_name = entity_evidence.detected_entities[0].name

        # 2. Extract Phase 9 candidate topics
        topics: List[str] = []
        if topic_evidence and topic_evidence.topics:
            topics = [t.topic_name for t in topic_evidence.topics[:5]]
        primary_topic = topics[0] if topics else "testing and certification services"
        secondary_topic = topics[1] if len(topics) > 1 else primary_topic

        # 3. Extract M10.2 candidate answerable units
        service_unit = None
        procedure_unit = None
        requirement_unit = None
        if answerability_evidence and answerability_evidence.units:
            for u in answerability_evidence.units:
                if u.unit_type.value == "SERVICE_DESCRIPTION" and not service_unit:
                    service_unit = u
                elif u.unit_type.value == "PROCEDURE_STEPS" and not procedure_unit:
                    procedure_unit = u
                elif u.unit_type.value in ("REQUIREMENTS_ELIGIBILITY", "SPECIFICATION") and not requirement_unit:
                    requirement_unit = u

        # 4. Extract M10.3 candidate claim
        claim_item = None
        if claim_evidence and claim_evidence.claims:
            claim_item = claim_evidence.claims[0]

        # 5. Deterministic query templates across 10 categories
        candidates: List[Tuple[QueryInformationNeedCategory, str, Dict[str, Any]]] = [
            (
                QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
                f"Who is {entity_name} and what services do they provide?",
                {"entity": entity_name},
            ),
            (
                QueryInformationNeedCategory.SERVICE_DISCOVERY,
                f"What services and capabilities are offered by {entity_name}?",
                {"entity": entity_name, "topic": primary_topic},
            ),
            (
                QueryInformationNeedCategory.SERVICE_EXPLANATION,
                f"How does {entity_name} provide {primary_topic}?",
                {"entity": entity_name, "topic": primary_topic, "unit_id": service_unit.unit_id if service_unit else None},
            ),
            (
                QueryInformationNeedCategory.CERTIFICATION_STANDARD,
                f"What certifications, standards, or compliance marks are handled by {entity_name}?",
                {"entity": entity_name},
            ),
            (
                QueryInformationNeedCategory.LOCATION_CONTACT,
                f"Where is {entity_name} located and how can they be contacted?",
                {"entity": entity_name},
            ),
            (
                QueryInformationNeedCategory.PROCEDURE_HOWTO,
                f"What is the process or procedure for {procedure_unit.section_heading if procedure_unit and procedure_unit.section_heading else primary_topic} at {entity_name}?",
                {"entity": entity_name, "topic": primary_topic, "unit_id": procedure_unit.unit_id if procedure_unit else None},
            ),
            (
                QueryInformationNeedCategory.REQUIREMENT_ELIGIBILITY,
                f"What are the requirements or documentation needed for {requirement_unit.section_heading if requirement_unit and requirement_unit.section_heading else secondary_topic} through {entity_name}?",
                {"entity": entity_name, "topic": secondary_topic, "unit_id": requirement_unit.unit_id if requirement_unit else None},
            ),
            (
                QueryInformationNeedCategory.COMPARISON_DECISION,
                f"Why choose {entity_name} for {primary_topic}?",
                {"entity": entity_name, "topic": primary_topic},
            ),
            (
                QueryInformationNeedCategory.TOPIC_SPECIFIC_PHASE9,
                f"What information is available about {secondary_topic} from {clean_domain}?",
                {"domain": clean_domain, "topic": secondary_topic},
            ),
            (
                QueryInformationNeedCategory.CLAIM_SPECIFIC_M10_3,
                cls._format_claim_query(entity_name, claim_item),
                {"entity": entity_name, "claim_id": claim_item.claim_id if claim_item else None},
            ),
        ]

        # Enforce budget limit and deduplication
        selected_candidates = candidates[:max_queries]
        queries: List[ControlledVisibilityQuery] = []
        seen_texts = set()

        for idx, (cat, text, meta) in enumerate(selected_candidates, start=1):
            clean_text = text.strip()
            if clean_text in seen_texts:
                continue
            seen_texts.add(clean_text)

            for trial in range(1, trials_count + 1):
                queries.append(ControlledVisibilityQuery(
                    query_id=f"q-{idx:02d}-{cat.value}",
                    query_text=clean_text,
                    category=cat,
                    target_domain=clean_domain,
                    target_url=target_url,
                    derived_from_entity=meta.get("entity"),
                    derived_from_topic=meta.get("topic"),
                    derived_from_unit_id=meta.get("unit_id"),
                    derived_from_claim_id=meta.get("claim_id"),
                    trial_index=trial,
                ))

        return queries

    @classmethod
    def _format_claim_query(cls, entity_name: str, claim_item: Optional[Any]) -> str:
        if not claim_item:
            return f"Does {entity_name} provide certified laboratory testing reports?"
        clm_text = claim_item.claim_text.strip()
        if len(clm_text) > 80:
            clm_text = clm_text[:77] + "..."
        return f"Does {entity_name} state: '{clm_text}'?"

    @staticmethod
    def _clean_domain(domain: str) -> str:
        d = domain.strip().lower()
        if d.startswith("http://") or d.startswith("https://"):
            d = urlparse(d).netloc
        if d.startswith("www."):
            d = d[4:]
        return d.split(":")[0]


class ExternalCitationAnalyzer:
    """
    Evaluates citation relationships and performs conservative content comparison
    against crawled evidence. Never flags MISMATCH unless crawled evidence materially
    conflicts with the cited claim.
    """

    @classmethod
    def analyze_citation_content(
        cls,
        citation: ExternalCitationObservation,
        crawled_pages_evidence: Dict[str, Any],
    ) -> CitationContentMatchStatus:
        """
        Determines observable content agreement between citation snippet and crawled page.
        """
        if not citation.is_target_domain:
            return CitationContentMatchStatus.UNABLE_TO_DETERMINE

        # If we have no snippet to compare, we cannot determine match
        if not citation.snippet or len(citation.snippet.strip()) < 10:
            return CitationContentMatchStatus.UNABLE_TO_DETERMINE

        c_url_norm = cls._normalize_url(citation.citation_url)
        page_ev = crawled_pages_evidence.get(c_url_norm)

        if not page_ev:
            # Page was not crawled or evidence not available
            return CitationContentMatchStatus.UNABLE_TO_DETERMINE

        page_text = (getattr(page_ev, "page_text", "") or getattr(page_ev, "title", "")).lower()
        snippet_lower = citation.snippet.lower()

        # Token overlap heuristic
        snip_words = set(re.findall(r"\b\w{4,}\b", snippet_lower))
        if not snip_words:
            return CitationContentMatchStatus.UNABLE_TO_DETERMINE

        page_words = set(re.findall(r"\b\w{4,}\b", page_text))
        overlap = len(snip_words.intersection(page_words)) / len(snip_words)

        # Check for explicit material contradiction (e.g., negative words clashing)
        contradiction_pairs = [
            ("expired", "active"),
            ("not certified", "certified"),
            ("closed", "open"),
            ("prohibited", "permitted"),
            ("cancelled", "valid"),
        ]
        has_contradiction = False
        for neg, pos in contradiction_pairs:
            if (neg in snippet_lower and pos in page_text) or (pos in snippet_lower and neg in page_text):
                has_contradiction = True
                break

        if has_contradiction:
            return CitationContentMatchStatus.MISMATCH

        if overlap >= 0.65:
            return CitationContentMatchStatus.MATCHES_PAGE_EVIDENCE
        elif overlap >= 0.25:
            return CitationContentMatchStatus.PARTIALLY_MATCHES
        else:
            # Absence of exact words does NOT equal mismatch (per user guidance!)
            return CitationContentMatchStatus.UNABLE_TO_DETERMINE

    @staticmethod
    def _normalize_url(url: str) -> str:
        p = urlparse(url.strip())
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = p.path.rstrip("/")
        return f"{p.scheme}://{netloc}{path}"


class ExternalVisibilityEngine:
    """
    Coordinates controlled query generation, provider execution, repeated trials,
    citation/mention analysis, and evidence linkage.
    """

    def __init__(
        self,
        enable_external_visibility: bool = False,
        providers: Optional[List[str]] = None,
        max_queries_per_site: int = 10,
        trials_per_query: int = 1,
    ):
        self.enabled = enable_external_visibility or (os.getenv("RANKINTEL_ENABLE_EXTERNAL_VISIBILITY", "").lower() in ("1", "true", "yes"))
        self.provider_names = providers
        self.max_queries_per_site = max_queries_per_site
        self.trials_per_query = trials_per_query

    def evaluate_page(
        self,
        url: str,
        on_page: Optional[OnPageEvidence] = None,
        entity_evidence: Optional[EntityEvidence] = None,
        topic_evidence: Optional[PageTopicIntelligence] = None,
        answerability_evidence: Optional[AnswerabilityEvidence] = None,
        claim_evidence: Optional[ClaimGroundingEvidence] = None,
    ) -> ExternalVisibilityEvidence:
        """
        Evaluates controlled external visibility for a single page or URL.
        Guarded: returns DISABLED / UNAVAILABLE immediately when opt-in is false.
        """
        domain = urlparse(url).netloc.replace("www.", "")

        if not self.enabled:
            return ExternalVisibilityEvidence(
                url=url,
                domain=domain,
                status=ExternalVisibilityStatus.DISABLED,
                limitations_and_disclaimers=[
                    "Controlled external AI visibility is disabled by default. Pass --external-ai to opt in."
                ],
                facts=["External AI visibility measurement not requested for this audit."],
            )

        # Obtain adapters
        adapters = ProviderRegistry.get_configured_adapters(self.provider_names)
        if not adapters:
            return ExternalVisibilityEvidence(
                url=url,
                domain=domain,
                status=ExternalVisibilityStatus.UNAVAILABLE,
                limitations_and_disclaimers=["No external visibility providers configured."],
                facts=["No provider adapter available to execute queries."],
            )

        # Generate deterministic query set
        queries = ControlledQueryGenerator.generate_queries(
            target_url=url,
            domain=domain,
            entity_evidence=entity_evidence,
            topic_evidence=topic_evidence,
            answerability_evidence=answerability_evidence,
            claim_evidence=claim_evidence,
            max_queries=self.max_queries_per_site,
            trials_count=self.trials_per_query,
        )

        observations: List[ExternalAIObservation] = []
        providers_evaluated: List[str] = []

        # Execute queries across adapters
        for adapter in adapters:
            providers_evaluated.append(adapter.provider.value)
            for query in queries:
                obs = adapter.execute_query(query)
                # Content comparison for citations
                for c in obs.citations:
                    c.content_match_status = ExternalCitationAnalyzer.analyze_citation_content(
                        c,
                        crawled_pages_evidence={cls_url_norm(url): on_page} if on_page else {},
                    )
                observations.append(obs)

        # Aggregate observation counts
        successful_cnt = sum(1 for o in observations if o.status == ExternalVisibilityStatus.SUCCESS)
        unavailable_cnt = sum(1 for o in observations if o.status == ExternalVisibilityStatus.UNAVAILABLE)
        failed_cnt = sum(1 for o in observations if o.status in (ExternalVisibilityStatus.ERROR, ExternalVisibilityStatus.TIMEOUT, ExternalVisibilityStatus.RATE_LIMITED))
        mention_cnt = sum(1 for o in observations if o.mention_observation and o.mention_observation.target_mentioned)
        domain_cited_cnt = sum(1 for o in observations if o.target_domain_cited)
        page_cited_cnt = sum(1 for o in observations if o.target_page_cited)
        total_cit_cnt = sum(len(o.citations) for o in observations)

        # Evidence linkages
        linkages = self._build_evidence_linkages(queries, observations)

        # Build factual findings
        facts: List[str] = [
            f"Executed {len(queries)} controlled queries across {len(adapters)} provider(s) ({successful_cnt} completed, {unavailable_cnt} unavailable, {failed_cnt} failed).",
            f"Target domain mentioned in {mention_cnt}/{len(observations)} answer observations.",
            f"Target domain cited in {domain_cited_cnt}/{len(observations)} observations ({page_cited_cnt} cited exact target URL).",
        ]

        analyses: List[str] = [
            "Observations reflect empirical responses under specified configurations and do not imply universal AI search rankings or consumer product behavior.",
            "Absence of target citation is preserved as an empirical observation without penalty to on-site health scores.",
        ]

        disclaimers: List[str] = [
            "External observations represent specific system outputs at execution timestamp and do not constitute universal AI visibility.",
            "Model parameters, grounding queries, and citation indexing operate independently of on-site technical scores.",
        ]

        overall_status = ExternalVisibilityStatus.SUCCESS if successful_cnt > 0 else (
            ExternalVisibilityStatus.UNAVAILABLE if unavailable_cnt == len(observations) else ExternalVisibilityStatus.ERROR
        )

        return ExternalVisibilityEvidence(
            url=url,
            domain=domain,
            status=overall_status,
            providers_evaluated=providers_evaluated,
            queries_executed_count=len(queries),
            successful_observations_count=successful_cnt,
            unavailable_observations_count=unavailable_cnt,
            failed_observations_count=failed_cnt,
            target_domain_mention_count=mention_cnt,
            target_domain_cited_count=domain_cited_cnt,
            target_page_cited_count=page_cited_cnt,
            total_external_citations_returned=total_cit_cnt,
            observations=observations,
            queries=queries,
            evidence_linkages=linkages,
            limitations_and_disclaimers=disclaimers,
            facts=facts,
            analyses=analyses,
        )

    @classmethod
    def evaluate_site(
        cls,
        site_crawl: SiteCrawlResult,
        config: Optional[Any] = None,
    ) -> None:
        """
        Site-level external visibility evaluation.
        Attaches SiteExternalVisibilityIntelligence to site_crawl.external_visibility_intelligence.
        """
        # Determine if enabled from config or env
        enabled = False
        if config and getattr(config, "enable_external_visibility", False):
            enabled = True
        elif os.getenv("RANKINTEL_ENABLE_EXTERNAL_VISIBILITY", "").lower() in ("1", "true", "yes"):
            enabled = True

        root_url = site_crawl.pages[0].url if site_crawl.pages else "https://example.com"
        clean_domain = urlparse(root_url).netloc.replace("www.", "")

        if not enabled:
            site_crawl.external_visibility_intelligence = SiteExternalVisibilityIntelligence(
                status="disabled",
                limitations_and_disclaimers=[
                    "External AI visibility measurement is disabled by default. Pass --external-ai to opt in."
                ],
                facts=["External AI visibility measurement not requested for this site crawl."],
            )
            return

        # Prepare site-wide evidence sources
        entity_ev = getattr(site_crawl, "entity_intelligence", None)
        topic_ev = getattr(site_crawl, "topic_intelligence", None)
        answerability_ev = getattr(site_crawl, "answerability_intelligence", None)
        providers = getattr(config, "external_visibility_providers", None)
        engine = cls(enable_external_visibility=True, providers=providers)
        # Build query set
        queries = ControlledQueryGenerator.generate_queries(
            target_url=root_url,
            domain=clean_domain,
            entity_evidence=None, # EntityEvidence adapter
            max_queries=engine.max_queries_per_site,
            trials_count=engine.trials_per_query,
        )

        adapters = ProviderRegistry.get_configured_adapters(engine.provider_names)
        observations: List[ExternalAIObservation] = []
        providers_tested: List[str] = [a.provider.value for a in adapters]

        for adapter in adapters:
            for q in queries:
                obs = adapter.execute_query(q)
                observations.append(obs)

        completed = sum(1 for o in observations if o.status == ExternalVisibilityStatus.SUCCESS)
        unavail = sum(1 for o in observations if o.status == ExternalVisibilityStatus.UNAVAILABLE)
        mentions = sum(1 for o in observations if o.mention_observation and o.mention_observation.target_mentioned)
        citations_cnt = sum(1 for o in observations if o.target_domain_cited)

        # Repeated trial consistency
        trial_consistency = cls._calculate_trial_consistency(observations)

        linkages = engine._build_evidence_linkages(queries, observations)

        site_crawl.external_visibility_intelligence = SiteExternalVisibilityIntelligence(
            status="success" if completed > 0 else ("unavailable" if unavail == len(observations) else "partial"),
            total_queries_planned=len(queries),
            total_observations_completed=completed,
            total_observations_unavailable=unavail,
            total_target_domain_mentions=mentions,
            total_target_citations=citations_cnt,
            citation_consistency_observations=trial_consistency,
            providers_tested=providers_tested,
            observations=observations,
            evidence_linkages=linkages,
            limitations_and_disclaimers=[
                "External observations reflect empirical responses from configured external providers at the execution timestamp.",
                "Observations do not measure universal search rankings or consumer product behavior.",
            ],
            facts=[
                f"Planned {len(queries)} controlled queries across {len(adapters)} provider(s) ({completed} completed, {unavail} unavailable).",
                f"Target domain mentioned in {mentions} observations, cited in {citations_cnt} observations.",
            ],
            analyses=[
                "External visibility evidence is preserved strictly as empirical observations without altering on-site health scores.",
            ],
        )

    def _build_evidence_linkages(
        self,
        queries: List[ControlledVisibilityQuery],
        observations: List[ExternalAIObservation],
    ) -> List[Dict[str, Any]]:
        """
        Builds the explicit evidence chain:
        Topic/Entity -> Unit -> Claim -> Query -> Observation -> Citation
        """
        linkages: List[Dict[str, Any]] = []
        for q in queries:
            obs_for_q = [o for o in observations if o.query.query_id == q.query_id]
            if not obs_for_q:
                continue
            first_obs = obs_for_q[0]
            linkages.append({
                "query_id": q.query_id,
                "category": q.category.value,
                "query_text": q.query_text,
                "derived_from_entity": q.derived_from_entity,
                "derived_from_topic": q.derived_from_topic,
                "derived_from_unit_id": q.derived_from_unit_id,
                "derived_from_claim_id": q.derived_from_claim_id,
                "target_domain_cited": any(o.target_domain_cited for o in obs_for_q),
                "target_mentioned": any(o.mention_observation and o.mention_observation.target_mentioned for o in obs_for_q),
                "citations_count": sum(len(o.citations) for o in obs_for_q),
                "sample_citation_urls": [c.citation_url for o in obs_for_q for c in o.citations if c.is_target_domain][:3],
            })
        return linkages

    @staticmethod
    def _calculate_trial_consistency(observations: List[ExternalAIObservation]) -> Dict[str, Any]:
        """Calculates consistency metrics across repeated trials for the same query."""
        by_query: Dict[str, List[ExternalAIObservation]] = {}
        for o in observations:
            by_query.setdefault(o.query.query_id, []).append(o)

        multi_trial_queries = {qid: obs for qid, obs in by_query.items() if len(obs) > 1}
        if not multi_trial_queries:
            return {"repeated_trials_evaluated": False, "note": "Single trial per query executed."}

        consistent_citations = 0
        consistent_mentions = 0
        for qid, obs_list in multi_trial_queries.items():
            all_cited = all(o.target_domain_cited for o in obs_list)
            none_cited = all(not o.target_domain_cited for o in obs_list)
            if all_cited or none_cited:
                consistent_citations += 1

            all_mentioned = all(o.mention_observation and o.mention_observation.target_mentioned for o in obs_list)
            none_mentioned = all(not (o.mention_observation and o.mention_observation.target_mentioned) for o in obs_list)
            if all_mentioned or none_mentioned:
                consistent_mentions += 1

        total_multi = len(multi_trial_queries)
        return {
            "repeated_trials_evaluated": True,
            "total_queries_with_multi_trials": total_multi,
            "citation_consistency_ratio": round(consistent_citations / total_multi, 2),
            "mention_consistency_ratio": round(consistent_mentions / total_multi, 2),
        }


def cls_url_norm(url: str) -> str:
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = p.path.rstrip("/")
    return f"{p.scheme}://{netloc}{path}"
