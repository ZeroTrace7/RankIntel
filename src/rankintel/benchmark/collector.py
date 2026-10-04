"""
Benchmark Intelligence Collector (Phase 11.1).
Orchestrates multi-engine evidence collection across the permanent 11-site benchmark
and generates structured, provenance-preserving intelligence packages per site.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from rankintel.benchmark.models import (
    BenchmarkCollectionDataset,
    SiteIntelligencePackage,
)
from rankintel.benchmark.normalizer import BenchmarkNormalizer
from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.reporters.markdown import MarkdownReporter

logger = logging.getLogger(__name__)

# Permanent 11-Site Benchmark (AGENTS.md Section 7)
PERMANENT_11_SITES: List[Dict[str, str]] = [
    {
        "name": "Aleph India",
        "domain": "alephindia.in",
        "url": "https://alephindia.in/",
        "role": "competitor",
    },
    {
        "name": "TCR Engineering",
        "domain": "tcreng.com",
        "url": "https://www.tcreng.com/",
        "role": "competitor",
    },
    {
        "name": "Zauba Corp",
        "domain": "zaubacorp.com",
        "url": "https://www.zaubacorp.com/",
        "role": "competitor",
    },
    {
        "name": "Yadav Measurements",
        "domain": "yadavmeasurements.com",
        "url": "https://www.yadavmeasurements.com/",
        "role": "competitor",
    },
    {
        "name": "Unique Measurement",
        "domain": "uniquemeasurement.com",
        "url": "https://www.uniquemeasurement.com/",
        "role": "competitor",
    },
    {
        "name": "Quality International",
        "domain": "qualityinternational.org",
        "url": "https://qualityinternational.org/",
        "role": "competitor",
    },
    {
        "name": "ASC Group",
        "domain": "ascgroup.in",
        "url": "https://www.ascgroup.in/",
        "role": "competitor",
    },
    {
        "name": "Standphill India",
        "domain": "standphillindia.in",
        "url": "https://www.standphillindia.in/",
        "role": "competitor",
    },
    {
        "name": "UMS PCS",
        "domain": "umspcs.in",
        "url": "https://umspcs.in/",
        "role": "competitor",
    },
    {
        "name": "SQC Certification",
        "domain": "sqccertification.com",
        "url": "https://sqccertification.com/",
        "role": "competitor",
    },
    {
        "name": "Sunrise Testing",
        "domain": "sunrisetesting.vercel.app",
        "url": "https://sunrisetesting.vercel.app/",
        "role": "sunrise",
    },
]


def _clean_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "").replace(":", "_")


def _execute_site_worker(
    site_info: Dict[str, str],
    audits_dir: str,
    packages_dir: str,
    external_ai: bool = False,
    external_providers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Process-isolated worker: audits a single site through the full RankIntel pipeline,
    generates Markdown/JSON audits, normalizes into SiteIntelligencePackage, and persists it.
    """
    url = site_info["url"]
    name = site_info.get("name", "")
    role = site_info.get("role", "competitor")
    domain = site_info.get("domain") or _clean_domain(url)

    t0 = time.time()
    try:
        collector = EvidenceCollector(
            enable_external_visibility=external_ai,
            external_providers=external_providers,
        )
        engine_results = collector.collect(
            url,
            enable_external_visibility=external_ai,
            external_providers=external_providers,
        )

        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize(url, engine_results)

        elapsed = round(time.time() - t0, 2)

        # Save Markdown and JSON audit reports
        os.makedirs(audits_dir, exist_ok=True)
        md_path = MarkdownReporter.save(report, output_dir=audits_dir)
        json_path = JsonReporter.save_audit(report, output_dir=audits_dir)

        # Normalize into SiteIntelligencePackage
        package = BenchmarkNormalizer.normalize(
            url=url,
            report=report,
            engine_results=engine_results,
            name=name,
            role=role,
            execution_time_sec=elapsed,
            crawl_limitations=[
                "Single-page multi-engine collection pass",
                "Process-isolated worker execution",
                "Socket timeout: 15.0s",
                "Respects robots.txt directives",
            ],
            raw_report_paths={
                "markdown_audit": md_path,
                "json_audit": json_path,
            },
        )

        # Persist individual site package
        os.makedirs(packages_dir, exist_ok=True)
        pkg_file = os.path.join(packages_dir, f"{domain}.json")
        with open(pkg_file, "w", encoding="utf-8") as f:
            f.write(package.model_dump_json(indent=2))

        return package.model_dump()

    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        err_package = SiteIntelligencePackage(
            site_url=url,
            domain=domain,
            name=name,
            role=role,
            collection_timestamp=datetime.now().strftime("%Y-%m-%d"),
            collection_status="FAILED",
            error_message=str(e),
            execution_time_sec=elapsed,
        )
        # Still write error package for provenance
        os.makedirs(packages_dir, exist_ok=True)
        pkg_file = os.path.join(packages_dir, f"{domain}.json")
        with open(pkg_file, "w", encoding="utf-8") as f:
            f.write(err_package.model_dump_json(indent=2))
        return err_package.model_dump()


