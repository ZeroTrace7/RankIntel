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

        return conflicts
