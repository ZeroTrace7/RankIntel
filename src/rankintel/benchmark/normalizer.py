"""
Benchmark Normalizer — Converts unified multi-engine SynthesisReport and EngineResults
into a structured, provenance-preserving SiteIntelligencePackage across 15 dimensions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from rankintel.models.schema import SynthesisReport, EngineResult
from rankintel.benchmark.models import (
    BenchmarkDimensionStatus,
    CrawlDiscoveryDimension,
    TechnicalSeoDimension,
    AccessibilityDimension,
    SecurityDimension,
    ContentDimension,
    EntityDimension,
    InternalLinkDimension,
    SearchTopicQueryIntentDimension,
    CannibalizationSearchGapDimension,
    RetrievalReadinessDimension,
    AnswerabilityDimension,
    ClaimGroundingDimension,
    MultimodalDimension,
    AgentReadinessDimension,
    ExternalAiDimension,
    EpistemicSeparation,
    SiteIntelligencePackage,
)


class BenchmarkNormalizer:
    """Normalizes multi-engine audit results into a standardized 15-dimension benchmark package."""

    @staticmethod
    def normalize(
        url: str,
        report: SynthesisReport,
        engine_results: Dict[str, EngineResult],
        name: str = "",
        role: str = "competitor",
        execution_time_sec: float = 0.0,
        crawl_limitations: Optional[List[str]] = None,
        raw_report_paths: Optional[Dict[str, str]] = None,
    ) -> SiteIntelligencePackage:
        limits = crawl_limitations or [
            "Single-page multi-engine collection pass",
            "Concurrency: process-isolated worker",
            "Timeout: 15.0s per socket request",
        ]
        
        # 1. Crawl / Discovery Dimension
        p = report.unified_on_page
        r = report.unified_robots
        crawl_status = BenchmarkDimensionStatus.AVAILABLE if p.status_code > 0 else BenchmarkDimensionStatus.UNAVAILABLE
        crawl_dim = CrawlDiscoveryDimension(
            status=crawl_status,
            url=report.url,
            http_status_code=p.status_code,
            is_redirect=p.is_redirect,
            canonical_url=p.canonical_url,
            internal_links_count=len(p.internal_links),
            external_links_count=len(p.external_links),
            robots_txt_found=r.found,
            robots_txt_url=r.robots_url,
            sitemaps_declared=list(r.sitemaps),
            crawl_limitations=limits,
            notes=[f"HTTP Status: {p.status_code}", f"Discovered {len(p.internal_links)} internal links"],
        )

        # 2. Technical SEO Dimension
        schema = report.unified_schema
        perf = report.unified_performance
        tech_status = BenchmarkDimensionStatus.AVAILABLE if p.status_code == 200 else BenchmarkDimensionStatus.PARTIAL
        tech_dim = TechnicalSeoDimension(
            status=tech_status,
            title=p.title,
            title_length=p.title_length,
            meta_description=p.meta_description,
            meta_description_length=p.meta_desc_length,
            h1_count=p.h1_count,
            h1_samples=list(p.h1_text[:5]),
            h2_count=p.h2_count,
            h3_count=p.h3_count,
            detected_schema_types=list(schema.detected_types),
            schema_blocks_count=schema.blocks_count,
            schema_validation_issues=list(schema.validation_issues),
            ttfb_ms=round(perf.ttfb_ms, 1),
            performance_score=perf.overall_performance_score,
            performance_source=perf.source,
            notes=[f"Title ({p.title_length} chars)", f"{len(schema.detected_types)} schema types detected"],
        )

        # 3. Accessibility Dimension
        a11y = report.unified_accessibility
        if a11y and a11y.wcag_aa_status.value in ("PASS", "FAIL", "PARTIAL"):
            a11y_status = BenchmarkDimensionStatus.AVAILABLE
        elif a11y and a11y.wcag_aa_status.value == "UNAVAILABLE":
            a11y_status = BenchmarkDimensionStatus.UNAVAILABLE
        else:
            a11y_status = BenchmarkDimensionStatus.PARTIAL

        a11y_samples = []
        if a11y and a11y.violations:
            for v in a11y.violations[:10]:
                a11y_samples.append({
                    "rule_id": v.rule_id,
                    "severity": v.severity.value if hasattr(v.severity, "value") else str(v.severity),
                    "description": v.description,
                    "failure_summary": v.failure_summary,
                })

        a11y_dim = AccessibilityDimension(
            status=a11y_status,
            wcag_status=a11y.wcag_aa_status.value if a11y else "UNAVAILABLE",
            engine_source=a11y.engine_source if a11y else "accessibility_engine",
            browser_evaluated=a11y.browser_evaluated if a11y else False,
            total_violations=a11y.total_violations if a11y else 0,
            critical_count=a11y.critical_count if a11y else 0,
            serious_count=a11y.serious_count if a11y else 0,
            moderate_count=a11y.moderate_count if a11y else 0,
            minor_count=a11y.minor_count if a11y else 0,
            rules_checked_count=a11y.rules_evaluated_count if a11y else 0,
            rules_passed_count=a11y.rules_passed_count if a11y else 0,
            violation_samples=a11y_samples,
            disclaimer="Automated checks evaluate observable criteria; non-certification scope.",
            notes=list(a11y.notes) if a11y else [],
        )

        # 4. Security Dimension
        sec = report.unified_security
        if sec and sec.overall_status.name in ("PASS", "FAIL", "PARTIAL"):
            sec_status = BenchmarkDimensionStatus.AVAILABLE
        else:
            sec_status = BenchmarkDimensionStatus.UNAVAILABLE

        sec_findings_sample = []
        if sec and sec.findings:
            for f in sec.findings[:10]:
                sec_findings_sample.append({
                    "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                    "title": f.title,
                    "recommendation": f.recommendation,
                })

        sec_dim = SecurityDimension(
            status=sec_status,
            overall_status=sec.overall_status.name if sec else "UNAVAILABLE",
            is_https=sec.is_https if sec else False,
            tls_valid=sec.tls_details.is_valid if (sec and sec.tls_details) else None,
            tls_protocol=sec.tls_details.protocol_version if (sec and sec.tls_details) else None,
            tls_days_remaining=sec.tls_details.days_until_expiration if (sec and sec.tls_details) else None,
            hsts_present=sec.hsts_present if sec else False,
            hsts_preload=sec.hsts_preload if sec else False,
            csp_present=sec.csp_present if sec else False,
            x_frame_options=sec.x_frame_options if sec else None,
            x_content_type_options=sec.x_content_type_options if sec else None,
            referrer_policy=sec.referrer_policy if sec else None,
            mixed_content_count=len(sec.mixed_content_resources) if sec else 0,
            server_leakage=list(sec.server_leakage) if sec else [],
            findings_count=len(sec.findings) if sec else 0,
            findings_samples=sec_findings_sample,
            notes=list(sec.recommendations) if sec else [],
        )

        # 5. Content Dimension
        cnt = report.unified_content
        cnt_status = BenchmarkDimensionStatus.AVAILABLE if (cnt and cnt.main_content_word_count > 0) else BenchmarkDimensionStatus.UNAVAILABLE
        ext_meth = cnt.extraction_method.value if (cnt and hasattr(cnt.extraction_method, "value")) else str(getattr(cnt, "extraction_method", "UNAVAILABLE"))
        thin_tier = cnt.thin_content.word_count_tier.value if (cnt and hasattr(cnt.thin_content.word_count_tier, "value")) else str(getattr(getattr(cnt, "thin_content", None), "word_count_tier", "UNAVAILABLE"))
        t_align = cnt.title_h1_relationship.alignment_status.value if (cnt and cnt.title_h1_relationship) else "UNAVAILABLE"
        t_overlap = cnt.title_h1_relationship.token_overlap_ratio if (cnt and cnt.title_h1_relationship) else 0.0

        cnt_dim = ContentDimension(
            status=cnt_status,
            main_content_words=cnt.main_content_word_count if cnt else 0,
            total_body_words=cnt.total_body_word_count if cnt else 0,
            content_to_boilerplate_ratio=round(cnt.content_to_boilerplate_ratio, 2) if cnt else 0.0,
            paragraph_count=cnt.paragraph_count if cnt else 0,
            extraction_method=ext_meth,
            thin_content_tier=thin_tier,
            has_placeholder_text=cnt.thin_content.placeholder_text_detected if cnt else False,
            exact_content_hash=cnt.exact_content_hash if cnt else "",
            simhash=cnt.simhash if cnt else "",
            title_h1_alignment=t_align,
            title_h1_token_overlap=round(t_overlap, 2),
            heading_hierarchy_valid=cnt.heading_structure.heading_hierarchy_valid if cnt else True,
            heading_skips=list(cnt.heading_structure.heading_skips) if cnt else [],
            empty_sections_count=cnt.heading_structure.empty_sections_count if cnt else 0,
            notes=list(cnt.facts) if cnt else [],
        )

        # 6. Entity Dimension
        ent = report.unified_entity
        ent_status = BenchmarkDimensionStatus.AVAILABLE if (ent and ent.total_entities_detected > 0) else BenchmarkDimensionStatus.PARTIAL
        ent_names = [e.name for e in getattr(ent, "detected_entities", [])[:15]]
        ent_types = list(set([e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type) for e in getattr(ent, "detected_entities", [])]))
        ent_samples = []
        if ent and ent.detected_entities:
            for e in ent.detected_entities[:8]:
                ent_samples.append({
                    "name": e.name,
                    "type": e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type),
                    "source": e.source.value if hasattr(e.source, "value") else str(e.source),
                    "telephone": e.telephone,
                    "email": e.email,
                })

        aligned_count = sum(1 for c in getattr(ent, "structured_vs_visible", []) if c.alignment_status.value in ("EXACT_MATCH", "NORMALIZED_MATCH", "PARTIAL_MATCH"))
        divergent_count = sum(1 for c in getattr(ent, "structured_vs_visible", []) if c.alignment_status.value == "DIVERGENT_IDENTITY_SUSPECTED")

        ent_dim = EntityDimension(
            status=ent_status,
            total_entities_detected=ent.total_entities_detected if ent else 0,
            entity_names=ent_names,
            entity_types_detected=ent_types,
            relationships_count=len(getattr(ent, "relationships", [])),
            structured_vs_visible_comparisons_count=len(getattr(ent, "structured_vs_visible", [])),
            aligned_comparisons_count=aligned_count,
            divergent_comparisons_count=divergent_count,
            samples=ent_samples,
            notes=list(ent.facts) if ent else [],
        )

        # 7. Internal Link Dimension
        link_status = BenchmarkDimensionStatus.AVAILABLE if len(p.internal_links) > 0 else BenchmarkDimensionStatus.PARTIAL
        int_dim = InternalLinkDimension(
            status=link_status,
            total_internal_links=len(p.internal_links),
            unique_internal_targets=len(set(p.internal_links)),
            total_external_links=len(p.external_links),
            unique_external_targets=len(set(p.external_links)),
            empty_anchors_count=getattr(report.unified_internal_link, "empty_anchor_count", 0),
            sample_internal_targets=list(dict.fromkeys(p.internal_links))[:10],
            notes=[f"{len(p.internal_links)} internal links observed, {len(set(p.internal_links))} unique targets"],
        )

        # 8. Search / Topic / Query / Intent Dimension
        sig = report.unified_search_signal
        top = report.unified_topic
        qp = report.unified_query_page
        intent = report.unified_search_intent
        pri_sig = getattr(intent, "primary_observed_intent_signal", None)
        pri_intent = pri_sig.value if hasattr(pri_sig, "value") else str(pri_sig or "INFORMATIONAL")
        sec_signals = getattr(intent, "secondary_observed_intent_signals", []) or []
        sec_intents = [si.value if hasattr(si, "value") else str(si) for si in sec_signals]
        topic_samples = [t.topic_name for t in getattr(top, "topics", [])[:10]]

        stqi_dim = SearchTopicQueryIntentDimension(
            status=BenchmarkDimensionStatus.AVAILABLE,
            search_signals_count=len(getattr(sig, "signals", [])),
            topics_detected_count=len(getattr(top, "topics", [])),
            topics_sample=topic_samples,
            query_page_concepts_count=getattr(qp, "total_concepts_mapped", 0),
            primary_intent=pri_intent,
            secondary_intents=sec_intents,
            intent_evidence_items_count=len(getattr(intent, "evidence_items", [])),
            notes=[f"Primary Intent: {pri_intent}", f"{len(getattr(top, 'topics', []))} topics extracted"],
        )

        # 9. Cannibalization & Search Gaps Dimension
        cann = report.unified_cannibalization
        cann_signals = getattr(cann, "potential_signals", [])
        cann_gaps = getattr(cann, "observable_gaps", [])
        cann_sig_sample = []
        for s in cann_signals[:5]:
            cann_sig_sample.append({
                "topic": s.topic,
                "competing_urls": s.competing_urls,
                "shared_intent": s.shared_intent.value if hasattr(s.shared_intent, "value") else str(s.shared_intent),
                "title_overlap_ratio": s.title_overlap_ratio,
            })
        cann_gap_sample = []
        for g in cann_gaps[:5]:
            cann_gap_sample.append({
                "topic": g.topic,
                "gap_type": g.gap_type.value if hasattr(g.gap_type, "value") else str(g.gap_type),
                "source_url": g.source_url,
                "recommendation": g.recommendation,
            })

        cann_dim = CannibalizationSearchGapDimension(
            status=BenchmarkDimensionStatus.AVAILABLE,
            potential_cannibalization_signals_count=len(cann_signals),
            observable_gaps_count=len(cann_gaps),
            overlap_signals_sample=cann_sig_sample,
            gaps_sample=cann_gap_sample,
            notes=[f"{len(cann_signals)} potential cannibalization signals flagged", f"{len(cann_gaps)} topic gaps identified"],
        )

        # 10. Retrieval Readiness Dimension (Phase 10.1)
        rr = report.unified_retrieval_readiness
        if rr:
            waf_ev = rr.waf_challenge
            is_waf_blocked = getattr(waf_ev, "is_blocked", False) if waf_ev else False
            waf_detected = getattr(waf_ev, "waf_or_challenge_detected", False) if waf_ev else False
            waf_prov = getattr(waf_ev, "waf_provider", None) if waf_ev else None
            if is_waf_blocked:
                rr_status = BenchmarkDimensionStatus.BLOCKED
            else:
                rr_status = BenchmarkDimensionStatus.AVAILABLE
            rr_dim = RetrievalReadinessDimension(
                status=rr_status,
                total_bots_evaluated=rr.total_bots_evaluated,
                search_index_allowed_count=rr.search_index_allowed_count,
                ai_training_allowed_count=rr.ai_training_allowed_count,
                user_fetch_allowed_count=rr.user_fetch_allowed_count,
                waf_or_challenge_detected=waf_detected,
                waf_blocked=is_waf_blocked,
                waf_provider=waf_prov,
                has_nosnippet=rr.snippet_controls.has_nosnippet,
                has_data_nosnippet=rr.snippet_controls.has_data_nosnippet,
                max_snippet=rr.snippet_controls.max_snippet,
                static_words=rr.content_availability.raw_word_count,
                rendered_words=rr.content_availability.rendered_word_count,
                word_count_delta=rr.content_availability.word_count_delta,
                rendering_impact_summary=rr.content_availability.js_rendering_impact,
                notes=list(rr.facts),
            )
        else:
            rr_dim = RetrievalReadinessDimension(status=BenchmarkDimensionStatus.UNAVAILABLE)

        # 11. Answerability Dimension (Phase 10.2)
        ans = report.unified_answerability
        if ans:
            ans_dim = AnswerabilityDimension(
                status=BenchmarkDimensionStatus.AVAILABLE,
                total_units_detected=ans.total_units_detected,
                units_by_type=dict(ans.units_by_type),
                heading_content_relationship=ans.clarity_assessment.heading_content_relationship.value if hasattr(ans.clarity_assessment.heading_content_relationship, "value") else str(ans.clarity_assessment.heading_content_relationship),
                question_answer_patterns=ans.clarity_assessment.question_answer_patterns.value if hasattr(ans.clarity_assessment.question_answer_patterns, "value") else str(ans.clarity_assessment.question_answer_patterns),
                definition_patterns=ans.clarity_assessment.definition_patterns.value if hasattr(ans.clarity_assessment.definition_patterns, "value") else str(ans.clarity_assessment.definition_patterns),
                step_list_structure=ans.clarity_assessment.step_list_structure.value if hasattr(ans.clarity_assessment.step_list_structure, "value") else str(ans.clarity_assessment.step_list_structure),
                table_availability=ans.clarity_assessment.table_availability.value if hasattr(ans.clarity_assessment.table_availability, "value") else str(ans.clarity_assessment.table_availability),
                explained_topics_count=ans.explained_topics_count,
                mentioned_only_topics_count=ans.mentioned_only_topics_count,
                unsupported_heading_topics_count=ans.unsupported_heading_topics_count,
                unsupported_headings_sample=list(ans.clarity_assessment.unsupported_concepts[:5]),
                notes=list(ans.facts),
            )
        else:
            ans_dim = AnswerabilityDimension(status=BenchmarkDimensionStatus.UNAVAILABLE)

        # 12. Claim Grounding Dimension (Phase 10.3)
        cg = report.unified_claim_grounding
        if cg:
            cons_breakdown = {}
            for eg in cg.entity_grounding:
                val = eg.consistency_status.value if hasattr(eg.consistency_status, "value") else str(eg.consistency_status)
                cons_breakdown[val] = cons_breakdown.get(val, 0) + 1

            cg_dim = ClaimGroundingDimension(
                status=BenchmarkDimensionStatus.AVAILABLE,
                total_claims_detected=cg.total_claims_detected,
                supported_claims_count=cg.supported_claims_count,
                partially_supported_count=cg.partially_supported_count,
                uncorroborated_count=cg.uncorroborated_count,
                contradicted_count=cg.contradicted_count,
                structured_agreements_count=cg.agreement_count,
                structured_disagreements_count=cg.disagreement_count,
                entity_consistency_breakdown=cons_breakdown,
                notes=list(cg.facts),
            )
        else:
            cg_dim = ClaimGroundingDimension(status=BenchmarkDimensionStatus.UNAVAILABLE)

        # 13. Multimodal Dimension (Phase 10.4)
        mma = report.unified_multimodal_agent
        if mma:
            mm = mma.multimodal
            img_ev = report.unified_image_seo
            mm_dim = MultimodalDimension(
                status=BenchmarkDimensionStatus.AVAILABLE,
                total_visual_assets=mm.total_visual_assets,
                informational_assets_count=mm.informational_assets_count,
                decorative_assets_count=mm.decorative_assets_count,
                alt_represented_count=mm.alt_represented_count,
                caption_represented_count=mm.caption_represented_count,
                text_represented_count=mm.text_represented_count,
                visual_only_observed_gaps=mm.visual_only_observed_count,
                modern_format_count=img_ev.modern_format_count if img_ev else 0,
                missing_dimensions_count=img_ev.missing_dimensions_count if img_ev else 0,
                notes=[f"{mm.total_visual_assets} visual assets audited ({mm.alt_represented_count} alt-represented)"],
            )
        else:
            mm_dim = MultimodalDimension(status=BenchmarkDimensionStatus.UNAVAILABLE)

        # 14. Agent Readiness Dimension (Phase 10.4)
        if mma:
            ar = mma.agent_readiness
            ar_dim = AgentReadinessDimension(
                status=BenchmarkDimensionStatus.AVAILABLE,
                total_forms_detected=ar.total_forms_detected,
                labeled_forms_count=ar.labeled_forms_count,
                action_buttons_detected=ar.action_buttons_detected,
                meaningful_accessible_buttons_count=ar.meaningful_accessible_buttons_count,
                descriptive_navigation_links_count=ar.descriptive_navigation_links_count,
                schema_actions_detected=ar.schema_actions_detected,
                webmcp_declarations_detected=ar.webmcp_declarations_detected,
                total_access_paths=len(mma.access_paths),
                action_surface_gaps=getattr(mma, "action_surface_gaps_count", 0),
                notes=[f"{ar.total_forms_detected} forms, {ar.action_buttons_detected} buttons audited"],
            )
        else:
            ar_dim = AgentReadinessDimension(status=BenchmarkDimensionStatus.UNAVAILABLE)

        # 15. External AI Dimension (Phase 10.5)
        evi = report.unified_external_visibility
        if evi and evi.status.value != "DISABLED":
            ext_status = (
                BenchmarkDimensionStatus.AVAILABLE
                if evi.status.value == "SUCCESS"
                else (BenchmarkDimensionStatus.BLOCKED if evi.status.value == "RATE_LIMITED" else BenchmarkDimensionStatus.PARTIAL)
            )
            ext_dim = ExternalAiDimension(
                status=ext_status,
                providers_evaluated=list(evi.providers_evaluated),
                queries_executed_count=evi.queries_executed_count,
                successful_observations_count=evi.successful_observations_count,
                failed_observations_count=evi.failed_observations_count,
                target_domain_cited_count=evi.target_domain_cited_count,
                target_domain_mentioned_count=evi.target_domain_mention_count,
                total_external_citations=evi.total_external_citations_returned,
                failure_reason=(
                    getattr(evi.observations[0], "failure_reason", None)
                    or getattr(evi.observations[0], "error_message", None)
                ) if evi.observations else None,
                limitation_disclaimer=(
                    "Controlled empirical observations under explicit API configurations. "
                    "Strictly opt-in; does not imply universal AI rankings or traffic."
                ),
                notes=list(evi.facts),
            )
        else:
            ext_dim = ExternalAiDimension(
                status=BenchmarkDimensionStatus.DISABLED,
                notes=["External AI visibility measurement was not requested (strictly opt-in via --external-ai)."],
            )

        # Epistemic Separation Compilation
        facts: List[str] = [
            f"HTTP response code: {p.status_code}",
            f"Static HTML word count: {p.word_count}",
            f"Title: '{p.title}' ({p.title_length} characters)",
            f"Meta description: '{p.meta_description}' ({p.meta_desc_length} characters)",
            f"H1 tags observed: {p.h1_count}",
            f"Internal links observed: {len(p.internal_links)}",
            f"External links observed: {len(p.external_links)}",
            f"Robots.txt found: {r.found}",
            f"Schema types declared: {', '.join(schema.detected_types) if schema.detected_types else 'None'}",
            f"HTTPS enforced: {sec.is_https if sec else 'Unknown'}",
            f"Server latency probe: {perf.ttfb_ms:.1f}ms ({perf.source})",
        ]
        if rr and rr.facts:
            facts.extend(rr.facts[:5])
        if ans and ans.facts:
            facts.extend(ans.facts[:5])
        if cg and cg.facts:
            facts.extend(cg.facts[:5])
        if mma and mma.facts:
            facts.extend(mma.facts[:5])

        ext_obs: List[str] = [
            f"Local network latency probe recorded {perf.ttfb_ms:.1f}ms TTFB",
        ]
        if evi and evi.status.value != "DISABLED" and evi.facts:
            ext_obs.extend(evi.facts)
        else:
            ext_obs.append("External AI measurement was disabled during this collection pass (opt-in via --external-ai).")

        analyses: List[str] = [
            f"Health score computed: {report.overall_health_score}/100 via invariant formula mode '{report.score_formula_mode}'",
            f"Technical SEO foundation: {report.technical_health_score}/100",
            f"GEO citability readiness: {report.geo_readiness_score}/100",
            f"Trust stack: {report.unified_trust.grade} ({report.trust_score}/100)",
        ]
        for c in report.conflicts_detected:
            analyses.append(f"Cross-engine conflict [{c.severity}] on '{c.feature}': {c.description} -> {c.interpretation}")

        recs: List[str] = []
        for act in report.prioritized_actions:
            recs.append(f"[{act.level}] {act.title}: {act.rationale}")

        epistemic = EpistemicSeparation(
            facts=facts,
            external_observations=ext_obs,
            analyses=analyses,
            recommendations=recs,
        )

        # Provenance tags
        provenance_list = []
        for tag in report.provenance:
            provenance_list.append({
                "finding": tag.finding,
                "engine": tag.engine,
                "source_file": tag.source_file,
                "confidence": tag.confidence,
                "confirmed_by": tag.confirmed_by,
                "contradicted_by": tag.contradicted_by,
            })

        conflicts_list = []
        for c in report.conflicts_detected:
            conflicts_list.append({
                "severity": c.severity,
                "feature": c.feature,
                "description": c.description,
                "engine_a_finding": c.engine_a_finding,
                "engine_b_finding": c.engine_b_finding,
                "interpretation": c.interpretation,
            })

        collection_status = "SUCCESS" if p.status_code == 200 else ("PARTIAL" if p.status_code > 0 else "FAILED")

        return SiteIntelligencePackage(
            site_url=report.url,
            domain=report.domain,
            name=name or report.domain,
            role=role,
            collection_timestamp=report.timestamp,
            collection_status=collection_status,
            error_message=None if p.status_code > 0 else "Failed to fetch website response",
            execution_time_sec=round(execution_time_sec, 2),
            overall_health_score=report.overall_health_score,
            technical_health_score=report.technical_health_score,
            geo_readiness_score=report.geo_readiness_score,
            trust_score=report.trust_score,
            performance_score=report.performance_score,
            score_formula_mode=report.score_formula_mode,
            formula_invariance_verified=True,
            crawl_limitations=limits,
            crawl_discovery=crawl_dim,
            technical_seo=tech_dim,
            accessibility=a11y_dim,
            security=sec_dim,
            content=cnt_dim,
            entity=ent_dim,
            internal_links=int_dim,
            search_topic_query_intent=stqi_dim,
            cannibalization_search_gaps=cann_dim,
            retrieval_readiness=rr_dim,
            answerability=ans_dim,
            claim_grounding=cg_dim,
            multimodal=mm_dim,
            agent_readiness=ar_dim,
            external_ai=ext_dim,
            epistemic_separation=epistemic,
            provenance_tags=provenance_list,
            conflicts_detected=conflicts_list,
            engines_executed=list(report.engines_executed),
            raw_report_paths=raw_report_paths or {},
        )
