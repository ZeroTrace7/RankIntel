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
from rankintel.models.schema import EngineResult


class EvidenceCollector:
    """Coordinates evidence collection across all specialized intelligence engines."""

    def __init__(self):
        self.seo_engine = SeoEngine()
        self.geo_engine = GeoOptimizerAdapter()  # wraps geo-optimizer-skill
        self.browser_engine = BrowserEngine()
        self.performance_engine = PerformanceEngine()
        self.mcp_engine = McpEngine()

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
        browser_html = (results.get("browser_engine") or EngineResult(engine_name="x")).raw_html
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

        return results
