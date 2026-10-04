"""
Phase 11.2 — Website-Level Intelligence Reviewer.
Transforms normalized benchmark evidence packages into coherent, human-readable
website intelligence profiles across 18 synthesized dimensions.
Strictly offline, deterministic, zero-network, and formula-invariant.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from rankintel.benchmark.models import (
    BenchmarkDimensionStatus,
    ReviewDimensionStatus,
    ObservableBusinessProfile,
    EntityProfile,
    ServiceProductProfile,
    TopicTaxonomyProfile,
    SearchIntentProfile,
    TopicDistributionProfile,
    PageTopicConcentrationProfile,
    TechnicalSeoReviewProfile,
    AccessibilitySecurityProfile,
    InternalLinkStructureProfile,
    RetrievalReadinessProfile,
    AnswerabilityReviewProfile,
    ClaimGroundingReviewProfile,
    MultimodalReviewProfile,
    AgentReadinessReviewProfile,
    ExternalAiReviewProfile,
    EvidenceLimitationsProfile,
    WebsiteIntelligenceReview,
    BenchmarkReviewDataset,
    SiteIntelligencePackage,
)

logger = logging.getLogger(__name__)


def _clean_domain(url_or_dom: str) -> str:
    """Normalize URL or domain string to a clean domain key."""
    if "://" not in url_or_dom:
        url_or_dom = "https://" + url_or_dom
    parsed = urlparse(url_or_dom)
    return parsed.netloc.lower().replace("www.", "").replace(":", "_").rstrip("/")


class WebsiteIntelligenceReviewer:
    """
    Deterministically transforms a SiteIntelligencePackage into a structured,
    provenance-preserving WebsiteIntelligenceReview spanning 18 dimensions.
    """

    @staticmethod
    def synthesize_review(pkg: SiteIntelligencePackage) -> WebsiteIntelligenceReview:
        """
        Synthesize a structured website intelligence profile from normalized benchmark evidence.
        Strictly deterministic, zero network calls.
        """
        review_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Observable business/company understanding
        biz_profile = WebsiteIntelligenceReviewer._synthesize_business_profile(pkg)

        # 2. Entities and entity types
        entity_profile = WebsiteIntelligenceReviewer._synthesize_entity_profile(pkg)

        # 3. Observable services/products
        service_profile = WebsiteIntelligenceReviewer._synthesize_service_profile(pkg)

        # 4. Primary and supporting topics
        topic_taxonomy = WebsiteIntelligenceReviewer._synthesize_topic_taxonomy(pkg)

        # 5. Dominant concepts
        dominant_concepts = topic_taxonomy.dominant_concepts

        # 6. Observable search intents
        search_intent = WebsiteIntelligenceReviewer._synthesize_search_intent(pkg)

        # 7. Topic-to-page distribution
        topic_dist = WebsiteIntelligenceReviewer._synthesize_topic_distribution(pkg)

        # 8. Page/topic concentration and overlap
        concentration = WebsiteIntelligenceReviewer._synthesize_concentration(pkg)

        # 9. Technical SEO condition
        tech_seo = WebsiteIntelligenceReviewer._synthesize_technical_seo(pkg)

        # 10. Accessibility and security signals
        a11y_sec = WebsiteIntelligenceReviewer._synthesize_a11y_security(pkg)

        # 11. Internal-link structure
        internal_links = WebsiteIntelligenceReviewer._synthesize_internal_links(pkg)

        # 12. GEO/AI retrieval readiness
        retrieval = WebsiteIntelligenceReviewer._synthesize_retrieval_readiness(pkg)

        # 13. Answerability structures
        answerability = WebsiteIntelligenceReviewer._synthesize_answerability(pkg)

        # 14. Claim/entity grounding
        claim_grounding = WebsiteIntelligenceReviewer._synthesize_claim_grounding(pkg)

        # 15. Multimodal readiness
        multimodal = WebsiteIntelligenceReviewer._synthesize_multimodal(pkg)

        # 16. Agent/action-surface readiness
        agent_readiness = WebsiteIntelligenceReviewer._synthesize_agent_readiness(pkg)

        # 17. External AI observations
        external_ai = WebsiteIntelligenceReviewer._synthesize_external_ai(pkg)

        # 18. Evidence limitations and uncertainty
        limitations = WebsiteIntelligenceReviewer._synthesize_limitations(pkg)

        raw_summary = {
            "status_code": pkg.crawl_discovery.http_status_code,
            "word_count": pkg.content.main_content_words,
            "title_length": pkg.technical_seo.title_length,
            "entities_count": pkg.entity.total_entities_detected,
            "topics_count": pkg.search_topic_query_intent.topics_detected_count,
            "units_count": pkg.answerability.total_units_detected,
            "claims_count": pkg.claim_grounding.total_claims_detected,
            "visual_assets": pkg.multimodal.total_visual_assets,
            "waf_detected": pkg.retrieval_readiness.waf_or_challenge_detected,
            "wcag_status": pkg.accessibility.wcag_status,
            "security_status": pkg.security.overall_status,
        }

        return WebsiteIntelligenceReview(
            domain=pkg.domain,
            site_url=pkg.site_url,
            name=pkg.name or biz_profile.business_name or pkg.domain,
            role=pkg.role,
            collection_timestamp=pkg.collection_timestamp,
            review_timestamp=review_ts,
            overall_health_score=pkg.overall_health_score,
            technical_health_score=pkg.technical_health_score,
            geo_readiness_score=pkg.geo_readiness_score,
            trust_score=pkg.trust_score,
            performance_score=pkg.performance_score,
            score_formula_mode=pkg.score_formula_mode,
            formula_invariance_verified=pkg.formula_invariance_verified,
            business_profile=biz_profile,
            entity_profile=entity_profile,
            service_profile=service_profile,
            topic_taxonomy=topic_taxonomy,
            dominant_concepts=dominant_concepts,
            search_intent=search_intent,
            topic_distribution=topic_dist,
            concentration_and_overlap=concentration,
            technical_seo=tech_seo,
            accessibility_security=a11y_sec,
            internal_links=internal_links,
            retrieval_readiness=retrieval,
            answerability=answerability,
            claim_grounding=claim_grounding,
            multimodal=multimodal,
            agent_readiness=agent_readiness,
            external_ai=external_ai,
            limitations_and_uncertainty=limitations,
            epistemic_separation=pkg.epistemic_separation,
            provenance_tags=pkg.provenance_tags,
            engines_executed=pkg.engines_executed,
            raw_evidence_summary=raw_summary,
        )

    # ── Internal Dimension Synthesizers ───────────────────────────────────────

    @staticmethod
    def _synthesize_business_profile(pkg: SiteIntelligencePackage) -> ObservableBusinessProfile:
        title = pkg.technical_seo.title
        meta = pkg.technical_seo.meta_description
        name = pkg.name or ""
        
        # Discover legal name or organizational entity from entity samples
        legal_name = None
        for ent in pkg.entity.entity_names:
            if any(kw in ent for kw in ("Pvt", "Ltd", "Services", "Engineering", "Inc", "LLC", "Corp", "Group")):
                legal_name = ent
                break

        # Industry domain synthesis
        combined_text = f"{title} {meta} {' '.join(pkg.search_topic_query_intent.topics_sample)}".lower()
        industry = "Industrial / Business Services"
        if "materials testing" in combined_text or "ndt" in combined_text:
            industry = "Materials Testing, NDT & Engineering Inspection"
        elif "bis" in combined_text or "crs" in combined_text or "certification" in combined_text:
            industry = "Regulatory Compliance & Product Certification"
        elif "calibration" in combined_text or "measurement" in combined_text:
            industry = "Calibration, Measurement & Metrology"
        elif "company" in combined_text and ("director" in combined_text or "financial" in combined_text or "filing" in combined_text):
            industry = "Corporate Intelligence & Business Research"
        elif "consulting" in combined_text or "advisory" in combined_text:
            industry = "Corporate Advisory, Tax & Legal Consulting"

        sources = []
        if title:
            sources.append("<title> element")
        if meta:
            sources.append("<meta name='description'>")
        if pkg.entity.total_entities_detected > 0:
            sources.append("Entity declarations")
        if pkg.technical_seo.h1_count > 0:
            sources.append("H1 headings")

        status = ReviewDimensionStatus.AVAILABLE if (title or name) else ReviewDimensionStatus.INSUFFICIENT_EVIDENCE
        summary = (
            f"Observable enterprise entity '{name or pkg.domain}' operating within {industry}. "
            f"Branded as '{title[:80]}' with primary purpose evidenced via {len(sources)} structural on-page sources."
        )

        return ObservableBusinessProfile(
            status=status,
            business_name=name or pkg.domain,
            legal_name=legal_name,
            branding_title=title,
            meta_description_summary=meta[:200] if meta else "No meta description evidenced on page.",
            business_nature_summary=summary,
            primary_industry_domain=industry,
            evidence_sources=sources,
            confidence="high" if len(sources) >= 2 else "medium",
        )

    @staticmethod
    def _synthesize_entity_profile(pkg: SiteIntelligencePackage) -> EntityProfile:
        ent = pkg.entity
        status = ReviewDimensionStatus.AVAILABLE if ent.total_entities_detected > 0 else ReviewDimensionStatus.INSUFFICIENT_EVIDENCE
        alignment_summary = (
            f"Detected {ent.total_entities_detected} entity signals across {len(ent.entity_types_detected)} types "
            f"({', '.join(ent.entity_types_detected[:3]) or 'none'}). "
            f"Structured vs visible comparisons: {ent.aligned_comparisons_count} aligned, {ent.divergent_comparisons_count} divergent."
        )

        return EntityProfile(
            status=status,
            total_entities_detected=ent.total_entities_detected,
            entity_types_detected=ent.entity_types_detected,
            named_entities=ent.entity_names[:10],
            relationships_count=ent.relationships_count,
            structured_vs_visible_comparisons=ent.structured_vs_visible_comparisons_count,
            aligned_comparisons=ent.aligned_comparisons_count,
            divergent_comparisons=ent.divergent_comparisons_count,
            entity_alignment_summary=alignment_summary,
            samples=ent.samples[:5],
        )

    @staticmethod
    def _synthesize_service_profile(pkg: SiteIntelligencePackage) -> ServiceProductProfile:
        # Extract explicit services evidenced from topics, titles, and answerable units
        service_units = pkg.answerability.units_by_type.get("SERVICE_DESCRIPTION", 0)
        observable_services = []
        for top in pkg.search_topic_query_intent.topics_sample:
            if any(term in top.lower() for term in ("testing", "calibration", "certification", "inspection", "advisory", "audit", "compliance", "consultant", "research", "materials", "ndt", "metrology")):
                observable_services.append(top)
        
        # Deduplicate and cap
        seen = set()
        unique_services = []
        for s in observable_services:
            clean = s.strip()
            if clean.lower() not in seen:
                seen.add(clean.lower())
                unique_services.append(clean)

        status = ReviewDimensionStatus.AVAILABLE if unique_services or service_units > 0 else ReviewDimensionStatus.PARTIAL
        summary = (
            f"Evidenced {len(unique_services)} distinct core service/capability domains and {service_units} "
            f"explicit on-page service description units."
        )

        return ServiceProductProfile(
            status=status,
            services_observed=unique_services[:12],
            product_offerings=[],
            service_descriptions_count=service_units,
            structured_units_count=service_units,
            evidence_sources=["AnswerabilityEngine", "SearchSignalEngine", "TopicIntelligenceEngine"],
            summary=summary,
        )

    @staticmethod
    def _synthesize_topic_taxonomy(pkg: SiteIntelligencePackage) -> TopicTaxonomyProfile:
        t = pkg.search_topic_query_intent
        total = t.topics_detected_count
        sample = t.topics_sample
        primary = sample[:5] if len(sample) >= 5 else sample
        supporting = sample[5:15] if len(sample) > 5 else []

        dominant_concepts = []
        for item in sample:
            clean = item.strip()
            if clean and clean not in dominant_concepts:
                dominant_concepts.append(clean)
            if len(dominant_concepts) >= 8:
                break

        status = ReviewDimensionStatus.AVAILABLE if total > 0 else ReviewDimensionStatus.INSUFFICIENT_EVIDENCE
        summary = (
            f"Identified {total} deterministic concept clusters. Primary topical anchors: "
            f"{', '.join(primary) if primary else 'None detected'}."
        )

        return TopicTaxonomyProfile(
            status=status,
            total_topics_detected=total,
            primary_topics=primary,
            supporting_topics=supporting,
            topics_sample=sample[:15],
            dominant_concepts=dominant_concepts,
            summary=summary,
        )

    @staticmethod
    def _synthesize_search_intent(pkg: SiteIntelligencePackage) -> SearchIntentProfile:
        intent = pkg.search_topic_query_intent
        primary = intent.primary_intent
        secondary = intent.secondary_intents
        ev_count = intent.intent_evidence_items_count

        summary = (
            f"Primary search intent classified as '{primary}' supported by {ev_count} observable structural signals. "
            f"Secondary intent spectrum: {', '.join(secondary) if secondary else 'None evidenced'}."
        )

        return SearchIntentProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            primary_intent=primary,
            secondary_intents=secondary,
            intent_evidence_count=ev_count,
            intent_evidence_summary=summary,
        )

    @staticmethod
    def _synthesize_topic_distribution(pkg: SiteIntelligencePackage) -> TopicDistributionProfile:
        cnt = pkg.content
        intent = pkg.search_topic_query_intent
        ans = pkg.answerability

        total_words = cnt.main_content_words
        topics_count = intent.topics_detected_count
        density = round((topics_count / max(1, total_words)) * 100, 2)

        summary = (
            f"Content corpus comprises {total_words} words across {cnt.paragraph_count} paragraphs. "
            f"Topical distribution: {ans.explained_topics_count} explained topics with structured units vs "
            f"{ans.mentioned_only_topics_count} mentioned-only topics (topic density: {density} per 100 words)."
        )

        return TopicDistributionProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            direct_primary_concepts_count=len(intent.topics_sample[:5]),
            secondary_supported_concepts_count=len(intent.topics_sample[5:]),
            query_page_concepts_count=intent.query_page_concepts_count,
            total_words=total_words,
            paragraphs_count=cnt.paragraph_count,
            explained_topics_count=ans.explained_topics_count,
            mentioned_only_topics_count=ans.mentioned_only_topics_count,
            concept_density_per_100_words=density,
            summary=summary,
        )

    @staticmethod
    def _synthesize_concentration(pkg: SiteIntelligencePackage) -> PageTopicConcentrationProfile:
        cnt = pkg.content
        can = pkg.cannibalization_search_gaps

        overlap_val = cnt.title_h1_token_overlap
        align_val = cnt.title_h1_alignment

        summary = (
            f"Boilerplate ratio: {cnt.content_to_boilerplate_ratio:.2f}. "
            f"Title-H1 lexical alignment is '{align_val}' with {overlap_val * 100:.1f}% token overlap. "
            f"Heading hierarchy: {'valid' if cnt.heading_hierarchy_valid else 'invalid with skips'}. "
            f"Observable topic overlap signals: {can.potential_cannibalization_signals_count}."
        )

        return PageTopicConcentrationProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            content_to_boilerplate_ratio=cnt.content_to_boilerplate_ratio,
            title_h1_alignment=align_val,
            title_h1_token_overlap=overlap_val,
            heading_hierarchy_valid=cnt.heading_hierarchy_valid,
            heading_skips=cnt.heading_skips,
            empty_sections_count=cnt.empty_sections_count,
            potential_cannibalization_signals_count=can.potential_cannibalization_signals_count,
            observable_gaps_count=can.observable_gaps_count,
            concentration_summary=summary,
            layer_boundary_note=can.layer_boundary_note,
        )

    @staticmethod
    def _synthesize_technical_seo(pkg: SiteIntelligencePackage) -> TechnicalSeoReviewProfile:
        t = pkg.technical_seo
        c = pkg.crawl_discovery

        title_status = "OPTIMAL" if 40 <= t.title_length <= 60 else ("TRUNCATED_RISK" if t.title_length > 60 else "TOO_SHORT")
        if t.title_length == 0:
            title_status = "MISSING"

        desc_len = t.meta_description_length
        desc_status = "OPTIMAL" if 110 <= desc_len <= 160 else ("TRUNCATED_RISK" if desc_len > 160 else ("MISSING" if desc_len == 0 else "TOO_SHORT"))

        canon = c.canonical_url
        if not canon:
            canon_status = "MISSING"
        elif canon.rstrip("/") == pkg.site_url.rstrip("/"):
            canon_status = "MATCHING"
        else:
            canon_status = "MISMATCH"

        summary = (
            f"Title length ({t.title_length} chars: {title_status}), Meta description ({desc_len} chars: {desc_status}). "
            f"Headings: {t.h1_count} H1, {t.h2_count} H2, {t.h3_count} H3. "
            f"Structured data: {len(t.detected_schema_types)} schema types declared across {t.schema_blocks_count} blocks. "
            f"TTFB latency: {t.ttfb_ms:.1f}ms ({t.performance_source})."
        )

        return TechnicalSeoReviewProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            title=t.title,
            title_length=t.title_length,
            title_status=title_status,
            meta_description=t.meta_description,
            meta_description_length=desc_len,
            meta_desc_status=desc_status,
            h1_count=t.h1_count,
            h1_samples=t.h1_samples,
            h2_count=t.h2_count,
            h3_count=t.h3_count,
            schema_types=t.detected_schema_types,
            schema_blocks_count=t.schema_blocks_count,
            schema_validation_issues=t.schema_validation_issues,
            canonical_url=canon,
            canonical_status=canon_status,
            robots_txt_found=c.robots_txt_found,
            sitemaps_declared=c.sitemaps_declared,
            ttfb_ms=t.ttfb_ms,
            performance_score=t.performance_score,
            performance_source=t.performance_source,
            summary=summary,
        )

    @staticmethod
    def _synthesize_a11y_security(pkg: SiteIntelligencePackage) -> AccessibilitySecurityProfile:
        a = pkg.accessibility
        s = pkg.security

        a11y_status = ReviewDimensionStatus.AVAILABLE if a.status == BenchmarkDimensionStatus.AVAILABLE else ReviewDimensionStatus.UNAVAILABLE
        sec_status = ReviewDimensionStatus.AVAILABLE if s.status == BenchmarkDimensionStatus.AVAILABLE else ReviewDimensionStatus.PARTIAL

        summary = (
            f"Accessibility WCAG automated status: {a.wcag_status} ({a.total_violations} violations: {a.serious_count} serious, {a.critical_count} critical). "
            f"Security transport posture: {s.overall_status} (HTTPS: {s.is_https}, TLS days remaining: {s.tls_days_remaining or 'N/A'}, "
            f"HSTS: {s.hsts_present}, CSP: {s.csp_present}, X-Frame-Options: {s.x_frame_options or 'MISSING'})."
        )

        return AccessibilitySecurityProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            wcag_status=a.wcag_status,
            total_accessibility_violations=a.total_violations,
            critical_violations=a.critical_count,
            serious_violations=a.serious_count,
            rules_checked_count=a.rules_checked_count,
            rules_passed_count=a.rules_passed_count,
            a11y_disclaimer=a.disclaimer,
            security_status=s.overall_status,
            is_https=s.is_https,
            tls_valid=s.tls_valid,
            tls_protocol=s.tls_protocol,
            tls_days_remaining=s.tls_days_remaining,
            hsts_present=s.hsts_present,
            csp_present=s.csp_present,
            x_frame_options=s.x_frame_options,
            x_content_type_options=s.x_content_type_options,
            referrer_policy=s.referrer_policy,
            mixed_content_count=s.mixed_content_count,
            server_leakage=s.server_leakage,
            security_findings_count=s.findings_count,
            summary=summary,
        )

    @staticmethod
    def _synthesize_internal_links(pkg: SiteIntelligencePackage) -> InternalLinkStructureProfile:
        lnk = pkg.internal_links
        density = round(lnk.total_internal_links / max(1, pkg.content.main_content_words), 4)

        summary = (
            f"Topology reveals {lnk.total_internal_links} total internal link instances targeting "
            f"{lnk.unique_internal_targets} unique internal destination URLs. "
            f"External references: {lnk.total_external_links} instances targeting {lnk.unique_external_targets} unique domains. "
            f"Empty anchor text occurrences: {lnk.empty_anchors_count}."
        )

        return InternalLinkStructureProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            total_internal_links=lnk.total_internal_links,
            unique_internal_targets=lnk.unique_internal_targets,
            total_external_links=lnk.total_external_links,
            unique_external_targets=lnk.unique_external_targets,
            empty_anchors_count=lnk.empty_anchors_count,
            sample_internal_targets=lnk.sample_internal_targets[:5],
            link_density_ratio=density,
            summary=summary,
        )

    @staticmethod
    def _synthesize_retrieval_readiness(pkg: SiteIntelligencePackage) -> RetrievalReadinessProfile:
        r = pkg.retrieval_readiness
        has_llms = False
        for tag in pkg.provenance_tags:
            if "/llms.txt: Present" in str(tag.get("finding", "")):
                has_llms = True
                break

        summary = (
            f"Bot access: {r.search_index_allowed_count}/6 search indexers, {r.ai_training_allowed_count}/3 training scrapers permitted. "
            f"WAF status: {'CHALLENGE/BLOCK DETECTED (' + (r.waf_provider or 'unknown') + ')' if r.waf_or_challenge_detected else 'No WAF challenge barriers observed'}. "
            f"Snippet directives: {'nosnippet ACTIVE' if r.has_nosnippet else 'snippets allowed'}. "
            f"Word count rendering delta: {r.word_count_delta} words ({r.static_words} static vs {r.rendered_words} rendered). "
            f"/llms.txt manifest: {'Present' if has_llms else 'Missing'}. GEO Score: {pkg.geo_readiness_score}/100."
        )

        return RetrievalReadinessProfile(
            status=ReviewDimensionStatus.BLOCKED if r.waf_blocked else ReviewDimensionStatus.AVAILABLE,
            total_bots_evaluated=r.total_bots_evaluated,
            search_index_allowed_count=r.search_index_allowed_count,
            ai_training_allowed_count=r.ai_training_allowed_count,
            user_fetch_allowed_count=r.user_fetch_allowed_count,
            waf_or_challenge_detected=r.waf_or_challenge_detected,
            waf_blocked=r.waf_blocked,
            waf_provider=r.waf_provider,
            has_nosnippet=r.has_nosnippet,
            has_data_nosnippet=r.has_data_nosnippet,
            max_snippet=r.max_snippet,
            static_words=r.static_words,
            rendered_words=r.rendered_words,
            word_count_delta=r.word_count_delta,
            rendering_impact_summary=r.rendering_impact_summary,
            llms_txt_present=has_llms,
            geo_score=pkg.geo_readiness_score,
            summary=summary,
        )

    @staticmethod
    def _synthesize_answerability(pkg: SiteIntelligencePackage) -> AnswerabilityReviewProfile:
        a = pkg.answerability
        status = ReviewDimensionStatus.AVAILABLE if a.total_units_detected > 0 else ReviewDimensionStatus.INSUFFICIENT_EVIDENCE

        summary = (
            f"Discovered {a.total_units_detected} observable information units across {len(a.units_by_type)} structural types "
            f"({', '.join(f'{k}:{v}' for k, v in a.units_by_type.items()) or 'none'}). "
            f"Topical support: {a.explained_topics_count} explained topics with explicit answerable structures, "
            f"{a.mentioned_only_topics_count} mentioned-only topics, {a.unsupported_heading_topics_count} unsupported headings."
        )

        return AnswerabilityReviewProfile(
            status=status,
            total_units_detected=a.total_units_detected,
            units_by_type=a.units_by_type,
            heading_content_relationship=a.heading_content_relationship,
            question_answer_patterns=a.question_answer_patterns,
            definition_patterns=a.definition_patterns,
            step_list_structure=a.step_list_structure,
            table_availability=a.table_availability,
            explained_topics_count=a.explained_topics_count,
            mentioned_only_topics_count=a.mentioned_only_topics_count,
            unsupported_heading_topics_count=a.unsupported_heading_topics_count,
            unsupported_headings_sample=a.unsupported_headings_sample,
            summary=summary,
        )

    @staticmethod
    def _synthesize_claim_grounding(pkg: SiteIntelligencePackage) -> ClaimGroundingReviewProfile:
        c = pkg.claim_grounding
        status = ReviewDimensionStatus.AVAILABLE if c.total_claims_detected > 0 else ReviewDimensionStatus.INSUFFICIENT_EVIDENCE
        ratio = round(c.supported_claims_count / max(1, c.total_claims_detected), 2)

        summary = (
            f"Evaluated {c.total_claims_detected} visible factual assertions: {c.supported_claims_count} fully supported on-site, "
            f"{c.partially_supported_count} partially supported, {c.uncorroborated_count} uncorroborated, {c.contradicted_count} contradicted "
            f"({ratio * 100:.0f}% grounding ratio). "
            f"Schema-DOM alignment: {c.structured_agreements_count} agreements, {c.structured_disagreements_count} disagreements."
        )

        return ClaimGroundingReviewProfile(
            status=status,
            total_claims_detected=c.total_claims_detected,
            supported_claims_count=c.supported_claims_count,
            partially_supported_count=c.partially_supported_count,
            uncorroborated_count=c.uncorroborated_count,
            contradicted_count=c.contradicted_count,
            structured_agreements_count=c.structured_agreements_count,
            structured_disagreements_count=c.structured_disagreements_count,
            entity_consistency_breakdown=c.entity_consistency_breakdown,
            grounding_ratio=ratio,
            summary=summary,
        )

    @staticmethod
    def _synthesize_multimodal(pkg: SiteIntelligencePackage) -> MultimodalReviewProfile:
        m = pkg.multimodal
        ratio = round(m.alt_represented_count / max(1, m.informational_assets_count), 2)

        summary = (
            f"Identified {m.total_visual_assets} visual assets ({m.informational_assets_count} informational, {m.decorative_assets_count} decorative). "
            f"Alt-text coverage: {m.alt_represented_count}/{m.informational_assets_count} informational assets ({ratio * 100:.0f}%). "
            f"Visual-only observed information gaps: {m.visual_only_observed_gaps}. "
            f"Modern formats (WebP/AVIF): {m.modern_format_count}. Layout shift risks (missing dimensions): {m.missing_dimensions_count}."
        )

        return MultimodalReviewProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            total_visual_assets=m.total_visual_assets,
            informational_assets_count=m.informational_assets_count,
            decorative_assets_count=m.decorative_assets_count,
            alt_represented_count=m.alt_represented_count,
            caption_represented_count=m.caption_represented_count,
            text_represented_count=m.text_represented_count,
            visual_only_observed_gaps=m.visual_only_observed_gaps,
            modern_format_count=m.modern_format_count,
            missing_dimensions_count=m.missing_dimensions_count,
            alt_coverage_ratio=ratio,
            summary=summary,
        )

    @staticmethod
    def _synthesize_agent_readiness(pkg: SiteIntelligencePackage) -> AgentReadinessReviewProfile:
        ag = pkg.agent_readiness

        summary = (
            f"Detected {ag.total_forms_detected} interactive forms ({ag.labeled_forms_count} labeled), "
            f"{ag.action_buttons_detected} action buttons ({ag.meaningful_accessible_buttons_count} accessible), "
            f"{ag.descriptive_navigation_links_count} descriptive navigation links. "
            f"Structured schema actions: {ag.schema_actions_detected}, WebMCP declarations: {ag.webmcp_declarations_detected}. "
            f"Triangulated information access paths: {ag.total_access_paths} (Action surface gaps: {ag.action_surface_gaps})."
        )

        return AgentReadinessReviewProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            total_forms_detected=ag.total_forms_detected,
            labeled_forms_count=ag.labeled_forms_count,
            action_buttons_detected=ag.action_buttons_detected,
            meaningful_accessible_buttons_count=ag.meaningful_accessible_buttons_count,
            descriptive_navigation_links_count=ag.descriptive_navigation_links_count,
            schema_actions_detected=ag.schema_actions_detected,
            webmcp_declarations_detected=ag.webmcp_declarations_detected,
            total_access_paths=ag.total_access_paths,
            action_surface_gaps=ag.action_surface_gaps,
            summary=summary,
        )

    @staticmethod
    def _synthesize_external_ai(pkg: SiteIntelligencePackage) -> ExternalAiReviewProfile:
        ext = pkg.external_ai
        status_str = ext.status.value

        if status_str == "DISABLED":
            summary = "External AI visibility evaluation was not requested (strictly opt-in via --external-ai). Offline boundary preserved."
            stat = ReviewDimensionStatus.DISABLED
        elif status_str == "AVAILABLE":
            summary = (
                f"Evaluated {len(ext.providers_evaluated)} provider(s) across {ext.queries_executed_count} queries. "
                f"Domain cited {ext.target_domain_cited_count} times, mentioned {ext.target_domain_mentioned_count} times."
            )
            stat = ReviewDimensionStatus.AVAILABLE
        elif status_str == "PARTIAL":
            summary = f"Partial external observations ({ext.successful_observations_count} successful, {ext.failed_observations_count} failed)."
            stat = ReviewDimensionStatus.PARTIAL
        else:
            reason = ext.failure_reason or "Unknown provider failure"
            summary = f"External observation failed or rate limited: {reason}."
            stat = ReviewDimensionStatus.UNAVAILABLE

        return ExternalAiReviewProfile(
            status=stat,
            providers_evaluated=ext.providers_evaluated,
            queries_executed_count=ext.queries_executed_count,
            successful_observations_count=ext.successful_observations_count,
            failed_observations_count=ext.failed_observations_count,
            target_domain_cited_count=ext.target_domain_cited_count,
            target_domain_mentioned_count=ext.target_domain_mentioned_count,
            total_external_citations=ext.total_external_citations,
            failure_reason=ext.failure_reason,
            limitation_disclaimer=ext.limitation_disclaimer,
            summary=summary,
        )

    @staticmethod
    def _synthesize_limitations(pkg: SiteIntelligencePackage) -> EvidenceLimitationsProfile:
        dim_statuses = {
            "crawl_discovery": pkg.crawl_discovery.status.value,
            "technical_seo": pkg.technical_seo.status.value,
            "accessibility": pkg.accessibility.status.value,
            "security": pkg.security.status.value,
            "content": pkg.content.status.value,
            "entity": pkg.entity.status.value,
            "internal_links": pkg.internal_links.status.value,
            "search_topic_query_intent": pkg.search_topic_query_intent.status.value,
            "cannibalization_search_gaps": pkg.cannibalization_search_gaps.status.value,
            "retrieval_readiness": pkg.retrieval_readiness.status.value,
            "answerability": pkg.answerability.status.value,
            "claim_grounding": pkg.claim_grounding.status.value,
            "multimodal": pkg.multimodal.status.value,
            "agent_readiness": pkg.agent_readiness.status.value,
            "external_ai": pkg.external_ai.status.value,
        }

        uncertainty_notes = [
            "Evaluated from single-page multi-engine collection pass; multi-page cannibalization and site-wide architecture are bounded.",
            "Automated WCAG 2.1 checks evaluate observable criteria; non-certification scope.",
            "Third-party search volume, market share, Google rankings, and traffic are NOT inferred from website evidence.",
            "Zero redundant network calls dispatched during review synthesis.",
        ]

        summary = (
            f"Review bound by {len(pkg.crawl_limitations)} explicit crawl limitations and {len(pkg.conflicts_detected)} "
            f"cross-engine conflicts. All 15 collection dimensions maintain explicit epistemic statuses."
        )

        return EvidenceLimitationsProfile(
            status=ReviewDimensionStatus.AVAILABLE,
            crawl_limitations=pkg.crawl_limitations,
            dimension_statuses=dim_statuses,
            cross_engine_conflicts=pkg.conflicts_detected,
            uncertainty_notes=uncertainty_notes,
            summary=summary,
        )

    # ── Collection & Batch Review Methods ────────────────────────────────────

    @classmethod
    def load_package(cls, file_path: str) -> SiteIntelligencePackage:
        """Load and deserialize a single SiteIntelligencePackage JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SiteIntelligencePackage.model_validate(data)

    @classmethod
    def review_all(
        cls,
        packages_dir: str = "benchmarks/packages",
        output_dir: Optional[str] = "benchmarks/reviews",
    ) -> BenchmarkReviewDataset:
        """
        Synthesize reviews for all benchmark packages found in `packages_dir`.
        Optionally persists JSON and Markdown review documents to `output_dir`.
        """
        pkg_dir = Path(packages_dir)
        if not pkg_dir.exists():
            raise FileNotFoundError(f"Packages directory '{packages_dir}' not found.")

        package_files = sorted(list(pkg_dir.glob("*.json")))
        if not package_files:
            raise FileNotFoundError(f"No benchmark package JSON files found in '{packages_dir}'.")

        reviews_dict: Dict[str, WebsiteIntelligenceReview] = {}
        summary_index: List[Dict[str, Any]] = []

        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

        for pfile in package_files:
            pkg = cls.load_package(str(pfile))
            rev = cls.synthesize_review(pkg)
            clean_key = _clean_domain(rev.domain)
            reviews_dict[clean_key] = rev

            summary_index.append({
                "domain": rev.domain,
                "clean_key": clean_key,
                "name": rev.name,
                "role": rev.role,
                "health_score": rev.overall_health_score,
                "tech_score": rev.technical_health_score,
                "geo_score": rev.geo_readiness_score,
                "trust_score": rev.trust_score,
                "perf_score": rev.performance_score,
                "entities_detected": rev.entity_profile.total_entities_detected,
                "topics_detected": rev.topic_taxonomy.total_topics_detected,
                "answer_units": rev.answerability.total_units_detected,
                "claims_grounded": f"{rev.claim_grounding.supported_claims_count}/{rev.claim_grounding.total_claims_detected}",
                "visual_assets": rev.multimodal.total_visual_assets,
                "waf_detected": rev.retrieval_readiness.waf_or_challenge_detected,
            })

            if output_dir:
                cls.save_review_pair(rev, output_dir=output_dir)

        dataset = BenchmarkReviewDataset(
            review_version="11.2",
            created_at=now_ts,
            total_sites=len(reviews_dict),
            sites_reviewed=len(reviews_dict),
            reviews=reviews_dict,
            summary_index=summary_index,
        )

        if output_dir:
            out_p = Path(output_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            agg_file = out_p / "benchmark_reviews_phase11.json"
            with open(agg_file, "w", encoding="utf-8") as f:
                f.write(dataset.model_dump_json(indent=2))

        return dataset

    @classmethod
    def save_review_pair(
        cls,
        review: WebsiteIntelligenceReview,
        output_dir: str = "benchmarks/reviews",
    ) -> Tuple[str, str]:
        """Save both JSON and Markdown representation of a review."""
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)

        clean_dom = _clean_domain(review.domain)
        json_path = out_p / f"{clean_dom}.json"
        md_path = out_p / f"{clean_dom}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(review.model_dump_json(indent=2))

        md_content = cls.render_markdown(review)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return str(json_path), str(md_path)

    # ── Markdown Representation Renderer ─────────────────────────────────────

    @classmethod
    def render_markdown(cls, r: WebsiteIntelligenceReview) -> str:
        """Render a comprehensive GitHub Markdown intelligence review covering all 18 dimensions."""
        lines = []
        lines.append(f"# Website Intelligence Review — {r.name or r.domain}")
        lines.append("")
        lines.append(f"**Target Site:** `{r.site_url}`  ")
        lines.append(f"**Domain:** `{r.domain}`  ")
        lines.append(f"**Role:** `{r.role}`  ")
        lines.append(f"**Evidence Collection Date:** `{r.collection_timestamp}`  ")
        lines.append(f"**Review Generated:** `{r.review_timestamp}`  ")
        lines.append(f"**Health Score Formula Mode:** `{r.score_formula_mode}` (Formula Invariance $\\Delta=0$: {'🟢 VERIFIED' if r.formula_invariance_verified else '🔴 MISMATCH'})  ")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Invariant Search & Citability Scorecard")
        lines.append("")
        lines.append("| Metric Category | Score / 100 | Epistemic Basis | Formula Mode |")
        lines.append("| :--- | :---: | :--- | :---: |")
        lines.append(f"| **Overall Search Health** | **{r.overall_health_score}** | Cross-engine consensus | `{r.score_formula_mode}` |")
        lines.append(f"| **Technical SEO Foundation** | **{r.technical_health_score}** | Static HTML & DOM checks | `{r.score_formula_mode}` |")
        lines.append(f"| **GEO / Citability Readiness** | **{r.geo_readiness_score}** | Princeton GEO metrics & structure | `{r.score_formula_mode}` |")
        lines.append(f"| **Trust Stack (E-E-A-T)** | **{r.trust_score}** | Security, Contact, Legal & Policy Signals | `{r.score_formula_mode}` |")
        lines.append(f"| **Performance & Latency** | **{r.performance_score}** | TTFB & Header response probe | `{r.score_formula_mode}` |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Observable business/company understanding
        bp = r.business_profile
        lines.append("## 1. Observable Business & Enterprise Understanding")
        lines.append(f"- **Declared Entity Name:** {bp.business_name}")
        if bp.legal_name:
            lines.append(f"- **Identified Legal Entity:** `{bp.legal_name}`")
        lines.append(f"- **Primary Industry Domain:** {bp.primary_industry_domain}")
        lines.append(f"- **Branding Page Title:** \"{bp.branding_title}\"")
        lines.append(f"- **Meta Description:** \"{bp.meta_description_summary}\"")
        lines.append(f"- **Evidence Sources:** {', '.join(bp.evidence_sources)}")
        lines.append(f"- **Operational Status:** `{bp.status.value}` (Confidence: `{bp.confidence}`)")
        lines.append(f"- **Analytical Summary:** {bp.business_nature_summary}")
        lines.append("")

        # 2. Entities and entity types
        ep = r.entity_profile
        lines.append("## 2. Entities & Knowledge Graph Representation")
        lines.append(f"- **Status:** `{ep.status.value}`")
        lines.append(f"- **Total Entities Detected:** {ep.total_entities_detected}")
        lines.append(f"- **Entity Types:** {', '.join(ep.entity_types_detected) if ep.entity_types_detected else 'None evidenced'}")
        lines.append(f"- **Named Entities (Sample):** {', '.join(ep.named_entities[:6]) if ep.named_entities else 'None detected'}")
        lines.append(f"- **Structured vs Visible Alignment:** {ep.aligned_comparisons} aligned, {ep.divergent_comparisons} divergent across {ep.structured_vs_visible_comparisons} comparisons.")
        lines.append(f"- **Synthesis:** {ep.entity_alignment_summary}")
        lines.append("")

        # 3. Observable services/products
        sp = r.service_profile
        lines.append("## 3. Observable Services & Products")
        lines.append(f"- **Status:** `{sp.status.value}`")
        lines.append(f"- **Service Descriptions Evidenced:** {sp.service_descriptions_count} explicit units")
        if sp.services_observed:
            lines.append(f"- **Core Services Evidenced:**")
            for svc in sp.services_observed:
                lines.append(f"  - {svc}")
        else:
            lines.append("- **Core Services Evidenced:** None explicitly cataloged in structured units.")
        lines.append(f"- **Synthesis:** {sp.summary}")
        lines.append("")

        # 4 & 5. Primary and supporting topics & Dominant concepts
        tp = r.topic_taxonomy
        lines.append("## 4 & 5. Topic Taxonomy & Dominant Concepts")
        lines.append(f"- **Status:** `{tp.status.value}`")
        lines.append(f"- **Total Topics Detected:** {tp.total_topics_detected}")
        lines.append(f"- **Primary Topics (Top 5):** {', '.join(tp.primary_topics) if tp.primary_topics else 'None'}")
        lines.append(f"- **Supporting Topics (Sample):** {', '.join(tp.supporting_topics) if tp.supporting_topics else 'None'}")
        lines.append(f"- **Dominant Semantic Concepts:** {', '.join(r.dominant_concepts) if r.dominant_concepts else 'None'}")
        lines.append(f"- **Synthesis:** {tp.summary}")
        lines.append("")

        # 6. Observable search intents
        si = r.search_intent
        lines.append("## 6. Observable Search Intent")
        lines.append(f"- **Status:** `{si.status.value}`")
        lines.append(f"- **Primary Intent:** `{si.primary_intent}`")
        lines.append(f"- **Secondary Intents:** {', '.join(f'`{x}`' for x in si.secondary_intents) if si.secondary_intents else 'None evidenced'}")
        lines.append(f"- **Supporting Evidence Count:** {si.intent_evidence_count} observable signals")
        lines.append(f"- **Synthesis:** {si.intent_evidence_summary}")
        lines.append("")

        # 7. Topic-to-page distribution
        td = r.topic_distribution
        lines.append("## 7. Topic-to-Page Distribution")
        lines.append(f"- **Status:** `{td.status.value}`")
        lines.append(f"- **Content Length:** {td.total_words} words across {td.paragraphs_count} paragraphs")
        lines.append(f"- **Topic Breadth:** {td.explained_topics_count} explained topics vs {td.mentioned_only_topics_count} mentioned-only topics")
        lines.append(f"- **Topic Density:** {td.concept_density_per_100_words} concepts per 100 words")
        lines.append(f"- **Synthesis:** {td.summary}")
        lines.append("")

        # 8. Page/topic concentration and overlap
        co = r.concentration_and_overlap
        lines.append("## 8. Page Concentration & Topical Overlap")
        lines.append(f"- **Status:** `{co.status.value}`")
        lines.append(f"- **Boilerplate Ratio:** {co.content_to_boilerplate_ratio:.2f}")
        lines.append(f"- **Title-H1 Alignment:** `{co.title_h1_alignment}` ({co.title_h1_token_overlap * 100:.1f}% token overlap)")
        lines.append(f"- **Heading Hierarchy Valid:** {'Yes' if co.heading_hierarchy_valid else 'No (skips detected)'}")
        if co.heading_skips:
            lines.append(f"- **Heading Skips:** {', '.join(co.heading_skips)}")
        lines.append(f"- **Potential Cannibalization Signals:** {co.potential_cannibalization_signals_count}")
        lines.append(f"- **Observable Topic Gaps:** {co.observable_gaps_count}")
        lines.append(f"- **Boundary Notice:** *{co.layer_boundary_note}*")
        lines.append("")

        # 9. Technical SEO condition
        ts = r.technical_seo
        lines.append("## 9. Technical SEO Foundation")
        lines.append(f"- **Status:** `{ts.status.value}`")
        lines.append(f"- **Page Title ({ts.title_length} chars):** \"{ts.title}\" [`{ts.title_status}`]")
        lines.append(f"- **Meta Description ({ts.meta_description_length} chars):** \"{ts.meta_description}\" [`{ts.meta_desc_status}`]")
        lines.append(f"- **Heading Structure:** {ts.h1_count} H1, {ts.h2_count} H2, {ts.h3_count} H3")
        lines.append(f"- **Structured Data:** {len(ts.schema_types)} types ({', '.join(ts.schema_types) if ts.schema_types else 'None'}) across {ts.schema_blocks_count} blocks")
        lines.append(f"- **Canonical URL:** `{ts.canonical_url or 'MISSING'}` [`{ts.canonical_status}`]")
        lines.append(f"- **Robots.txt:** {'Found' if ts.robots_txt_found else 'Missing'} | Sitemaps declared: {len(ts.sitemaps_declared)}")
        lines.append(f"- **Latency (TTFB):** {ts.ttfb_ms:.1f}ms ({ts.performance_source})")
        lines.append("")

        # 10. Accessibility and security signals
        as_ = r.accessibility_security
        lines.append("## 10. Accessibility & Transport Security")
        lines.append(f"- **WCAG 2.1 Automated Status:** `{as_.wcag_status}` ({as_.total_accessibility_violations} violations: {as_.critical_violations} critical, {as_.serious_violations} serious)")
        lines.append(f"- **Accessibility Disclaimer:** *{as_.a11y_disclaimer}*")
        lines.append(f"- **Security Posture:** `{as_.security_status}` ({as_.security_findings_count} findings)")
        lines.append(f"- **HTTPS:** {'Enforced' if as_.is_https else 'Not Enforced'} | TLS Days Remaining: {as_.tls_days_remaining or 'N/A'}")
        lines.append(f"- **Security Headers:** HSTS: `{as_.hsts_present}`, CSP: `{as_.csp_present}`, X-Frame-Options: `{as_.x_frame_options or 'MISSING'}`")
        lines.append("")

        # 11. Internal-link structure
        il = r.internal_links
        lines.append("## 11. Internal Link Architecture")
        lines.append(f"- **Status:** `{il.status.value}`")
        lines.append(f"- **Internal Links:** {il.total_internal_links} instances targeting {il.unique_internal_targets} unique URLs")
        lines.append(f"- **External Links:** {il.total_external_links} instances targeting {il.unique_external_targets} unique URLs")
        lines.append(f"- **Empty Anchors:** {il.empty_anchors_count}")
        lines.append(f"- **Link Density:** {il.link_density_ratio:.4f} links per content word")
        lines.append("")

        # 12. GEO/AI retrieval readiness
        rr = r.retrieval_readiness
        lines.append("## 12. GEO & AI Retrieval Readiness")
        lines.append(f"- **Status:** `{rr.status.value}`")
        lines.append(f"- **Bot Access Matrix:** {rr.search_index_allowed_count}/6 search indexers, {rr.ai_training_allowed_count}/3 training scrapers allowed")
        lines.append(f"- **WAF / Barrier:** {'CHALLENGE/BLOCK DETECTED (' + (rr.waf_provider or 'unknown') + ')' if rr.waf_or_challenge_detected else 'None observed'}")
        lines.append(f"- **Snippet Directives:** {'nosnippet ACTIVE' if rr.has_nosnippet else 'Snippets allowed'}")
        lines.append(f"- **Word Count Rendering Impact:** {rr.word_count_delta} words delta ({rr.static_words} static vs {rr.rendered_words} rendered)")
        lines.append(f"- **/llms.txt Manifest:** {'Present' if rr.llms_txt_present else 'Missing'}")
        lines.append(f"- **GEO Readiness Score:** {rr.geo_score}/100")
        lines.append("")

        # 13. Answerability structures
        an = r.answerability
        lines.append("## 13. AI Answerability & Structured Units")
        lines.append(f"- **Status:** `{an.status.value}`")
        lines.append(f"- **Total Units Detected:** {an.total_units_detected}")
        if an.units_by_type:
            lines.append(f"- **Units Breakdown:**")
            for ut, uc in an.units_by_type.items():
                lines.append(f"  - `{ut}`: {uc}")
        else:
            lines.append("- **Units Breakdown:** No structured information units detected on-site.")
        lines.append(f"- **Explained vs Mentioned Topics:** {an.explained_topics_count} explained, {an.mentioned_only_topics_count} mentioned only")
        lines.append(f"- **Unsupported Headings:** {an.unsupported_heading_topics_count}")
        lines.append("")

        # 14. Claim/entity grounding
        cg = r.claim_grounding
        lines.append("## 14. Claim Grounding & Assertion Support")
        lines.append(f"- **Status:** `{cg.status.value}`")
        lines.append(f"- **Total Observable Claims:** {cg.total_claims_detected}")
        lines.append(f"- **On-Site Support Status:** {cg.supported_claims_count} supported ({cg.grounding_ratio * 100:.0f}%), {cg.partially_supported_count} partial, {cg.uncorroborated_count} uncorroborated, {cg.contradicted_count} contradicted")
        lines.append(f"- **Structured vs Visible Content:** {cg.structured_agreements_count} agreements, {cg.structured_disagreements_count} disagreements")
        lines.append("")

        # 15. Multimodal readiness
        mm = r.multimodal
        lines.append("## 15. Multimodal Asset Readiness")
        lines.append(f"- **Status:** `{mm.status.value}`")
        lines.append(f"- **Total Visual Assets:** {mm.total_visual_assets}")
        lines.append(f"- **Asset Breakdown:** {mm.informational_assets_count} informational, {mm.decorative_assets_count} decorative")
        lines.append(f"- **Alt-Text Coverage:** {mm.alt_represented_count}/{mm.informational_assets_count} informational assets ({mm.alt_coverage_ratio * 100:.0f}%)")
        lines.append(f"- **Visual-Only Gaps:** {mm.visual_only_observed_gaps}")
        lines.append(f"- **Layout Shift Risks (Missing Dimensions):** {mm.missing_dimensions_count}")
        lines.append("")

        # 16. Agent/action-surface readiness
        ar = r.agent_readiness
        lines.append("## 16. Autonomous Agent Action Surfaces")
        lines.append(f"- **Status:** `{ar.status.value}`")
        lines.append(f"- **Interactive Forms:** {ar.total_forms_detected} ({ar.labeled_forms_count} labeled)")
        lines.append(f"- **Action Buttons:** {ar.action_buttons_detected} ({ar.meaningful_accessible_buttons_count} accessible)")
        lines.append(f"- **Descriptive Navigation Links:** {ar.descriptive_navigation_links_count}")
        lines.append(f"- **Schema Actions & WebMCP:** {ar.schema_actions_detected} Schema actions, {ar.webmcp_declarations_detected} WebMCP declarations")
        lines.append(f"- **Triangulated Access Paths:** {ar.total_access_paths} (Action surface gaps: {ar.action_surface_gaps})")
        lines.append("")

        # 17. External AI observations
        ea = r.external_ai
        lines.append("## 17. External AI Visibility Observations")
        lines.append(f"- **Status:** `{ea.status.value}`")
        if ea.status == ReviewDimensionStatus.DISABLED:
            lines.append("- **Measurement Note:** External AI measurement was disabled during this collection pass (strictly opt-in via `--external-ai`).")
        else:
            lines.append(f"- **Providers Evaluated:** {', '.join(ea.providers_evaluated)}")
            lines.append(f"- **Queries Executed:** {ea.queries_executed_count} ({ea.successful_observations_count} succeeded, {ea.failed_observations_count} failed)")
            lines.append(f"- **Target Domain Citations:** {ea.target_domain_cited_count} cited, {ea.target_domain_mentioned_count} mentioned")
            if ea.failure_reason:
                lines.append(f"- **Failure Reason:** `{ea.failure_reason}`")
        lines.append(f"- **Disclaimer:** *{ea.limitation_disclaimer}*")
        lines.append("")

        # 18. Evidence limitations and uncertainty
        lim = r.limitations_and_uncertainty
        lines.append("## 18. Evidence Limitations & Uncertainty")
        lines.append(f"- **Status:** `{lim.status.value}`")
        lines.append(f"- **Crawl Scope Constraints:**")
        for cl in lim.crawl_limitations:
            lines.append(f"  - {cl}")
        lines.append(f"- **Uncertainty & Boundaries:**")
        for un in lim.uncertainty_notes:
            lines.append(f"  - {un}")
        if lim.cross_engine_conflicts:
            lines.append(f"- **Cross-Engine Conflicts Detected ({len(lim.cross_engine_conflicts)}):**")
            for c in lim.cross_engine_conflicts:
                lines.append(f"  - `[{c.get('severity', 'INFO')}]` {c.get('feature', 'Feature')}: {c.get('description', '')}")
        lines.append("")

        # Epistemic Partitioning Container
        ep = r.epistemic_separation
        lines.append("---")
        lines.append("")
        lines.append("## Epistemic Separation Container")
        lines.append("")
        lines.append("### 1. Hard On-Page Facts (DOM & HTTP Headers)")
        for fact in ep.facts[:12]:
            lines.append(f"- {fact}")
        lines.append("")
        lines.append("### 2. External Observations (Third-Party Probes)")
        for ext in ep.external_observations:
            lines.append(f"- {ext}")
        lines.append("")
        lines.append("### 3. RankIntel Analysis & Syntheses")
        for ana in ep.analyses:
            lines.append(f"- {ana}")
        lines.append("")
        lines.append("### 4. Prioritized Recommendations")
        for rec in ep.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

        # Provenance Log
        lines.append("---")
        lines.append("")
        lines.append("## Provenance & Attribution Log")
        lines.append("")
        lines.append(f"Preserving {len(r.provenance_tags)} provenance records across engines: `{', '.join(r.engines_executed)}`.")
        lines.append("")
        lines.append("| Engine | Finding | Source | Confidence |")
        lines.append("| :--- | :--- | :--- | :---: |")
        for pt in r.provenance_tags[:12]:
            clean_f = str(pt.get("finding", "")).replace("|", "\\|")
            lines.append(f"| `{pt.get('engine', '')}` | {clean_f} | `{pt.get('source_file', '')}` | `{pt.get('confidence', '')}` |")
        lines.append("")

        return "\n".join(lines)
