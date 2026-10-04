"""
RankIntel FastMCP Server — Exposes multi-engine SEO, GEO, and competitive intelligence tools.
Can be invoked by Claude, Cursor, Antigravity, or any standard MCP client.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
try:
    from fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        class FastMCP:  # type: ignore
            def __init__(self, name: str = "rankintel", *args, **kwargs):
                self.name = name

            def tool(self, func=None):
                if func is None:
                    return lambda f: f
                return func

            def run(self, *args, **kwargs):
                pass

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.intelligence.comparer import IntelligenceComparer

mcp = FastMCP("rankintel", instructions="RankIntel Multi-Engine Search Intelligence & GEO Server")

@mcp.tool
def rankintel_audit(
    url: str,
    deep_crawl: bool = False,
    max_pages: int = 25,
    external_ai: bool = False,
    external_providers: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run full multi-engine SEO, GEO citability, Trust Stack, and CWV performance audit on a URL.
    Optionally crawls internal site pages for site-wide issues.
    Optionally enables controlled external AI visibility observations via external_ai=True.
    """
    if not url.startswith("http"):
        url = "https://" + url

    providers_list = [p.strip() for p in external_providers.split(",")] if external_providers else None

    collector = EvidenceCollector(
        enable_external_visibility=external_ai,
        external_providers=providers_list,
    )
    results = collector.collect(
        url,
        enable_external_visibility=external_ai,
        external_providers=providers_list,
    )

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize(url, results)

    if deep_crawl:
        report.site_crawl = collector.seo_engine.crawl_site(url, max_pages=max_pages)

    return {
        "url": report.url,
        "domain": report.domain,
        "timestamp": report.timestamp,
        "overall_health_score": report.overall_health_score,
        "technical_health_score": report.technical_health_score,
        "geo_readiness_score": report.geo_readiness_score,
        "trust_score": report.trust_score,
        "trust_grade": report.unified_trust.grade,
        "performance_score": report.performance_score,
        "ttfb_ms": report.unified_performance.ttfb_ms,
        "llms_txt_present": report.unified_geo.llms_txt_found,
        "engines_executed": report.engines_executed,
        "conflicts_detected": [c.model_dump() for c in report.conflicts_detected],
        "top_prioritized_actions": [a.model_dump() for a in report.prioritized_actions[:5]],
        "provenance_chain": [p.model_dump() for p in report.provenance],
        "production_fixes": report.fixes,
        "site_crawl_summary": report.site_crawl.model_dump() if report.site_crawl else None,
        "security_status": report.unified_security.overall_status.value if report.unified_security else "UNKNOWN",
        "security_findings_count": report.unified_security.total_findings if report.unified_security else 0,
        "accessibility_status": report.unified_accessibility.wcag_aa_status.value if report.unified_accessibility else "UNKNOWN",
        "accessibility_violations_count": report.unified_accessibility.total_violations if report.unified_accessibility else 0,
        "image_seo_total_images": report.unified_image_seo.total_images if report.unified_image_seo else 0,
        "image_seo_missing_alt": report.unified_image_seo.missing_alt_count if report.unified_image_seo else 0,
        "content_main_word_count": report.unified_content.main_content_word_count if report.unified_content else 0,
        "entities_detected_count": report.unified_entity.total_entities_detected if report.unified_entity else 0,
        "internal_links_total": report.unified_internal_link.internal_links_count if report.unified_internal_link else 0,
        "internal_links_unique": report.unified_internal_link.unique_internal_outlinks_count if report.unified_internal_link else 0,
        "internal_links_empty_anchors": report.unified_internal_link.empty_anchor_count if report.unified_internal_link else 0,
        "internal_links_generic_anchors": report.unified_internal_link.generic_anchor_count if report.unified_internal_link else 0,
        "search_signals_total": report.unified_search_signal.total_signals_detected if report.unified_search_signal else 0,
        "search_signal_top_terms": [s.term for s in report.unified_search_signal.signals[:5]] if (report.unified_search_signal and report.unified_search_signal.signals) else [],
        "site_recurring_concepts_count": report.site_crawl.search_signal_intelligence.recurring_concepts_count if (report.site_crawl and report.site_crawl.search_signal_intelligence) else 0,
        "topics_derived_count": report.unified_topic.total_topics_derived if report.unified_topic else 0,
        "top_topics": [t.topic_name for t in report.unified_topic.topics[:5]] if (report.unified_topic and report.unified_topic.topics) else [],
        "site_recurring_topics_count": report.site_crawl.topic_intelligence.recurring_topics_count if (report.site_crawl and report.site_crawl.topic_intelligence) else 0,
        "query_page_concepts_mapped_count": report.unified_query_page.total_concepts_mapped if report.unified_query_page else 0,
        "query_page_direct_concepts_count": report.unified_query_page.direct_concepts_count if report.unified_query_page else 0,
        "site_multi_page_overlaps_count": report.site_crawl.query_page_intelligence.multi_page_overlap_count if (report.site_crawl and report.site_crawl.query_page_intelligence) else 0,
        "search_intent_primary": report.unified_search_intent.primary_observed_intent_signal.value if report.unified_search_intent else "unspecified",
        "search_intent_signals_count": len(report.unified_search_intent.evidence_items) if report.unified_search_intent else 0,
        "site_topics_covered_count": report.site_crawl.topic_coverage_intelligence.total_topics_covered if (report.site_crawl and report.site_crawl.topic_coverage_intelligence) else 0,
        "potential_cannibalization_signals_count": len(report.site_crawl.cannibalization_intelligence.potential_cannibalization_signals) if (report.site_crawl and report.site_crawl.cannibalization_intelligence) else (len(report.unified_cannibalization.potential_signals) if report.unified_cannibalization else 0),
        "observable_topic_gaps_count": len(report.site_crawl.cannibalization_intelligence.observable_topic_gaps) if (report.site_crawl and report.site_crawl.cannibalization_intelligence) else (len(report.unified_cannibalization.observable_gaps) if report.unified_cannibalization else 0),
        "retrieval_search_indexers_allowed": report.unified_retrieval_readiness.search_index_allowed_count if report.unified_retrieval_readiness else 0,
        "retrieval_training_scrapers_allowed": report.unified_retrieval_readiness.ai_training_allowed_count if report.unified_retrieval_readiness else 0,
        "retrieval_user_fetchers_allowed": report.unified_retrieval_readiness.user_fetch_allowed_count if report.unified_retrieval_readiness else 0,
        "retrieval_waf_blocked": report.unified_retrieval_readiness.waf_challenge.is_blocked if report.unified_retrieval_readiness else False,
        "retrieval_snippet_status": report.unified_retrieval_readiness.snippet_controls.status.value if report.unified_retrieval_readiness else "ALLOWED",
        "answerability_units_detected": report.unified_answerability.total_units_detected if report.unified_answerability else 0,
        "answerability_units_by_type": report.unified_answerability.units_by_type if report.unified_answerability else {},
        "answerability_explained_topics_count": report.unified_answerability.explained_topics_count if report.unified_answerability else 0,
        "answerability_clarity_qa_status": report.unified_answerability.clarity_assessment.question_answer_patterns.value if report.unified_answerability else "UNAVAILABLE",
        "answerability_clarity_definitions_status": report.unified_answerability.clarity_assessment.definition_patterns.value if report.unified_answerability else "UNAVAILABLE",
        "claim_grounding_total_claims": report.unified_claim_grounding.total_claims_detected if report.unified_claim_grounding else 0,
        "claim_grounding_supported_count": report.unified_claim_grounding.supported_claims_count if report.unified_claim_grounding else 0,
        "claim_grounding_partially_supported_count": report.unified_claim_grounding.partially_supported_count if report.unified_claim_grounding else 0,
        "claim_grounding_uncorroborated_count": report.unified_claim_grounding.uncorroborated_count if report.unified_claim_grounding else 0,
        "claim_grounding_contradicted_count": report.unified_claim_grounding.contradicted_count if report.unified_claim_grounding else 0,
        "claim_grounding_agreements_count": report.unified_claim_grounding.agreement_count if report.unified_claim_grounding else 0,
        "claim_grounding_disagreements_count": report.unified_claim_grounding.disagreement_count if report.unified_claim_grounding else 0,
        "claim_grounding_entity_candidates_count": len(report.unified_claim_grounding.entity_grounding) if report.unified_claim_grounding else 0,
        "multimodal_total_assets": report.unified_multimodal_agent.multimodal.total_visual_assets if report.unified_multimodal_agent else 0,
        "multimodal_informational_count": report.unified_multimodal_agent.multimodal.informational_assets_count if report.unified_multimodal_agent else 0,
        "multimodal_alt_represented_count": report.unified_multimodal_agent.multimodal.alt_represented_count if report.unified_multimodal_agent else 0,
        "multimodal_caption_represented_count": report.unified_multimodal_agent.multimodal.caption_represented_count if report.unified_multimodal_agent else 0,
        "multimodal_visual_only_gaps": report.unified_multimodal_agent.multimodal.visual_only_observed_count if report.unified_multimodal_agent else 0,
        "agent_total_forms": report.unified_multimodal_agent.agent_readiness.total_forms_detected if report.unified_multimodal_agent else 0,
        "agent_labeled_forms_count": report.unified_multimodal_agent.agent_readiness.labeled_forms_count if report.unified_multimodal_agent else 0,
        "agent_action_buttons_count": report.unified_multimodal_agent.agent_readiness.action_buttons_detected if report.unified_multimodal_agent else 0,
        "agent_schema_actions_count": report.unified_multimodal_agent.agent_readiness.schema_actions_detected if report.unified_multimodal_agent else 0,
        "agent_webmcp_declarations_count": report.unified_multimodal_agent.agent_readiness.webmcp_declarations_detected if report.unified_multimodal_agent else 0,
        "access_paths_total_count": len(report.unified_multimodal_agent.access_paths) if report.unified_multimodal_agent else 0,
        "access_paths_structured_sample": [p.model_dump() for p in report.unified_multimodal_agent.access_paths[:5]] if report.unified_multimodal_agent else [],
        "agent_interaction_surfaces_sample": [s.model_dump() for s in report.unified_multimodal_agent.agent_readiness.surfaces[:5]] if report.unified_multimodal_agent else [],
        "external_visibility_status": report.unified_external_visibility.status.value if report.unified_external_visibility else "DISABLED",
        "external_observations_completed": report.unified_external_visibility.successful_observations_count if report.unified_external_visibility else 0,
        "external_target_domain_cited_count": report.unified_external_visibility.target_domain_cited_count if report.unified_external_visibility else 0,
        "external_target_domain_mentioned_count": report.unified_external_visibility.target_domain_mention_count if report.unified_external_visibility else 0,
        "external_observations_sample": [o.model_dump() for o in report.unified_external_visibility.observations[:3]] if report.unified_external_visibility else [],
    }

