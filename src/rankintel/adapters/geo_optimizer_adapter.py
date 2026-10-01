"""
GeoOptimizer Adapter — Wraps geo-optimizer-skill v4+.

Produces RankIntel GeoAeoEvidence from geo_optimizer's 47-method citability
analysis. Accepts pre-fetched HTML (from browser_engine.raw_html) so no
second HTTP request is made for the same URL.

Falls back to the built-in GeoEngine when geo-optimizer-skill is not installed.
"""
from __future__ import annotations
import time
from typing import Optional
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    GeoCitabilityMethod,
    GeoAeoEvidence,
    EngineResult,
)

try:
    from geo_optimizer.core.citability import audit_citability
    from geo_optimizer.core.audit_llms import audit_llms_txt
    HAS_GEO_OPTIMIZER = True
except ImportError:
    HAS_GEO_OPTIMIZER = False
    audit_citability = None  # type: ignore
    audit_llms_txt = None  # type: ignore


class GeoOptimizerAdapter:
    """
    RankIntel adapter wrapping geo-optimizer-skill for GEO/AEO evidence.

    When raw_html is provided (from crawl4ai browser engine), it is used
    directly so the same URL is not fetched twice. The llms.txt audit always
    makes its own request since it checks a separate URL (/llms.txt).
    """

    def execute(self, url: str, raw_html: Optional[str] = None) -> EngineResult:
        """
        Run GEO analysis.

        Args:
            url: Target URL being audited.
            raw_html: Pre-fetched rendered HTML from browser_engine. If None,
                      falls back to geo_optimizer's own HTTP fetch.
        """
        t0 = time.time()

        if not HAS_GEO_OPTIMIZER:
            # Graceful fallback to built-in GeoEngine
            from rankintel.engines.geo_engine import GeoEngine
            result = GeoEngine().execute(url)
            result.engine_name = "rankintel_geo"
            return result

        try:
            geo_ev = self._run_citability(url, raw_html)
            return EngineResult(
                engine_name="rankintel_geo",
                status="success",
                execution_time_sec=round(time.time() - t0, 2),
                geo_aeo=geo_ev,
            )
        except Exception as e:
            return EngineResult(
                engine_name="rankintel_geo",
                status="error",
                error_message=f"GeoOptimizerAdapter failed: {e}",
                execution_time_sec=round(time.time() - t0, 2),
            )

    def _run_citability(self, url: str, raw_html: Optional[str]) -> GeoAeoEvidence:
        """Run citability analysis and llms.txt check, return GeoAeoEvidence."""

        if raw_html:
            # Use pre-fetched HTML — no second HTTP request
            soup = BeautifulSoup(raw_html, "html.parser")
            soup_clean = BeautifulSoup(raw_html, "html.parser")
            cit = audit_citability(soup, url, soup_clean)
        else:
            # Fallback: let geo_optimizer fetch its own copy
            from geo_optimizer import audit as geo_audit
            full_result = geo_audit(url)
            cit = full_result.citability

        # Map geo_optimizer MethodScore objects → RankIntel GeoCitabilityMethod
        methods = [
            GeoCitabilityMethod(
                name=m.name,
                label=m.label,
                detected=m.detected,
                score=m.score,
                max_score=m.max_score,
                impact=m.impact,  # geo-optimizer already labels impact strings correctly
                details=m.details if isinstance(m.details, dict) else {},
            )
            for m in cit.methods
        ]

        # Extract specific ratios/counts from method details
        def _detail(method_name: str, key: str, default=0.0):
            for m in cit.methods:
                if m.name == method_name:
                    v = (m.details or {}).get(key, default)
                    return float(v)
            return float(default)

        answer_first_ratio = _detail("answer_first", "ratio")
        passage_density_ratio = _detail("passage_density", "ratio")
        stat_density = _detail("statistics", "density_per_1000")
        auth_cit_count = int(_detail("cite_sources", "authoritative_citations_count"))
        total_ext_links = int(_detail("cite_sources", "total_external_links"))

        # llms.txt always checks its own URL (separate endpoint)
        try:
            llms = audit_llms_txt(url)
            has_markdown_structure = bool(
                getattr(llms, "has_h1", False)
                or getattr(llms, "has_links", False)
                or getattr(llms, "has_sections", False)
                or getattr(llms, "has_blockquote", False)
                or getattr(llms, "has_description", False)
            )
            llms_found = bool(llms.found and has_markdown_structure)
            llms_warnings = list(llms.validation_warnings or []) if llms_found else []
            llms_full = bool(llms.has_full and llms_found)
        except Exception:
            llms_found = False
            llms_warnings = []
            llms_full = False

        return GeoAeoEvidence(
            overall_citability_score=cit.total_score,
            answer_first_ratio=answer_first_ratio,
            passage_density_ratio=passage_density_ratio,
            statistical_density_per_1000=stat_density,
            outbound_citations_count=total_ext_links,
            authoritative_citations_count=auth_cit_count,
            llms_txt_found=llms_found,
            llms_txt_warnings=llms_warnings,
            llms_full_found=llms_full,
            question_h2s=[],
            methods=methods,
            engine_source="geo_optimizer_skill",
        )
