"""
Evidence Provenance Tagger — Tracks the source engine, file origin,
confidence, and cross-engine confirmation/contradiction for each finding.
"""
from __future__ import annotations
from typing import Dict, List
from rankintel.models.schema import EngineResult, EvidenceProvenanceTag

class ProvenanceTagger:
    """Attaches source attribution and cross-engine agreement to key SEO/GEO/Trust findings."""

    @staticmethod
    def tag(engine_results: Dict[str, EngineResult]) -> List[EvidenceProvenanceTag]:
        tags: List[EvidenceProvenanceTag] = []
        seo = engine_results.get("advertools_seo")
        browser = engine_results.get("browser_engine")
        geo = engine_results.get("rankintel_geo")
        perf = engine_results.get("performance_engine")

        # 1. robots.txt findings
        if seo and seo.robots and seo.robots.found:
            for bot, status in seo.robots.bot_access.items():
                tags.append(EvidenceProvenanceTag(
                    finding=f"{bot}: {status.status}",
                    source_file="robots.txt",
                    engine="seo_engine",
                    evidence_snippet=f"User-agent: {bot} -> {status.status}",
                    confidence="high",
                    confirmed_by=[],
                    contradicted_by=[]
                ))

        # 2. Schema detection — cross-engine confirmation vs JS injection
        if seo and seo.schema_data and browser and browser.schema_data:
            static_types = set(seo.schema_data.detected_types)
            browser_types = set(browser.schema_data.detected_types)
            confirmed = sorted(list(static_types & browser_types))
            js_only = sorted(list(browser_types - static_types))

            for t in confirmed:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Schema type '{t}' detected",
                    source_file="application/ld+json",
                    engine="seo_engine",
                    confidence="high",
                    confirmed_by=["browser_engine"]
                ))
            for t in js_only:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Schema type '{t}' is JS-injected (invisible to static crawlers)",
                    source_file="DOM (JavaScript)",
                    engine="browser_engine",
                    confidence="high",
                    contradicted_by=["seo_engine"]
                ))
        elif seo and seo.schema_data:
            for t in seo.schema_data.detected_types:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Schema type '{t}' detected in raw HTML",
                    source_file="application/ld+json",
                    engine="seo_engine",
                    confidence="high"
                ))

        # 3. Heading and Title structure
        if seo and seo.on_page:
            tags.append(EvidenceProvenanceTag(
                finding=f"Page Title ({seo.on_page.title_length} chars): '{seo.on_page.title[:45]}...'",
                source_file="<title> tag",
                engine="seo_engine",
                confidence="high",
                confirmed_by=["browser_engine"] if (browser and browser.on_page and browser.on_page.title == seo.on_page.title) else []
            ))
            if browser and browser.on_page and browser.on_page.title and browser.on_page.title != seo.on_page.title:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Rendered Title differs from Static Title",
                    source_file="DOM (hydration)",
                    engine="browser_engine",
                    confidence="high",
                    contradicted_by=["seo_engine"]
                ))

        # 4. TTFB & Performance Telemetry
        if perf and perf.performance:
            tags.append(EvidenceProvenanceTag(
                finding=f"TTFB Latency: {perf.performance.ttfb_ms:.0f}ms",
                source_file="HTTP response probe",
                engine="performance_engine",
                evidence_snippet=f"Telemetry Source: {perf.performance.source}",
                confidence="high" if perf.performance.source.startswith("pagespeed") else "medium"
            ))

        # 5. GEO & llms.txt provenance
        if geo and geo.geo_aeo:
            found = geo.geo_aeo.llms_txt_found
            tags.append(EvidenceProvenanceTag(
                finding=f"/llms.txt: {'PRESENT' if found else 'MISSING'}",
                source_file="/llms.txt HTTP check",
                engine="rankintel_geo",
                confidence="high"
            ))
            tags.append(EvidenceProvenanceTag(
                finding=f"Princeton GEO Citability: {geo.geo_aeo.overall_citability_score}/100",
                source_file="DOM content passages",
                engine="rankintel_geo",
                confidence="high"
            ))

        # 6. Cloud Intelligence provenance (OpenSEO MCP)
        mcp = engine_results.get("mcp_cloud")
        if mcp and mcp.cloud_intelligence and mcp.cloud_intelligence.available:
            if mcp.cloud_intelligence.keywords:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Organic Search Traffic: {mcp.cloud_intelligence.keywords.estimated_monthly_traffic:,} visits/mo",
                    source_file="OpenSEO MCP (DataForSEO)",
                    engine="mcp_cloud",
                    evidence_snippet=f"{mcp.cloud_intelligence.keywords.total_keywords} total keywords tracked",
                    confidence="high"
                ))
            if mcp.cloud_intelligence.backlinks:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Referring Domains: {mcp.cloud_intelligence.backlinks.referring_domains}",
                    source_file="OpenSEO MCP (DataForSEO)",
                    engine="mcp_cloud",
                    evidence_snippet=f"Authority score: {mcp.cloud_intelligence.backlinks.domain_authority_score}",
                    confidence="high"
                ))

        # 7. Image SEO findings (Phase 7.1)
        img_res = engine_results.get("image_engine")
        if img_res and img_res.image_seo and img_res.status == "success":
            img = img_res.image_seo
            tags.append(EvidenceProvenanceTag(
                finding=f"Image Optimization: {img.total_images} images detected ({img.missing_alt_count} missing alt)",
                source_file="HTML DOM",
                engine="image_engine",
                evidence_snippet=f"{img.modern_format_count} modern formats, {img.missing_dimensions_count} layout shift risks",
                confidence="high"
            ))
            if img.head_audit:
                head = img.head_audit
                tags.append(EvidenceProvenanceTag(
                    finding=f"HTML Head Audit: Viewport {'Present' if head.viewport_present else 'Missing'}, Lang {'Present' if head.lang_present else 'Missing'}",
                    source_file="<head> HTML",
                    engine="image_engine",
                    evidence_snippet=f"Heading valid: {head.heading_hierarchy_valid}",
                    confidence="high"
                ))

        # 8. Accessibility findings (Phase 7.2)
        a11y_res = engine_results.get("accessibility_engine")
        if a11y_res and a11y_res.accessibility and a11y_res.status == "success":
            a11y = a11y_res.accessibility
            tags.append(EvidenceProvenanceTag(
                finding=f"WCAG AA Automated Status: {a11y.wcag_aa_status.value} ({a11y.total_violations} violations)",
                source_file="HTML DOM",
                engine=a11y.engine_source or "accessibility_engine",
                evidence_snippet=f"Critical: {a11y.critical_count}, Serious: {a11y.serious_count}, Moderate: {a11y.moderate_count}",
                confidence="high" if a11y.browser_evaluated else "medium"
            ))

        # 9. Security findings (Phase 7.3)
        sec_res = engine_results.get("security_engine")
        if sec_res and sec_res.security and sec_res.status == "success":
            sec = sec_res.security
            tags.append(EvidenceProvenanceTag(
                finding=f"Security Posture Status: {sec.overall_status.value} ({sec.total_findings} findings)",
                source_file="HTTP Headers / TLS",
                engine="security_engine",
                evidence_snippet=f"HSTS: {'Yes' if sec.hsts_present else 'No'}, CSP: {'Yes' if sec.csp_present else 'No'}",
                confidence="high"
            ))
            if sec.tls_details and sec.tls_details.is_valid:
                tls = sec.tls_details
                days = f"{tls.days_until_expiration} days left" if tls.days_until_expiration is not None else "valid"
                tags.append(EvidenceProvenanceTag(
                    finding=f"TLS Certificate: Valid ({days})",
                    source_file="TLS Handshake",
                    engine="security_engine",
                    evidence_snippet=f"Protocol: {tls.protocol_version or 'N/A'}",
                    confidence="high"
                ))

        # 10. Content findings (Phase 8.1)
        cnt_res = engine_results.get("content_engine")
        if cnt_res and cnt_res.content and cnt_res.status == "success":
            cnt = cnt_res.content
            tags.append(EvidenceProvenanceTag(
                finding=f"Main Content Extraction: {cnt.main_content_word_count} words ({cnt.extraction_method.value})",
                source_file="HTML DOM",
                engine="content_engine",
                evidence_snippet=f"Exact Hash: {cnt.exact_content_hash[:12]}..., SimHash: {cnt.simhash[:8]}...",
                confidence="high"
            ))
            if cnt.heading_structure:
                h = cnt.heading_structure
                status_str = "Valid hierarchy" if h.heading_hierarchy_valid else f"{len(h.heading_skips)} skips"
                tags.append(EvidenceProvenanceTag(
                    finding=f"Heading Structure: {h.total_headings} headings ({status_str})",
                    source_file="HTML Headings",
                    engine="content_engine",
                    evidence_snippet=f"H1: {h.h1_count}, H2: {h.h2_count}, H3: {h.h3_count}",
                    confidence="high"
                ))

        # 11. Entity findings (Phase 8.2)
        ent_res = engine_results.get("entity_engine")
        if ent_res and ent_res.entity and ent_res.status == "success":
            ent_ev = ent_res.entity
            if ent_ev.detected_entities:
                org_count = sum(1 for e in ent_ev.detected_entities if e.entity_type.value in ("ORGANIZATION", "LOCAL_BUSINESS"))
                tags.append(EvidenceProvenanceTag(
                    finding=f"Entity Detection: {len(ent_ev.detected_entities)} entity signals ({org_count} organization/business)",
                    source_file="JSON-LD & HTML DOM",
                    engine="entity_engine",
                    evidence_snippet=f"Entities: {', '.join([e.name for e in ent_ev.detected_entities[:3]])}...",
                    confidence="high"
                ))
            if ent_ev.structured_vs_visible:
                for comp in ent_ev.structured_vs_visible:
                    tags.append(EvidenceProvenanceTag(
                        finding=f"Entity Alignment ({comp.attribute_name}): {comp.alignment_status.value}",
                        source_file="JSON-LD vs DOM Signals",
                        engine="entity_engine",
                        evidence_snippet=f"Structured: '{comp.structured_value}' vs Visible: '{comp.visible_value}'",
                        confidence="high"
                    ))

        # 12. Internal link findings (Phase 8.3)
        link_res = engine_results.get("internal_link_engine")
        if link_res and link_res.internal_link and link_res.status == "success":
            lnk_ev = link_res.internal_link
            tags.append(EvidenceProvenanceTag(
                finding=f"Internal Link Topology: {lnk_ev.internal_links_count} internal links ({lnk_ev.unique_internal_outlinks_count} unique destinations)",
                source_file="HTML DOM",
                engine="internal_link_engine",
                evidence_snippet=f"Total: {lnk_ev.total_links_found}, Nofollow: {lnk_ev.nofollow_links_count}, Empty Anchors: {lnk_ev.empty_anchor_count}",
                confidence="high"
            ))
            if lnk_ev.generic_anchor_count > 0:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Generic Anchor Text: {lnk_ev.generic_anchor_count} generic anchor links observed",
                    source_file="HTML DOM",
                    engine="internal_link_engine",
                    evidence_snippet=f"Generic anchors: {', '.join([g.anchor_text for g in lnk_ev.generic_anchors[:3]])}",
                    confidence="high"
                ))

        # 13. Search Signal findings (Phase 9.1 - Layer A)
        sig_res = engine_results.get("search_signal_engine")
        if sig_res and sig_res.search_signal and sig_res.status == "success":
            sig_ev = sig_res.search_signal
            if sig_ev.signals:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Search Signal Evidence: {sig_ev.total_signals_detected} on-site search-relevant signal terms evidenced",
                    source_file="HTML DOM & Metadata",
                    engine="search_signal_engine",
                    evidence_snippet=f"Top terms: {', '.join([s.term for s in sig_ev.signals[:5]])}",
                    confidence="high"
                ))
            if sig_ev.analyses:
                for an in sig_ev.analyses[:2]:
                    tags.append(EvidenceProvenanceTag(
                        finding=f"Search Signal Structure: {an}",
                        source_file="Structural Tag Correlation",
                        engine="search_signal_engine",
                        evidence_snippet=an,
                        confidence="high"
                    ))

        # 14. Topic Intelligence findings (Phase 9.2 - Layer A)
        topic_res = engine_results.get("topic_intelligence_engine")
        if topic_res and topic_res.topic_intelligence and topic_res.status == "success":
            top_ev = topic_res.topic_intelligence
            if top_ev.topics:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Topic Intelligence: {top_ev.total_topics_derived} deterministic concept groups derived from on-site evidence",
                    source_file="Search Signal & Entity Evidence",
                    engine="topic_intelligence_engine",
                    evidence_snippet=f"Top topics: {', '.join([t.topic_name for t in top_ev.topics[:4]])}",
                    confidence="high"
                ))
            if top_ev.relationships:
                rel0 = top_ev.relationships[0]
                rel0_type = rel0.relationship_type.value if hasattr(rel0.relationship_type, "value") else str(rel0.relationship_type)
                tags.append(EvidenceProvenanceTag(
                    finding=f"Topic Relationships: {len(top_ev.relationships)} inter-topic relationships mapped",
                    source_file="Deterministic Concept Clustering",
                    engine="topic_intelligence_engine",
                    evidence_snippet=f"Sample: {rel0.topic_a} -> {rel0_type} -> {rel0.topic_b}",
                    confidence="high"
                ))

        # 15. Query-Page Mapping findings (Phase 9.3 - Layer A)
        qp_res = engine_results.get("query_page_mapping_engine")
        if qp_res and qp_res.query_page and qp_res.status == "success":
            qp_ev = qp_res.query_page
            if qp_ev.mapped_concepts:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Query-Page Mapping: {qp_ev.total_concepts_mapped} observed concepts mapped to page ({qp_ev.direct_concepts_count} DIRECT, {qp_ev.supported_concepts_count} SUPPORTED)",
                    source_file="On-Site Evidence Triangulation",
                    engine="query_page_mapping_engine",
                    evidence_snippet=f"Primary concepts: {', '.join(qp_ev.primary_concepts[:4]) if qp_ev.primary_concepts else 'None'}",
                    confidence="high"
                ))
            if qp_ev.analyses:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Query-Page Evidence Distribution: {qp_ev.analyses[0]}",
                    source_file="Structural Evidence Matrix",
                    engine="query_page_mapping_engine",
                    evidence_snippet=qp_ev.analyses[0],
                    confidence="high"
                ))

        # 16. Search Intent findings (Phase 9.4 - Layer A)
        intent_res = engine_results.get("search_intent_engine")
        if intent_res and intent_res.search_intent and intent_res.status == "success":
            intent_ev = intent_res.search_intent
            pri_val = (
                intent_ev.primary_observed_intent_signal.value
                if hasattr(intent_ev.primary_observed_intent_signal, "value")
                else str(intent_ev.primary_observed_intent_signal)
            )
            tags.append(EvidenceProvenanceTag(
                finding=f"Search Intent Signals: Primary observed intent signal is '{pri_val}' ({len(intent_ev.evidence_items)} observable evidence items)",
                source_file="On-Site Structural Intent Heuristics",
                engine="search_intent_engine",
                evidence_snippet=f"Counts: {intent_ev.intent_counts}",
                confidence="high" if pri_val != "unspecified" else "medium"
            ))
            if intent_ev.analyses:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Search Intent Corroboration: {intent_ev.analyses[0]}",
                    source_file="Multi-Signal Corroboration Engine",
                    engine="search_intent_engine",
                    evidence_snippet=intent_ev.analyses[0],
                    confidence="high"
                ))

        # 17. Cannibalization & Search Gap findings (Phase 9.5 - Layer A)
        cann_res = engine_results.get("cannibalization_analyzer")
        if cann_res and cann_res.cannibalization and cann_res.status == "success":
            cann_ev = cann_res.cannibalization
            if cann_ev.potential_signals:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Cannibalization Intelligence: {len(cann_ev.potential_signals)} potential cannibalization signal(s) flagged",
                    source_file="Multi-Dimensional Signal Gate",
                    engine="cannibalization_analyzer",
                    evidence_snippet=f"Competing topics: {', '.join([s.topic for s in cann_ev.potential_signals[:3]])}",
                    confidence="high"
                ))
            if cann_ev.observable_gaps:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Search Gap Intelligence: {len(cann_ev.observable_gaps)} observable on-site topic gap(s) identified",
                    source_file="Observable Coverage Matrix",
                    engine="search_gap_analyzer",
                    evidence_snippet=f"Gap topics: {', '.join([g.topic for g in cann_ev.observable_gaps[:3]])}",
                    confidence="high"
                ))
            if cann_ev.analyses:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Cannibalization & Gap Observations: {cann_ev.analyses[0]}",
                    source_file="On-Site Evidence Triangulation",
                    engine="cannibalization_analyzer",
                    evidence_snippet=cann_ev.analyses[0][:100],
                    confidence="high"
                ))
        # 18. AI Access & Retrieval Readiness findings (Phase 10.1)
        retrieval_res = engine_results.get("retrieval_readiness_engine")
        if retrieval_res and retrieval_res.retrieval_readiness and retrieval_res.status == "success":
            r_ev = retrieval_res.retrieval_readiness
            tags.append(EvidenceProvenanceTag(
                finding=f"AI Search Retrieval Access: {r_ev.search_index_allowed_count} indexers allowed, {r_ev.ai_training_allowed_count} training scrapers allowed",
                source_file="robots.txt & HTTP Directives",
                engine="retrieval_readiness_engine",
                evidence_snippet=f"WAF status: {'BLOCKED' if r_ev.waf_challenge.is_blocked else 'ALLOWED'}, snippet status: {r_ev.snippet_controls.status.value}",
                confidence="high",
            ))
            if r_ev.snippet_controls.has_nosnippet:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Snippet Suppression: nosnippet present ({', '.join(r_ev.snippet_controls.nosnippet_sources)})",
                    source_file="Meta / X-Robots-Tag",
                    engine="retrieval_readiness_engine",
                    evidence_snippet="nosnippet directive",
                    confidence="high",
                ))
            if r_ev.content_availability.significant_content_difference:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Content Availability Delta: +{r_ev.content_availability.word_count_delta} words in rendered DOM",
                    source_file="DOM (hydration comparison)",
                    engine="retrieval_readiness_engine",
                    evidence_snippet=r_ev.content_availability.js_rendering_impact,
                    confidence="high",
                ))

        # 19. AI Answerability & Information Extraction findings (Phase 10.2)
        ans_res = engine_results.get("answerability_engine")
        if ans_res and ans_res.answerability and ans_res.status == "success":
            ans_ev = ans_res.answerability
            tags.append(EvidenceProvenanceTag(
                finding=f"Observable Information Units: {ans_ev.total_units_detected} unit(s) across {len(ans_ev.units_by_type)} structural types",
                source_file="DOM & Schema Structure",
                engine="answerability_engine",
                evidence_snippet=f"Explained topics: {ans_ev.explained_topics_count}, Q&A clarity: {ans_ev.clarity_assessment.question_answer_patterns.value}",
                confidence="high",
            ))
            if ans_ev.explained_topics_count > 0:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Phase 9 Topic Explanations: {ans_ev.explained_topics_count} topic(s) substantiated by explicit answerable structures",
                    source_file="Heading & Body Passages",
                    engine="answerability_engine",
                    evidence_snippet=", ".join([tl.topic_name for tl in ans_ev.topic_links if tl.status.value == "EXPLAINED"][:4]),
                    confidence="high",
                ))
            if ans_ev.clarity_assessment.unsupported_concepts:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Unsupported Topical Headings: {len(ans_ev.clarity_assessment.unsupported_concepts)} heading(s) without supporting body copy",
                    source_file="Heading Section AST",
                    engine="answerability_engine",
                    evidence_snippet=", ".join(ans_ev.clarity_assessment.unsupported_concepts[:3]),
                    confidence="high",
                ))

        # 20. Claim Grounding & Entity Intelligence findings (Phase 10.3)
        cg_res = engine_results.get("claim_grounding_engine")
        if cg_res and cg_res.claim_grounding and cg_res.status == "success":
            cg_ev = cg_res.claim_grounding
            tags.append(EvidenceProvenanceTag(
                finding=f"Observable Claims Grounding: {cg_ev.total_claims_detected} claim(s) ({cg_ev.supported_claims_count} supported on-site, {cg_ev.uncorroborated_count} uncorroborated)",
                source_file="Visible Content & Answerable Units",
                engine="claim_grounding_engine",
                evidence_snippet=f"Supported: {cg_ev.supported_claims_count}, Partial: {cg_ev.partially_supported_count}, Uncorroborated: {cg_ev.uncorroborated_count}, Contradicted: {cg_ev.contradicted_count}",
                confidence="high",
            ))
            if cg_ev.structured_agreements:
                agree_cnt = sum(1 for a in cg_ev.structured_agreements if a.status.value == "AGREEMENT")
                disagree_cnt = sum(1 for a in cg_ev.structured_agreements if a.status.value == "DISAGREEMENT")
                tags.append(EvidenceProvenanceTag(
                    finding=f"Structured vs Visible Alignment: {agree_cnt} agreement(s), {disagree_cnt} disagreement(s)",
                    source_file="JSON-LD & DOM Content",
                    engine="claim_grounding_engine",
                    evidence_snippet=", ".join([f"{a.field_name}: {a.status.value}" for a in cg_ev.structured_agreements[:3]]),
                    confidence="high",
                ))
            if cg_ev.entity_grounding:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Entity Surface Consistency: {len(cg_ev.entity_grounding)} candidate(s) tracked across 6 content surfaces",
                    source_file="DOM, Headings, Meta, JSON-LD, Units",
                    engine="claim_grounding_engine",
                    evidence_snippet=", ".join([f"{eg.entity_name} ({eg.consistency_status.value})" for eg in cg_ev.entity_grounding[:2]]),
                    confidence="high",
                ))

        # 21. Multimodal & Agent Readiness Intelligence findings (Phase 10.4)
        mma_res = engine_results.get("multimodal_agent_engine")
        if mma_res and mma_res.multimodal_agent and mma_res.status == "success":
            mma_ev = mma_res.multimodal_agent
            tags.append(EvidenceProvenanceTag(
                finding=f"Multimodal Information Representation: {mma_ev.multimodal.total_visual_assets} visual asset(s) ({mma_ev.multimodal.informational_assets_count} informational, {mma_ev.multimodal.alt_represented_count} alt-represented)",
                source_file="HTML DOM & Image Assets",
                engine="multimodal_agent_engine",
                evidence_snippet=f"Captions: {mma_ev.multimodal.caption_represented_count}, Visual-only gaps: {mma_ev.multimodal.visual_only_observed_count}",
                confidence="high",
            ))
            if mma_ev.agent_readiness.total_forms_detected > 0:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Agent Interaction Surfaces: {mma_ev.agent_readiness.total_forms_detected} form(s) ({mma_ev.agent_readiness.labeled_forms_count} labeled), {mma_ev.agent_readiness.action_buttons_detected} button(s)",
                    source_file="HTML Forms & Controls",
                    engine="multimodal_agent_engine",
                    evidence_snippet=f"Search: {mma_ev.agent_readiness.search_forms_count}, Contact/Inquiry: {mma_ev.agent_readiness.contact_inquiry_forms_count}, Schema Actions: {mma_ev.agent_readiness.schema_actions_detected}",
                    confidence="high",
                ))
            if mma_ev.access_paths:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Information Access Paths: {len(mma_ev.access_paths)} path(s) triangulated across visual and interactive surfaces",
                    source_file="Multi-Engine Triangulation",
                    engine="multimodal_agent_engine",
                    evidence_snippet=", ".join([f"{p.path_type} ({p.related_concept})" for p in mma_ev.access_paths[:3]]),
                    confidence="high",
                ))

        return tags
