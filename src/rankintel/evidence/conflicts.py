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

        return conflicts
