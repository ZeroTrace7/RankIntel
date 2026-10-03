"""
Evidence Collector — Orchestrates the specialized engines:
1. SEO Engine (advertools / RFC robots / sitemaps)
2. Browser Engine (crawl4ai AsyncWebCrawler / httpx fallback)
3. GEO Engine (geo-optimizer-skill adapter; raw_html passed from browser engine)
4. Performance Engine (PageSpeed API / Core Web Vitals / TTFB)
5. MCP Cloud Engine (OpenSEO / DataForSEO — silent fallback)
"""
from __future__ import annotations
from typing import Dict
from rankintel.engines.seo_engine import SeoEngine
from rankintel.adapters.geo_optimizer_adapter import GeoOptimizerAdapter
from rankintel.engines.browser_engine import BrowserEngine
from rankintel.engines.performance_engine import PerformanceEngine
from rankintel.engines.mcp_engine import McpEngine
from rankintel.engines.image_engine import ImageEngine
from rankintel.engines.accessibility_engine import AccessibilityEngine
from rankintel.engines.security_engine import SecurityEngine
from rankintel.engines.content_engine import ContentEngine
from rankintel.engines.entity_engine import EntityEngine
from rankintel.engines.internal_link_engine import InternalLinkEngine
from rankintel.engines.search_signal_engine import SearchSignalEngine
from rankintel.engines.topic_intelligence_engine import TopicIntelligenceEngine
from rankintel.engines.query_page_mapping_engine import QueryPageMappingEngine
from rankintel.engines.search_intent_engine import SearchIntentEngine
from rankintel.models.schema import (
    EngineResult,
    SecurityStatus,
    WcagStatus,
    SecurityEvidence,
    AccessibilityEvidence,
    ImageSEOEvidence,
    ContentEvidence,
    EntityEvidence,
    InternalLinkEvidence,
    SearchSignalEvidence,
    PageTopicIntelligence,
    PageQueryEvidence,
    PageIntentEvidence,
)
import asyncio
import concurrent.futures
from urllib.parse import urlparse