@mcp.tool
def rankintel_compare(url_a: str, url_b: str) -> Dict[str, Any]:
    """
    Run competitive gap analysis benchmarking two websites head-to-head.
    Identifies competitive advantage, category score deltas, and strategic remediation steps.
    """
    comparer = IntelligenceComparer()
    comparison = comparer.compare(url_a, url_b)

    return {
        "target_a_url": comparison.target_a_url,
        "target_b_url": comparison.target_b_url,
        "winner_url": comparison.winner_url,
        "score_gap": comparison.score_gap,
        "target_a_score": comparison.target_a_report.overall_health_score,
        "target_b_score": comparison.target_b_report.overall_health_score,
        "category_deltas": [d.model_dump() for d in comparison.category_deltas],
        "action_plan": [a.model_dump() for a in comparison.action_plan]
    }

@mcp.tool
def rankintel_generate_fixes(url: str) -> Dict[str, str]:
    """
    Generate drop-in production code fixes for a URL:
    optimized Title/Meta Description, JSON-LD @graph structured data, /llms.txt, and hardened robots.txt.
    """
    if not url.startswith("http"):
        url = "https://" + url

    collector = EvidenceCollector()
    results = collector.collect(url)
    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize(url, results)

    return report.fixes

def run_server():
    """Run MCP server via stdio transport."""
    mcp.run()

if __name__ == "__main__":
    run_server()