class BenchmarkCollector:
    """Manages collection across all benchmark sites and compiles the aggregate dataset."""

    def __init__(
        self,
        audits_dir: str = "audits",
        packages_dir: str = "benchmarks/packages",
        external_ai: bool = False,
        external_providers: Optional[List[str]] = None,
    ):
        self.audits_dir = audits_dir
        self.packages_dir = packages_dir
        self.external_ai = external_ai
        self.external_providers = external_providers

    def collect_site(self, site_info: Dict[str, str]) -> SiteIntelligencePackage:
        """Synchronously collect intelligence for a single site."""
        res_dict = _execute_site_worker(
            site_info=site_info,
            audits_dir=self.audits_dir,
            packages_dir=self.packages_dir,
            external_ai=self.external_ai,
            external_providers=self.external_providers,
        )
        return SiteIntelligencePackage.model_validate(res_dict)

    def collect_all(
        self,
        sites: Optional[List[Dict[str, str]]] = None,
        workers: int = 3,
        dataset_output_path: Optional[str] = None,
    ) -> BenchmarkCollectionDataset:
        """
        Execute concurrent benchmark intelligence collection across all sites
        using ProcessPoolExecutor for true process isolation.
        """
        target_sites = sites or PERMANENT_11_SITES
        wall_start = time.time()

        packages: Dict[str, SiteIntelligencePackage] = {}
        summary_matrix: List[Dict[str, Any]] = []

        print(f"\n{'='*80}")
        print(f"  RankIntel Phase 11.1 — Benchmark Intelligence Collection Layer")
        print(f"  Target Population: {len(target_sites)} permanent benchmark sites")
        print(f"  Worker Processes: {workers} (ProcessPoolExecutor)")
        print(f"  External AI: {'ENABLED' if self.external_ai else 'DISABLED (Strictly Opt-In)'}")
        print(f"{'='*80}\n")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_site = {
                executor.submit(
                    _execute_site_worker,
                    site_info,
                    self.audits_dir,
                    self.packages_dir,
                    self.external_ai,
                    self.external_providers,
                ): site_info
                for site_info in target_sites
            }

            for future in as_completed(future_to_site):
                site_info = future_to_site[future]
                site_url = site_info["url"]
                domain = site_info.get("domain") or _clean_domain(site_url)

                try:
                    pkg_dict = future.result(timeout=300)
                    pkg = SiteIntelligencePackage.model_validate(pkg_dict)
                    packages[domain] = pkg

                    # Add row to summary matrix
                    summary_row = {
                        "site": pkg.site_url,
                        "domain": pkg.domain,
                        "name": pkg.name,
                        "role": pkg.role,
                        "collection_status": pkg.collection_status,
                        "overall_health_score": pkg.overall_health_score,
                        "technical_health_score": pkg.technical_health_score,
                        "geo_readiness_score": pkg.geo_readiness_score,
                        "trust_score": pkg.trust_score,
                        "performance_score": pkg.performance_score,
                        "score_formula_mode": pkg.score_formula_mode,
                        "formula_invariance_verified": pkg.formula_invariance_verified,
                        "ttfb_ms": pkg.technical_seo.ttfb_ms,
                        "m10_1_allowed_search_bots": pkg.retrieval_readiness.search_index_allowed_count,
                        "m10_1_waf_barrier": "Blocked" if pkg.retrieval_readiness.waf_blocked else ("Detected" if pkg.retrieval_readiness.waf_or_challenge_detected else "None"),
                        "m10_2_answer_units": pkg.answerability.total_units_detected,
                        "m10_3_claims_grounded": f"{pkg.claim_grounding.supported_claims_count}/{pkg.claim_grounding.total_claims_detected}",
                        "m10_4_visual_assets": pkg.multimodal.total_visual_assets,
                        "m10_4_agent_forms": pkg.agent_readiness.total_forms_detected,
                        "m10_5_external_ai_status": pkg.external_ai.status.value,
                        "execution_time_sec": pkg.execution_time_sec,
                    }
                    summary_matrix.append(summary_row)

                    status_icon = "[OK]" if pkg.collection_status == "SUCCESS" else ("[PARTIAL]" if pkg.collection_status == "PARTIAL" else "[FAIL]")
                    print(
                        f"  {status_icon:<9} [{pkg.collection_status}] {pkg.domain:<28} "
                        f"Health: {pkg.overall_health_score:>2}/100 | "
                        f"Units: {pkg.answerability.total_units_detected:>2} | "
                        f"Claims: {pkg.claim_grounding.supported_claims_count:>2}/{pkg.claim_grounding.total_claims_detected:<2} | "
                        f"Assets: {pkg.multimodal.total_visual_assets:>3} | "
                        f"Time: {pkg.execution_time_sec:>5.2f}s",
                        flush=True,
                    )

                except Exception as exc:
                    print(f"  [ERROR] {domain}: Worker execution failed - {exc}", flush=True)
                    err_pkg = SiteIntelligencePackage(
                        site_url=site_url,
                        domain=domain,
                        name=site_info.get("name", domain),
                        role=site_info.get("role", "competitor"),
                        collection_timestamp=datetime.now().strftime("%Y-%m-%d"),
                        collection_status="FAILED",
                        error_message=str(exc),
                    )
                    packages[domain] = err_pkg
                    summary_matrix.append({
                        "site": site_url,
                        "domain": domain,
                        "name": err_pkg.name,
                        "role": err_pkg.role,
                        "collection_status": "FAILED",
                        "error": str(exc),
                    })

        wall_elapsed = round(time.time() - wall_start, 2)
        succeeded = sum(1 for p in packages.values() if p.collection_status == "SUCCESS")
        partial = sum(1 for p in packages.values() if p.collection_status == "PARTIAL")
        failed = sum(1 for p in packages.values() if p.collection_status == "FAILED")

        dataset = BenchmarkCollectionDataset(
            benchmark_version="11.1",
            created_at=datetime.now().isoformat(),
            wall_clock_sec=wall_elapsed,
            workers_used=workers,
            total_sites=len(target_sites),
            sites_succeeded=succeeded,
            sites_partial=partial,
            sites_failed=failed,
            sites_list=[s["url"] for s in target_sites],
            packages=packages,
            summary_matrix=summary_matrix,
        )

        # Save aggregate dataset JSON
        save_path = dataset_output_path or os.path.join("benchmarks", "benchmark_dataset_phase11.json")
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(dataset.model_dump_json(indent=2))

        print(f"\n{'='*80}")
        print(f"  BENCHMARK COLLECTION COMPLETE")
        print(f"  Total wall-clock time: {wall_elapsed:.2f}s (Average {wall_elapsed/len(target_sites):.2f}s/site)")
        print(f"  Status: {succeeded} SUCCESS, {partial} PARTIAL, {failed} FAILED (Total: {len(target_sites)})")
        print(f"  Per-site packages: {os.path.abspath(self.packages_dir)}/")
        print(f"  Per-site audits:   {os.path.abspath(self.audits_dir)}/")
        print(f"  Dataset saved to:  {os.path.abspath(save_path)}")
        print(f"{'='*80}\n")

        return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="RankIntel Phase 11.1 Benchmark Intelligence Collector")
    parser.add_argument("--workers", type=int, default=3, help="Number of worker processes (default: 3)")
    parser.add_argument("--audits-dir", type=str, default="audits", help="Directory to save per-site audit markdown/json")
    parser.add_argument("--packages-dir", type=str, default="benchmarks/packages", help="Directory to save per-site structured packages")
    parser.add_argument("--output-dataset", type=str, default="benchmarks/benchmark_dataset_phase11.json", help="Path for aggregate benchmark dataset")
    parser.add_argument("--external-ai", action="store_true", help="Enable external AI visibility measurement (strictly opt-in)")
    parser.add_argument("--external-providers", type=str, default=None, help="Comma-separated provider names (e.g. gemini,mock)")

    args = parser.parse_args()

    prov_list = [p.strip() for p in args.external_providers.split(",")] if args.external_providers else None

    collector = BenchmarkCollector(
        audits_dir=args.audits_dir,
        packages_dir=args.packages_dir,
        external_ai=args.external_ai,
        external_providers=prov_list,
    )

    collector.collect_all(
        workers=args.workers,
        dataset_output_path=args.output_dataset,
    )


if __name__ == "__main__":
    main()
