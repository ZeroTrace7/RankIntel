"""
Performance Engine — Core Web Vitals & Server Latency Telemetry.
Integrates with Google PageSpeed Insights API with robust local network latency fallback.
"""
from __future__ import annotations
import os
import time
import requests
from typing import Dict, List, Optional

from rankintel.references.cwv_thresholds import CWV_THRESHOLDS
from rankintel.models.schema import (
    PerformanceMetric,
    PerformanceEvidence,
    EngineResult
)

class PerformanceEngine:
    """Evaluates Core Web Vitals (LCP, CLS, INP/TBT, TTFB) using PageSpeed API or local probes."""

    PAGESPEED_API_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PAGESPEED_API_KEY")

    def execute(self, url: str) -> EngineResult:
        """Run performance audit pass."""
        t0 = time.time()

        # Try PageSpeed Insights first (authenticated or unauthenticated public tier)
        evidence = self._query_pagespeed_api(url)

        if not evidence:
            # Fallback to local probe
            evidence = self._measure_local_performance(url)

        return EngineResult(
            engine_name="performance_engine",
            status="success",
            execution_time_sec=round(time.time() - t0, 2),
            performance=evidence
        )

    def _query_pagespeed_api(self, url: str) -> Optional[PerformanceEvidence]:
        """Fetch Core Web Vitals from Google PageSpeed Insights API, extracting CrUX field data or Lighthouse lab data."""
        params = {
            "url": url,
            "strategy": "mobile",
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            resp = requests.get(self.PAGESPEED_API_ENDPOINT, params=params, timeout=12)
            if resp.status_code != 200:
                return None

            data = resp.json()
            lighthouse = data.get("lighthouseResult", {})
            categories = lighthouse.get("categories", {})
            perf_cat = categories.get("performance", {})
            score = int((perf_cat.get("score", 0.5) or 0.5) * 100)

            # Check for CrUX field data first (loadingExperience)
            loading_exp = data.get("loadingExperience", {})
            crux_metrics = loading_exp.get("metrics", {})
            has_crux = bool(crux_metrics and "LARGEST_CONTENTFUL_PAINT_MS" in crux_metrics)

            if has_crux:
                crux_lcp_ms = float(crux_metrics.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("percentile", 2500))
                crux_inp_ms = float(crux_metrics.get("INTERACTION_TO_NEXT_PAINT", {}).get("percentile", 200))
                crux_cls_val = float(crux_metrics.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile", 10)) / 100.0
                crux_ttfb_ms = float(crux_metrics.get("EXPERIMENTAL_TIME_TO_FIRST_BYTE", {}).get("percentile", 800))

                metrics = [
                    self._evaluate_metric("LCP", crux_lcp_ms / 1000.0),
                    self._evaluate_metric("CLS", crux_cls_val),
                    self._evaluate_metric("INP", crux_inp_ms),
                    self._evaluate_metric("TTFB", crux_ttfb_ms / 1000.0),
                ]

                return PerformanceEvidence(
                    source="pagespeed_crux_field",
                    overall_performance_score=score,
                    ttfb_ms=round(crux_ttfb_ms, 1),
                    lcp_ms=round(crux_lcp_ms, 1),
                    cls=round(crux_cls_val, 3),
                    inp_ms=round(crux_inp_ms, 1),
                    metrics=metrics,
                    passed_audit=score >= 90,
                    notes=[
                        "CrUX field data (75th percentile of real Google users).",
                        "RankIntel performance bands: 90–100=Pass, 50–89=Needs Improvement, <50=Poor (based on Lighthouse scale).",
                    ]
                )

            # Fallback to Lighthouse lab data
            audits = lighthouse.get("audits", {})
            lcp_val = audits.get("largest-contentful-paint", {}).get("numericValue", 2500) / 1000.0  # seconds
            cls_val = audits.get("cumulative-layout-shift", {}).get("numericValue", 0.05)
            fcp_val = audits.get("first-contentful-paint", {}).get("numericValue", 1500)
            ttfb_val = audits.get("server-response-time", {}).get("numericValue", 400) / 1000.0  # seconds
            inp_val = audits.get("total-blocking-time", {}).get("numericValue", 150)  # ms proxy for INP in lab

            metrics = [
                self._evaluate_metric("LCP", lcp_val),
                self._evaluate_metric("CLS", cls_val),
                self._evaluate_metric("INP", inp_val),
                self._evaluate_metric("TTFB", ttfb_val),
            ]

            return PerformanceEvidence(
                source="pagespeed_lighthouse_lab",
                overall_performance_score=score,
                ttfb_ms=round(ttfb_val * 1000, 1),
                fcp_ms=round(fcp_val, 1),
                lcp_ms=round(lcp_val * 1000, 1),
                cls=round(cls_val, 3),
                inp_ms=round(inp_val, 1),
                metrics=metrics,
                passed_audit=score >= 90,
                notes=[
                    "Lighthouse lab simulation (insufficient CrUX field traffic).",
                    "RankIntel performance bands: 90–100=Pass, 50–89=Needs Improvement, <50=Poor (based on Lighthouse scale).",
                ]
            )

        except Exception:
            return None

    def _measure_local_performance(self, url: str) -> PerformanceEvidence:
        """Measure server latency locally with high precision."""
        notes = []
        timings = []
        status_code = 200

        # Run 2 sequential probe requests to measure TTFB reliably
        for _ in range(2):
            try:
                start = time.perf_counter()
                resp = requests.get(
                    url,
                    headers={'User-Agent': 'RankIntel/2.0 (Performance Probe)'},
                    timeout=8,
                    stream=True
                )
                status_code = resp.status_code
                # Read initial chunk to capture true TTFB
                _ = next(resp.iter_content(chunk_size=1024), b"")
                elapsed = time.perf_counter() - start
                timings.append(elapsed)
            except Exception as e:
                notes.append(f"Network probe warning: {e}")

        if not timings:
            return PerformanceEvidence(
                source="unavailable",
                overall_performance_score=0,
                ttfb_ms=0.0,
                lcp_ms=None,
                cls=None,
                inp_ms=None,
                metrics=[],
                passed_audit=False,
                notes=notes + ["Local TTFB probe failed — score excluded from holistic formula."],
            )

        avg_ttfb_sec = sum(timings) / len(timings)
        ttfb_ms = avg_ttfb_sec * 1000.0

        # Heuristic scoring based on official Google thresholds
        if avg_ttfb_sec <= 0.8:
            score = 85
        elif avg_ttfb_sec <= 1.8:
            score = 65
        else:
            score = 35

        ttfb_metric = self._evaluate_metric("TTFB", avg_ttfb_sec)

        return PerformanceEvidence(
            source="local_probe",
            overall_performance_score=score,
            ttfb_ms=round(ttfb_ms, 1),
            lcp_ms=None,
            cls=None,
            inp_ms=None,
            metrics=[ttfb_metric],
            passed_audit=score >= 90,
            notes=[
                "Local high-precision TTFB probe (set PAGESPEED_API_KEY for CrUX real-user telemetry).",
                "RankIntel performance bands: 90–100=Pass, 50–89=Needs Improvement, <50=Poor (based on Lighthouse scale).",
            ]
        )


    def _evaluate_metric(self, name: str, val: float) -> PerformanceMetric:
        """Evaluate a metric against CWV_THRESHOLDS."""
        spec = CWV_THRESHOLDS.get(name, {})
        good_th = spec.get("good", 1.0)
        needs_th = spec.get("needs_improvement", 2.0)
        unit = spec.get("unit", "")

        if val <= good_th:
            status = "GOOD"
        elif val <= needs_th:
            status = "NEEDS_IMPROVEMENT"
        else:
            status = "POOR"

        return PerformanceMetric(
            name=name,
            value=round(val, 3),
            unit=unit,
            status=status,
            threshold_good=good_th,
            threshold_poor=needs_th,
        )