class EvidenceCollector:
    """Coordinates evidence collection across all specialized intelligence engines."""

    def __init__(self):
        self.seo_engine = SeoEngine()
        self.geo_engine = GeoOptimizerAdapter()  # wraps geo-optimizer-skill
        self.browser_engine = BrowserEngine()
        self.performance_engine = PerformanceEngine()
        self.mcp_engine = McpEngine()
        self.image_engine = ImageEngine()
        self.accessibility_engine = AccessibilityEngine()
        self.security_engine = SecurityEngine()
        self.content_engine = ContentEngine()
        self.entity_engine = EntityEngine()
        self.internal_link_engine = InternalLinkEngine()
        self.search_signal_engine = SearchSignalEngine()
        self.topic_intelligence_engine = TopicIntelligenceEngine()
        self.query_page_mapping_engine = QueryPageMappingEngine()
        self.search_intent_engine = SearchIntentEngine()

    def _run_async(self, coro):
        """Helper to run async coroutines safely from synchronous context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    def collect(self, url: str) -> Dict[str, EngineResult]:
        """Run all engines on the target URL and collect raw evidence."""
        results: Dict[str, EngineResult] = {}

        # 1. SEO Engine (advertools — robots, sitemap, static HTML)
        try:
            results["advertools_seo"] = self.seo_engine.execute(url)
        except Exception as e:
            results["advertools_seo"] = EngineResult(
                engine_name="advertools_seo",
                status="error",
                error_message=f"SEO engine failed: {e}",
            )

        # 2. Browser Engine (crawl4ai AsyncWebCrawler — post-JS DOM + raw_html)
        try:
            results["browser_engine"] = self.browser_engine.execute_sync(url)
        except Exception as e:
            results["browser_engine"] = EngineResult(
                engine_name="browser_engine",
                status="error",
                error_message=f"Browser engine failed: {e}",
            )

        # 3. GEO Engine — pass raw_html from browser engine to avoid a second HTTP request
        browser_res = results.get("browser_engine")
        browser_html = browser_res.raw_html if browser_res else None
        # Fallback to static HTML if browser engine produced none
        if not browser_html:
            seo_res_check = results.get("advertools_seo")
            if seo_res_check and seo_res_check.on_page and hasattr(seo_res_check.on_page, "raw_html"):
                browser_html = getattr(seo_res_check.on_page, "raw_html", None)

        try:
            results["rankintel_geo"] = self.geo_engine.execute(url, raw_html=browser_html)
        except Exception as e:
            results["rankintel_geo"] = EngineResult(
                engine_name="rankintel_geo",
                status="error",
                error_message=f"GEO engine failed: {e}",
            )

        # 4. Performance Engine (PSI API / CrUX / TTFB probe)
        try:
            results["performance_engine"] = self.performance_engine.execute(url)
        except Exception as e:
            results["performance_engine"] = EngineResult(
                engine_name="performance_engine",
                status="error",
                error_message=f"Performance engine failed: {e}",
            )

        # 5. MCP Cloud Engine (OpenSEO / DataForSEO — silent fallback if unavailable)
        try:
            results["mcp_cloud"] = self.mcp_engine.execute(url)
        except Exception as e:
            results["mcp_cloud"] = EngineResult(
                engine_name="mcp_cloud",
                status="skipped",
                error_message=f"Cloud intelligence skipped: {e}",
            )

        # 6. Image Engine (Phase 7.1) — Reuses already-observed raw_html (zero extra HTTP requests)
        try:
            if browser_html:
                img_evidence = ImageEngine.evaluate(browser_html, url)
                results["image_engine"] = EngineResult(
                    engine_name="image_engine",
                    status="success",
                    image_seo=img_evidence,
                )
            else:
                results["image_engine"] = EngineResult(
                    engine_name="image_engine",
                    status="skipped",
                    error_message="No HTML available for image analysis",
                    image_seo=ImageSEOEvidence(),
                )
        except Exception as e:
            results["image_engine"] = EngineResult(
                engine_name="image_engine",
                status="error",
                error_message=f"Image engine failed: {e}",
            )

        # 7. Accessibility Engine (Phase 7.2) — Preserves both static AST and axe/browser tiers
        try:
            if browser_html:
                # If browser engine performed full browser rendering, invoke axe/browser evaluation tier
                browser_rendered = (
                    browser_res is not None
                    and browser_res.on_page is not None
                    and browser_res.on_page.engine_source == "crawl4ai_browser_dom"
                )
                if browser_rendered:
                    try:
                        a11y_evidence = self._run_async(
                            AccessibilityEngine.evaluate_async(url, browser_html)
                        )
                    except Exception:
                        a11y_evidence = AccessibilityEngine.evaluate_static(browser_html, url)
                else:
                    a11y_evidence = AccessibilityEngine.evaluate_static(browser_html, url)

                results["accessibility_engine"] = EngineResult(
                    engine_name="accessibility_engine",
                    status="success",
                    accessibility=a11y_evidence,
                )
            else:
                a11y_evidence = AccessibilityEvidence(
                    url=url,
                    wcag_aa_status=WcagStatus.UNAVAILABLE,
                    notes=["No HTML available for accessibility analysis."],
                )
                results["accessibility_engine"] = EngineResult(
                    engine_name="accessibility_engine",
                    status="skipped",
                    error_message="No HTML available for accessibility analysis",
                    accessibility=a11y_evidence,
                )
        except Exception as e:
            results["accessibility_engine"] = EngineResult(
                engine_name="accessibility_engine",
                status="error",
                error_message=f"Accessibility engine failed: {e}",
            )

        # 8. Security Engine (Phase 7.3) — Reuses response headers & raw_html (zero duplicate HTTP page requests)
        try:
            seo_res = results.get("advertools_seo")
            headers = seo_res.on_page.response_headers if (seo_res and seo_res.on_page) else {}
            parsed_u = urlparse(url)
            is_https = parsed_u.scheme.lower() == "https"

            tls_details = None
            if is_https and parsed_u.hostname:
                try:
                    tls_details = self.security_engine.check_tls_certificate(
                        parsed_u.hostname, parsed_u.port or 443
                    )
                except Exception:
                    pass

            if headers:
                sec_evidence = self.security_engine.audit_headers_and_html(
                    url=url,
                    headers=headers,
                    raw_html=browser_html,
                    tls_details=tls_details,
                )
                results["security_engine"] = EngineResult(
                    engine_name="security_engine",
                    status="success",
                    security=sec_evidence,
                )
            else:
                # Do NOT trigger an extra HTTP page request if headers are unavailable; preserve UNAVAILABLE semantics
                sec_evidence = SecurityEvidence(
                    url=url,
                    is_https=is_https,
                    overall_status=SecurityStatus.UNAVAILABLE,
                    tls_details=tls_details,
                    recommendations=["Response headers were unavailable from collection pass."],
                )
                results["security_engine"] = EngineResult(
                    engine_name="security_engine",
                    status="skipped",
                    error_message="Response headers unavailable from collection pass",
                    security=sec_evidence,
                )
        except Exception as e:
            results["security_engine"] = EngineResult(
                engine_name="security_engine",
                status="error",
                error_message=f"Security engine failed: {e}",
            )

        # 9. Content Engine (Phase 8.1) — Reuses already-observed raw_html (zero duplicate HTTP requests)
        try:
            seo_res = results.get("advertools_seo")
            title = None
            h1_list = None
            if browser_res and browser_res.on_page:
                title = browser_res.on_page.title
                h1_list = browser_res.on_page.h1_text
            elif seo_res and seo_res.on_page:
                title = seo_res.on_page.title
                h1_list = seo_res.on_page.h1_text

            if browser_html:
                content_ev = self.content_engine.evaluate(
                    raw_html=browser_html,
                    url=url,
                    title=title,
                    h1_list=h1_list,
                )
                results["content_engine"] = EngineResult(
                    engine_name="content_engine",
                    status="success",
                    content=content_ev,
                )
            else:
                content_ev = self.content_engine.evaluate(
                    raw_html=None,
                    url=url,
                    title=title,
                    h1_list=h1_list,
                )
                results["content_engine"] = EngineResult(
                    engine_name="content_engine",
                    status="skipped",
                    error_message="No HTML available for content analysis",
                    content=content_ev,
                )
        except Exception as e:
            results["content_engine"] = EngineResult(
                engine_name="content_engine",
                status="error",
                error_message=f"Content engine failed: {e}",
            )

        # 10. Entity Engine (Phase 8.2) — Reuses already-observed raw_html (zero duplicate HTTP requests)
        try:
            on_page_data = None
            if browser_res and browser_res.on_page:
                on_page_data = browser_res.on_page
            elif seo_res and seo_res.on_page:
                on_page_data = seo_res.on_page

            if browser_html:
                entity_ev = self.entity_engine.evaluate(
                    raw_html=browser_html,
                    url=url,
                    on_page=on_page_data,
                )
                results["entity_engine"] = EngineResult(
                    engine_name="entity_engine",
                    status="success",
                    entity=entity_ev,
                )
            else:
                entity_ev = self.entity_engine.evaluate(
                    raw_html=None,
                    url=url,
                    on_page=on_page_data,
                )
                results["entity_engine"] = EngineResult(
                    engine_name="entity_engine",
                    status="skipped",
                    error_message="No HTML available for entity analysis",
                    entity=entity_ev,
                )
        except Exception as e:
            results["entity_engine"] = EngineResult(
                engine_name="entity_engine",
                status="error",
                error_message=f"Entity engine failed: {e}",
            )

        # 11. Internal Link Engine (Phase 8.3) — Reuses already-observed raw_html (zero duplicate HTTP requests)
        try:
            if browser_html:
                link_ev = self.internal_link_engine.evaluate(
                    raw_html=browser_html,
                    url=url,
                )
                results["internal_link_engine"] = EngineResult(
                    engine_name="internal_link_engine",
                    status="success",
                    internal_link=link_ev,
                )
            else:
                link_ev = self.internal_link_engine.evaluate(
                    raw_html=None,
                    url=url,
                )
                results["internal_link_engine"] = EngineResult(
                    engine_name="internal_link_engine",
                    status="skipped",
                    error_message="No HTML available for internal link analysis",
                    internal_link=link_ev,
                )
        except Exception as e:
            results["internal_link_engine"] = EngineResult(
                engine_name="internal_link_engine",
                status="error",
                error_message=f"Internal link engine failed: {e}",
            )

        # 12. Search Signal Engine (Phase 9.1 - Layer A) — Reuses already-observed raw_html & evidence (zero duplicate HTTP requests)
        try:
            content_ev_res = results.get("content_engine")
            entity_ev_res = results.get("entity_engine")
            img_ev_res = results.get("image_seo_engine")

            cnt_data = content_ev_res.content if (content_ev_res and content_ev_res.content) else None
            ent_data = entity_ev_res.entity if (entity_ev_res and entity_ev_res.entity) else None
            img_data = img_ev_res.image_seo if (img_ev_res and img_ev_res.image_seo) else None

            if browser_html:
                sig_ev = self.search_signal_engine.evaluate(
                    raw_html=browser_html,
                    url=url,
                    on_page=on_page_data,
                    content_ev=cnt_data,
                    entity_ev=ent_data,
                    image_seo_ev=img_data,
                )
                results["search_signal_engine"] = EngineResult(
                    engine_name="search_signal_engine",
                    status="success",
                    search_signal=sig_ev,
                )
            else:
                sig_ev = self.search_signal_engine.evaluate(
                    raw_html=None,
                    url=url,
                    on_page=on_page_data,
                    content_ev=cnt_data,
                    entity_ev=ent_data,
                    image_seo_ev=img_data,
                )
                results["search_signal_engine"] = EngineResult(
                    engine_name="search_signal_engine",
                    status="skipped",
                    error_message="No HTML available for search signal analysis",
                    search_signal=sig_ev,
                )
        except Exception as e:
            results["search_signal_engine"] = EngineResult(
                engine_name="search_signal_engine",
                status="error",
                error_message=f"Search signal engine failed: {e}",
            )

        # 13. Topic Intelligence Engine (Phase 9.2 - Layer A) — Reuses already-observed evidence (zero duplicate HTTP requests)
        try:
            sig_ev_res = results.get("search_signal_engine")
            content_ev_res = results.get("content_engine")
            entity_ev_res = results.get("entity_engine")

            sig_data = sig_ev_res.search_signal if (sig_ev_res and sig_ev_res.search_signal) else None
            cnt_data = content_ev_res.content if (content_ev_res and content_ev_res.content) else None
            ent_data = entity_ev_res.entity if (entity_ev_res and entity_ev_res.entity) else None

            topic_ev = self.topic_intelligence_engine.evaluate(
                search_signal_ev=sig_data,
                content_ev=cnt_data,
                entity_ev=ent_data,
                url=url,
            )

            status = "success" if (browser_html and sig_data and sig_data.signals) else "skipped"
            err_msg = None if browser_html else "No HTML available for topic intelligence"

            results["topic_intelligence_engine"] = EngineResult(
                engine_name="topic_intelligence_engine",
                status=status,
                error_message=err_msg,
                topic_intelligence=topic_ev,
            )
        except Exception as e:
            results["topic_intelligence_engine"] = EngineResult(
                engine_name="topic_intelligence_engine",
                status="error",
                error_message=f"Topic intelligence engine failed: {e}",
                topic_intelligence=PageTopicIntelligence(
                    url=url,
                    engine_source="topic_intelligence_engine",
                    status="error",
                    error_message=str(e),
                ),
            )

        # 14. Query-Page Mapping Engine (Phase 9.3 - Layer A) — Reuses already-observed evidence (zero duplicate HTTP requests)
        try:
            sig_ev_res = results.get("search_signal_engine")
            topic_ev_res = results.get("topic_intelligence_engine")
            cnt_ev_res = results.get("content_engine")
            ent_ev_res = results.get("entity_engine")
            seo_res = results.get("advertools_seo")

            sig_data = sig_ev_res.search_signal if (sig_ev_res and sig_ev_res.search_signal) else None
            topic_data = topic_ev_res.topic_intelligence if (topic_ev_res and topic_ev_res.topic_intelligence) else None
            cnt_data = cnt_ev_res.content if (cnt_ev_res and cnt_ev_res.content) else None
            ent_data = ent_ev_res.entity if (ent_ev_res and ent_ev_res.entity) else None
            on_page_data = seo_res.on_page if (seo_res and seo_res.on_page) else None

            qp_ev = self.query_page_mapping_engine.evaluate(
                url=url,
                on_page=on_page_data,
                search_signal_ev=sig_data,
                topic_intel_ev=topic_data,
                content_ev=cnt_data,
                entity_ev=ent_data,
            )

            status = "success" if (browser_html and qp_ev.total_concepts_mapped > 0) else ("skipped" if not browser_html else "success")
            err_msg = None if browser_html else "No HTML available for query-page mapping"

            results["query_page_mapping_engine"] = EngineResult(
                engine_name="query_page_mapping_engine",
                status=status,
                error_message=err_msg,
                query_page=qp_ev,
            )
        except Exception as e:
            results["query_page_mapping_engine"] = EngineResult(
                engine_name="query_page_mapping_engine",
                status="error",
                error_message=f"Query-page mapping engine failed: {e}",
                query_page=PageQueryEvidence(
                    url=url,
                    engine_source="query_page_mapping_engine",
                    status="error",
                    error_message=str(e),
                ),
            )

        # 15. Search Intent Engine (Phase 9.4 - Layer A) — Reuses already-observed evidence (zero duplicate HTTP requests)
        try:
            browser_res = results.get("crawl4ai_browser")
            schema_data = browser_res.schema_data if (browser_res and browser_res.schema_data) else None

            intent_ev = self.search_intent_engine.evaluate(
                url=url,
                raw_html=browser_html,
                on_page=on_page_data,
                search_signal_ev=sig_data,
                topic_intel_ev=topic_data,
                query_page_ev=qp_ev if 'qp_ev' in locals() else None,
                content_ev=cnt_data,
                entity_ev=ent_data,
                schema_ev=schema_data,
            )

            status = "success" if browser_html else "skipped"
            err_msg = None if browser_html else "No HTML available for search intent analysis"

            results["search_intent_engine"] = EngineResult(
                engine_name="search_intent_engine",
                status=status,
                error_message=err_msg,
                search_intent=intent_ev,
            )
        except Exception as e:
            results["search_intent_engine"] = EngineResult(
                engine_name="search_intent_engine",
                status="error",
                error_message=f"Search intent engine failed: {e}",
                search_intent=PageIntentEvidence(
                    url=url,
                    engine_source="search_intent_engine",
                    status="error",
                    error_message=str(e),
                ),
            )

        return results
