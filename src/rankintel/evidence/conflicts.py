"""
Conflict & Triangulation Detector — Identifies divergence, anomalies, and
critical insights between static SEO crawlers, browser engines, and GEO analyzers.
"""
from __future__ import annotations
from typing import Dict, List
from rankintel.models.schema import EngineResult, ConflictFinding

class ConflictDetector:
    """Detects agreements and conflicts across specialized engines."""

    def detect(self, engine_results: Dict[str, EngineResult]) -> List[ConflictFinding]:
        conflicts: List[ConflictFinding] = []

        seo_res = engine_results.get("advertools_seo")
        geo_res = engine_results.get("rankintel_geo")
        browser_res = engine_results.get("browser_engine")

        # 1. Check AI Crawler Misconfiguration (Search Bot vs Training Bot)
        if seo_res and seo_res.robots and seo_res.robots.found:
            access = seo_res.robots.bot_access
            oai_search = access.get("OAI-SearchBot")
            gpt_bot = access.get("GPTBot")

            if oai_search and gpt_bot:
                if oai_search.status == "BLOCKED" and gpt_bot.status == "ALLOWED":
                    conflicts.append(ConflictFinding(
                        category="AI_CRAWLER_MISCONFIG",
                        feature="ChatGPT Search vs Training Access",
                        description="OAI-SearchBot is blocked while GPTBot is allowed.",
                        engine_a_finding="OAI-SearchBot: BLOCKED (No ChatGPT Search citations)",
                        engine_b_finding="GPTBot: ALLOWED (Training scraper permitted)",
                        interpretation=(
                            "Critical AI Search Discrepancy: The site permits model training scraping (GPTBot) "
                            "but explicitly blocks live ChatGPT Search queries (OAI-SearchBot). This surrenders "
                            "valuable content for AI training without receiving referral citations in return."
                        ),
                        severity="HIGH"
                    ))

            googlebot = access.get("Googlebot")
            google_ext = access.get("Google-Extended")
            if googlebot and google_ext:
                if googlebot.status == "BLOCKED" and google_ext.status == "ALLOWED":
                    conflicts.append(ConflictFinding(
                        category="AI_CRAWLER_MISCONFIG",
                        feature="Googlebot vs Google-Extended",
                        description="Googlebot is blocked while Google-Extended is allowed.",
                        engine_a_finding="Googlebot: BLOCKED",
                        engine_b_finding="Google-Extended: ALLOWED",
                        interpretation="Severe misconfiguration: Site is de-indexed from Google Search but still crawled for Gemini training.",
                        severity="HIGH"
                    ))

        # 2. Check Static vs Browser-Rendered Schema Divergence
        if seo_res and seo_res.schema_data and browser_res and browser_res.schema_data:
            static_types = set(seo_res.schema_data.detected_types)
            browser_types = set(browser_res.schema_data.detected_types)

            js_only_types = browser_types - static_types
            if js_only_types:
                conflicts.append(ConflictFinding(
                    category="CLIENT_RENDERED_SCHEMA",
                    feature="JavaScript-Injected Structured Data",
                    description=f"Schemas {list(js_only_types)} only exist in browser DOM, missing from static HTML.",
                    engine_a_finding=f"advertools_seo (Static): Found {len(static_types)} types {list(static_types)}",
                    engine_b_finding=f"browser_engine (DOM): Found {len(browser_types)} types {list(browser_types)}",
                    interpretation=(
                        "Schema.org markup is injected dynamically via client-side JavaScript. While Googlebot eventually "
                        "renders JS, many AI search bots (Perplexity, Claude), social scrapers, and indexers execute with "
                        "static fetch only, completely missing your structured entities."
                    ),
                    severity="HIGH"
                ))

        # 3. Check Static vs Browser On-Page Content Divergence
        if seo_res and seo_res.on_page and browser_res and browser_res.on_page:
            static_title = seo_res.on_page.title
            browser_title = browser_res.on_page.title
            if static_title and browser_title and static_title != browser_title:
                conflicts.append(ConflictFinding(
                    category="DOM_HYDRATION_DIVERGENCE",
                    feature="Title Tag Overwrite",
                    description="Title tag in static HTML is altered during browser rendering.",
                    engine_a_finding=f"Static HTML: '{static_title}'",
                    engine_b_finding=f"Browser DOM: '{browser_title}'",
                    interpretation=(
                        "Client-side JavaScript rewrites the <title> tag upon page hydration. "
                        "Search engines with slow rendering pipelines may index the outdated static title."
                    ),
                    severity="MEDIUM"
                ))

            # H1 missing in static
            if seo_res.on_page.h1_count == 0 and browser_res.on_page.h1_count > 0:
                conflicts.append(ConflictFinding(
                    category="CSR_HEADING_DEPENDENCY",
                    feature="Missing Static H1 Tag",
                    description="H1 tag is completely absent from initial HTML, only present after JS execution.",
                    engine_a_finding="advertools_seo: 0 H1 tags in raw source",
                    engine_b_finding=f"browser_engine: {browser_res.on_page.h1_count} H1 tags in rendered DOM",
                    interpretation=(
                        "Core content hierarchy relies on client-side rendering. "
                        "Static crawlers perceive the page as lacking a clear primary topical heading."
                    ),
                    severity="MEDIUM"
                ))

        # 4. Check GEO Citability vs Technical AI Discovery (llms.txt missing)
        if geo_res and geo_res.geo_aeo:
            citability = geo_res.geo_aeo.overall_citability_score
            has_llms = geo_res.geo_aeo.llms_txt_found
            if citability >= 50 and not has_llms:
                conflicts.append(ConflictFinding(
                    category="AI_DISCOVERY_GAP",
                    feature="High Citability Content without llms.txt",
                    description=f"Site has a strong Citability Score ({citability}/100) but no /llms.txt manifest.",
                    engine_a_finding=f"rankintel_geo: Citability {citability}/100 (rich facts and structure)",
                    engine_b_finding="advertools/geo: /llms.txt returned HTTP 404 (Missing)",
                    interpretation=(
                        "The site's content contains dense, citable data that answer engines favor, "
                        "yet fails to provide a standard machine-readable /llms.txt index, making automated agent ingestion harder."
                    ),
                    severity="LOW"
                ))

        # 5. Check Insecure Asset References on HTTPS Origin (Image / Head vs Security)
        img_res = engine_results.get("image_engine")
        sec_res = engine_results.get("security_engine")

        insecure_assets = []
        if img_res and img_res.image_seo:
            if img_res.image_seo.head_audit and img_res.image_seo.head_audit.insecure_resource_urls:
                insecure_assets.extend(img_res.image_seo.head_audit.insecure_resource_urls)
            for img in img_res.image_seo.images:
                if img.src.startswith("http://") and img.src not in insecure_assets:
                    insecure_assets.append(img.src)

        has_sec_mixed = False
        sec_finding_desc = ""
        if sec_res and sec_res.security and sec_res.security.is_https:
            if sec_res.security.mixed_content_resources:
                has_sec_mixed = True
                sec_finding_desc = f"{len(sec_res.security.mixed_content_resources)} mixed content resources detected by SecurityEngine"
            else:
                for f in sec_res.security.findings:
                    if f.code in ("SEC_ACTIVE_MIXED_CONTENT", "SEC_PASSIVE_MIXED_CONTENT"):
                        has_sec_mixed = True
                        sec_finding_desc = f.description
                        break

        if insecure_assets and has_sec_mixed:
            conflicts.append(ConflictFinding(
                category="MIXED_CONTENT_SECURITY",
                feature="Insecure Assets on HTTPS Origin",
                description=f"Detected {len(insecure_assets)} insecure asset references (HTTP) on an HTTPS page triggering mixed content security warnings.",
                engine_a_finding=f"image_engine / head_audit: Observed {len(insecure_assets)} plaintext http:// URLs ({insecure_assets[0][:60]}...)",
                engine_b_finding=f"security_engine: {sec_finding_desc}",
                interpretation=(
                    "Insecure asset references (HTTP) within an HTTPS page trigger browser mixed-content blocking "
                    "and 'Not Secure' padlock warnings. Browsers block active scripts/styles and suppress or flag insecure "
                    "images, degrading both user trust and search engine visual indexation."
                ),
                severity="HIGH"
            ))

        # 6. Check Client-Side Rendered Content Divergence (Static vs Browser/Content Engine)
        cnt_res = engine_results.get("content_engine")
        if seo_res and seo_res.on_page and cnt_res and cnt_res.content:
            static_words = seo_res.on_page.word_count
            main_words = cnt_res.content.main_content_word_count
            if static_words < 50 and main_words >= 250:
                conflicts.append(ConflictFinding(
                    category="CLIENT_RENDERED_CONTENT",
                    feature="JavaScript-Rendered Main Content",
                    description=f"Static HTML contains only {static_words} words, while rendered DOM contains {main_words} editorial words.",
                    engine_a_finding=f"advertools_seo (Static): {static_words} words extracted from raw HTML",
                    engine_b_finding=f"content_engine (DOM): {main_words} words extracted from rendered DOM",
                    interpretation=(
                        "Core editorial body content depends on client-side JavaScript hydration. "
                        "Crawlers lacking headless JavaScript rendering pipelines (such as many AI search scrapers) "
                        "will perceive the page as thin or empty."
                    ),
                    severity="HIGH"
                ))

        # 7. Check Structured vs Visible Entity Divergence (Entity Engine)
        ent_res = engine_results.get("entity_engine")
        if ent_res and ent_res.entity and ent_res.entity.structured_vs_visible:
            for comp in ent_res.entity.structured_vs_visible:
                if comp.alignment_status.value == "DIVERGENT_IDENTITY_SUSPECTED" and comp.attribute_name == "organization_name":
                    conflicts.append(ConflictFinding(
                        category="DIVERGENT_ORGANIZATION_IDENTITY",
                        feature="Structured vs Visible Entity Branding",
                        description=f"Structured Organization '{comp.structured_value}' differs from visible branding '{comp.visible_value}'.",
                        engine_a_finding=f"Structured Data (JSON-LD): Declares '{comp.structured_value}'",
                        engine_b_finding=f"Visible Signals (DOM): Declares '{comp.visible_value}'",
                        interpretation=(
                            "The organization declared in structured data and the organization observed in visible page branding "
                            "share no common brand tokens. This may represent white-labeling, third-party template reuse, "
                            "or an entity disambiguation discrepancy in search engine knowledge graphs."
                        ),
                        severity="MEDIUM"
                    ))
                    break

        # 8. Check Retrieval Readiness Directives vs Access Conflicts (Phase 10.1)
        retrieval_res = engine_results.get("retrieval_readiness_engine")
        if retrieval_res and retrieval_res.retrieval_readiness and retrieval_res.status == "success":
            r_ev = retrieval_res.retrieval_readiness
            # Case A: robots.txt allows search bot, but page declares noindex
            oai_rec = r_ev.bot_access_records.get("OAI-SearchBot")
            if oai_rec and oai_rec.robots_access.value == "ALLOWED" and r_ev.indexability_interaction.has_noindex:
                conflicts.append(ConflictFinding(
                    category="AI_RETRIEVAL_DIRECTIVE_CONFLICT",
                    feature="robots.txt Crawl Permitted vs noindex Suppression",
                    description="OAI-SearchBot is permitted in robots.txt, but page declares noindex.",
                    engine_a_finding="robots.txt: OAI-SearchBot ALLOWED",
                    engine_b_finding=f"Page Directives: noindex in {', '.join(r_ev.indexability_interaction.noindex_sources)}",
                    interpretation=(
                        "Search indexers are allowed to fetch the URL, but the noindex directive "
                        "instructs search engines not to index or surface citations from this page."
                    ),
                    severity="HIGH"
                ))

            # Case B: robots.txt allows crawlers, but server/WAF blocked access
            if r_ev.waf_challenge.is_blocked and any(b.robots_access.value == "ALLOWED" for b in r_ev.bot_access_records.values()):
                conflicts.append(ConflictFinding(
                    category="WAF_RETRIEVAL_BLOCK",
                    feature="robots.txt Permitted vs Network/WAF Blocked",
                    description=f"robots.txt permits crawler access, but server returned HTTP {r_ev.waf_challenge.status_code} / challenge.",
                    engine_a_finding="robots.txt: Crawler access permitted",
                    engine_b_finding=f"Network/WAF: HTTP {r_ev.waf_challenge.status_code} ({r_ev.waf_challenge.waf_provider})",
                    interpretation=(
                        "While robots.txt grants crawler access, automated requests are intercepted "
                        "by firewall or challenge barriers before reaching the application."
                    ),
                    severity="HIGH"
                ))

        # 9. Check Answerability & Extraction Conflicts (Phase 10.2)
        ans_res = engine_results.get("answerability_engine")
        if ans_res and ans_res.answerability and ans_res.status == "success":
            ans_ev = ans_res.answerability
            # Case A: Important Topic Promoted in Heading but Completely Unsupported
            for tl in ans_ev.topic_links:
                if tl.status.value == "UNSUPPORTED_HEADING" and tl.section_heading:
                    conflicts.append(ConflictFinding(
                        category="CONTENT_ANSWERABILITY_GAP",
                        feature="Topic Heading without Supporting Content",
                        description=f"Topic '{tl.topic_name}' has dedicated heading '{tl.section_heading}', but supporting body content is genuinely absent.",
                        engine_a_finding=f"Topic Engine: Candidate topic '{tl.topic_name}'",
                        engine_b_finding=f"Answerability Engine: Heading '{tl.section_heading}' has 0 supporting body words",
                        interpretation=(
                            "The page establishes an explicit topical heading promise for search/AI retrieval, "
                            "but fails to provide observable explanatory or factual body copy under that section."
                        ),
                        severity="MEDIUM"
                    ))
                    break

            # Case B: Answerable Unit Obscured by Snippet Control
            if ans_ev.clarity_assessment.obscured_or_fragmented_items:
                conflicts.append(ConflictFinding(
                    category="SNIPPET_SUPPRESSION_CONFLICT",
                    feature="Answer Unit Obscured by data-nosnippet",
                    description=f"{len(ans_ev.clarity_assessment.obscured_or_fragmented_items)} answerable unit(s) are enclosed in data-nosnippet elements.",
                    engine_a_finding=f"Answerability Engine: Structured answer units extracted ({len(ans_ev.clarity_assessment.obscured_or_fragmented_items)} items)",
                    engine_b_finding="Snippet Controls: data-nosnippet attribute active on enclosing element",
                    interpretation=(
                        "Valuable factual or procedural answers exist on page but are tagged with data-nosnippet, "
                        "instructing search engines and AI retrievers not to surface them in search snippets."
                    ),
                    severity="HIGH"
                ))

        # 10. Check Claim Grounding & Structured Agreement Conflicts (Phase 10.3)
        cg_res = engine_results.get("claim_grounding_engine")
        if cg_res and cg_res.claim_grounding and cg_res.status == "success":
            cg_ev = cg_res.claim_grounding
            # Case A: Structured vs Visible Disagreement (e.g., name, phone, email, address)
            for agree in cg_ev.structured_agreements:
                if agree.status.value == "DISAGREEMENT":
                    conflicts.append(ConflictFinding(
                        category="STRUCTURED_VISIBLE_DIVERGENCE",
                        feature=f"JSON-LD vs Visible {agree.field_name.replace('_', ' ').title()}",
                        description=(
                            f"JSON-LD declares '{agree.structured_value}' while visible content "
                            f"displays '{agree.visible_value}' under {agree.context_label} context."
                        ),
                        engine_a_finding=f"JSON-LD Schema: '{agree.structured_value}'",
                        engine_b_finding=f"Visible Content: '{agree.visible_value}'",
                        interpretation=(
                            f"Discrepancy detected between structured schema declarations and visible user-facing text. "
                            f"Search engines and AI systems comparing structured data against rendered pages may flag "
                            f"inconsistent identity signals for '{agree.field_name}'."
                        ),
                        severity="HIGH" if agree.field_name in ("organization_name", "telephone") else "MEDIUM"
                    ))

            # Case B: Explicit Contradictory Claims on Site
            for claim in cg_ev.claims:
                if claim.support_status.value == "CONTRADICTED_ON_SITE" and claim.contradicting_snippets:
                    conflicts.append(ConflictFinding(
                        category="ON_SITE_CLAIM_CONTRADICTION",
                        feature=f"Contradicting Claims: {claim.claim_type.replace('_', ' ').title()}",
                        description=(
                            f"Observable statement '{claim.claim_text[:60]}...' is explicitly contradicted "
                            f"by '{claim.contradicting_snippets[0][:60]}...' on the site."
                        ),
                        engine_a_finding=f"Statement: '{claim.claim_text[:80]}'",
                        engine_b_finding=f"Contradicting Evidence: '{claim.contradicting_snippets[0][:80]}'",
                        interpretation=(
                            "The site presents mutually incompatible factual values for the same subject and context, "
                            "creating ambiguous signals for both human readers and AI retrieval systems."
                        ),
                        severity="HIGH"
                    ))
                    break

        # 11. Check Multimodal & Agent Readiness Conflicts (Phase 10.4)
        mma_res = engine_results.get("multimodal_agent_engine")
        if mma_res and mma_res.multimodal_agent and mma_res.status == "success":
            mma_ev = mma_res.multimodal_agent
            # Case A: Important Information Unit Linked to Visual-Only Graphic
            for asset in mma_ev.multimodal.assets:
                if asset.related_unit_id and asset.representation_status.value == "VISUAL_ONLY_OBSERVED":
                    conflicts.append(ConflictFinding(
                        category="MULTIMODAL_INFORMATION_GAP",
                        feature="Information Unit Missing Textual / Alt Representation",
                        description=f"Information unit '{asset.related_unit_id}' is linked to graphic '{asset.src_or_id[:40]}' with no text, alt, or caption representation.",
                        engine_a_finding=f"Answerability Engine: Important information unit '{asset.related_unit_id}' identified",
                        engine_b_finding="Multimodal Engine: Visual asset lacks alt text, figcaption, or surrounding explanation",
                        interpretation=(
                            "A key topical or procedural unit is illustrated by an informational visual graphic, but the visual "
                            "asset provides no machine-readable textual representation. Non-visual user agents and text-only search "
                            "crawlers cannot extract the information contained in the image."
                        ),
                        severity="MEDIUM"
                    ))
                    break

            # Case B: Visible Action Button Has Conflicting Accessible Name Metadata
            for s in mma_ev.agent_readiness.surfaces:
                if s.signal_type.value == "ACTION_BUTTON" and s.aria_label and s.surface_name:
                    vis = s.surface_name.strip().lower()
                    aria = s.aria_label.strip().lower()
                    clashes = [("submit", "cancel"), ("save", "delete"), ("next", "previous"), ("open", "close"), ("login", "logout")]
                    if any((c1 in vis and c2 in aria) or (c2 in vis and c1 in aria) for c1, c2 in clashes):
                        conflicts.append(ConflictFinding(
                            category="ACTION_ACCESSIBLE_NAME_MISMATCH",
                            feature="Button Visible Text vs Accessible Name Clashing",
                            description=f"Button displays visible label '{s.surface_name}' but declares conflicting aria-label '{s.aria_label}'.",
                            engine_a_finding=f"DOM Visible Label: '{s.surface_name}'",
                            engine_b_finding=f"ARIA Accessible Name: '{s.aria_label}'",
                            interpretation=(
                                "The visible text displayed on an action control conflicts with the programmatic name exposed "
                                "via ARIA attributes, causing divergent behavior for assistive technologies and web agents."
                            ),
                            severity="HIGH"
                        ))
                        break

            # Case C: Structured Interaction Metadata (JSON-LD) Conflicts with Observable Control
            schema_acts = [sf for sf in mma_ev.agent_readiness.surfaces if sf.signal_type.value == "SCHEMA_POTENTIAL_ACTION"]
            dom_forms = [sf for sf in mma_ev.agent_readiness.surfaces if sf.signal_type.value in ("SEARCH_FORM", "FORM_CONTROL")]
            if schema_acts and dom_forms:
                for sa in schema_acts:
                    target = (sa.structured_action_target or "").lower()
                    for df in dom_forms:
                        if df.form_action and target:
                            # If schema action targets endpoint A but form action explicitly targets completely different endpoint B
                            sa_path = target.split("?")[0].rstrip("/")
                            df_path = df.form_action.split("?")[0].rstrip("/")
                            if sa_path and df_path and sa_path != df_path and (sa_path in df_path or df_path in sa_path) is False:
                                conflicts.append(ConflictFinding(
                                    category="STRUCTURED_ACTION_CONTROL_CONFLICT",
                                    feature="JSON-LD Action Target vs DOM Form Action Discrepancy",
                                    description=f"Schema declares action target '{sa_path}' while DOM form targets '{df_path}'.",
                                    engine_a_finding=f"JSON-LD Schema Action Target: '{sa_path}'",
                                    engine_b_finding=f"DOM Form Action: '{df_path}'",
                                    interpretation=(
                                        "Structured data declares an automated interaction target endpoint that diverges from "
                                        "the actual interactive form action attribute rendered in the DOM."
                                    ),
                                    severity="MEDIUM"
                                ))
                                break

        # 12. Check Controlled External AI Visibility Conflicts (Phase 10.5)
        ext_res = engine_results.get("external_visibility_engine")
        if ext_res and ext_res.external_visibility and ext_res.status == "success":
            ext_ev = ext_res.external_visibility
            for obs in ext_ev.observations:
                for cit in obs.citations:
                    if cit.content_match_status.value == "MISMATCH":
                        conflicts.append(ConflictFinding(
                            category="EXTERNAL_CITATION_MATERIAL_MISMATCH",
                            feature=f"External Citation Material Contradiction ({obs.provider.value})",
                            description=(
                                f"External observation citation '{cit.citation_url}' snippet materially conflicts "
                                f"with observed crawled evidence on the site."
                            ),
                            engine_a_finding=f"External Provider Citation ({obs.provider.value}): '{cit.snippet[:80]}'",
                            engine_b_finding="Crawled On-Site Evidence: Conflicting factual statements detected",
                            interpretation=(
                                "The external AI/search citation presents factual assertions that directly contradict "
                                "the verifiable content found on the crawled target page."
                            ),
                            severity="HIGH"
                        ))
                        break

        return conflicts
