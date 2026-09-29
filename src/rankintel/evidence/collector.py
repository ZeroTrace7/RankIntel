"""
Evidence Collector — Orchestrates the specialized engines:
1. SEO Engine (advertools / RFC robots / sitemaps)
2. Browser Engine (crawl4ai / client-side JS DOM)
3. GEO Engine (Princeton GEO / AutoGEO / llms.txt validation)
"""
from __future__ import annotations
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

from rankintel.engines.seo_engine import SeoEngine
from rankintel.engines.geo_engine import GeoEngine
from rankintel.engines.browser_engine import BrowserEngine
from rankintel.models.schema import EngineResult

class EvidenceCollector:
    """Coordinates and collects evidence across all specialized intelligence engines."""

    def __init__(self):
        self.seo_engine = SeoEngine()
        self.geo_engine = GeoEngine()
        self.browser_engine = BrowserEngine()

    def collect(self, url: str) -> Dict[str, EngineResult]:
        """Run all three engines on the target URL and collect raw evidence."""
        results: Dict[str, EngineResult] = {}

        # 1. Run SEO Engine (advertools)
        try:
            results["advertools_seo"] = self.seo_engine.execute(url)
        except Exception as e:
            results["advertools_seo"] = EngineResult(
                engine_name="advertools_seo",
                status="error",
                error_message=f"SEO engine failed: {e}"
            )

        # 2. Run GEO Engine (Princeton / AutoGEO)
        try:
            results["rankintel_geo"] = self.geo_engine.execute(url)
        except Exception as e:
            results["rankintel_geo"] = EngineResult(
                engine_name="rankintel_geo",
                status="error",
                error_message=f"GEO engine failed: {e}"
            )

        # 3. Run Browser Engine (crawl4ai / JS render check)
        try:
            results["browser_engine"] = self.browser_engine.execute_sync(url)
        except Exception as e:
            results["browser_engine"] = EngineResult(
                engine_name="browser_engine",
                status="error",
                error_message=f"Browser engine failed: {e}"
            )

        return results
