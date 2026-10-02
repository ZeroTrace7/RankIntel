"""
M6.8.3 — Multi-Process Parallel Benchmark Runner for RankIntel.

Runs the permanent 11-site benchmark with true OS-process isolation.
Each site gets its own Python interpreter, event loop, GIL, and log file.

Usage:
    venv\Scripts\python.exe benchmark_11_sites.py [--workers N] [--max-pages N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# ── Permanent 11-Site Benchmark (AGENTS.md Section 7) ──────────────────────
SITES = [
    "https://alephindia.in/",
    "https://www.tcreng.com/",
    "https://www.zaubacorp.com/",
    "https://www.yadavmeasurements.com/",
    "https://www.uniquemeasurement.com/",
    "https://qualityinternational.org/",
    "https://www.ascgroup.in/",
    "https://www.standphillindia.in/",
    "https://umspcs.in/",
    "https://sqccertification.com/",
    "https://sunrisetesting.vercel.app/",
]


def _get_domain(url: str) -> str:
    """Extract clean domain name for filenames."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    return domain


def _run_site_worker(site: str, max_pages: int, log_dir: str, audit_dir: str) -> Dict[str, Any]:
    """
    Worker function executed in an INDEPENDENT OS process.
    Each invocation has its own Python interpreter, GIL, and event loop.
    
    Returns a structured dict with crawl results or error info.
    """
    domain = _get_domain(site)
    log_path = os.path.join(log_dir, f"{domain}.log")
    
    # Configure per-process logging to dedicated file
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    logger = logging.getLogger(f"benchmark.{domain}")
    logger.info("Starting benchmark for %s (max_pages=%d)", site, max_pages)
    
    t0 = time.time()
    try:
        from rankintel.crawler.deep_crawler import AsyncDeepCrawler
        from rankintel.models.schema import CrawlConfig
        
        config = CrawlConfig(
            max_pages=max_pages,
            max_depth=3,
            concurrency=3,
            crawl_delay=0.2,
            timeout_sec=15.0,
            enable_sitemap_analysis=True,
            enable_browser_rendering=True,
        )
        crawler = AsyncDeepCrawler(config=config)
        result = asyncio.run(crawler.crawl(site))
        
        elapsed = round(time.time() - t0, 2)
        logger.info("Completed %s in %.2fs", site, elapsed)
        
        # Write per-site audit report (AGENTS.md Section 3)
        _write_audit_report(site, domain, result, elapsed, audit_dir)
        
        return {
            "site": site,
            "domain": domain,
            "status": "OK",
            "elapsed_sec": elapsed,
            "pages_discovered": result.pages_discovered,
            "pages_crawled": result.pages_crawled,
            "sitemap_only_urls": result.sitemap_only_urls,
            "rendered_only_urls": result.rendered_only_urls,
            "pages_blocked": result.pages_blocked,
            "pages_failed": result.pages_failed,
            "pages_queued": result.pages_queued,
            "completeness_status": result.completeness_status,
            "crawl_duration_sec": result.crawl_duration_sec,
            "log_file": log_path,
        }
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        logger.exception("FAILED: %s — %s", site, e)
        return {
            "site": site,
            "domain": domain,
            "status": "ERROR",
            "error": str(e),
            "elapsed_sec": elapsed,
            "log_file": log_path,
        }


def _write_audit_report(
    site: str, domain: str, result: Any, elapsed: float, audit_dir: str
) -> None:
    """Write per-site audit markdown to audits/{domain}-{YYYY-MM-DD}.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(audit_dir, f"{domain}-{today}.md")
    
    lines = [
        f"# Audit Report: {site}",
        f"**Date**: {today}",
        f"**Engine**: RankIntel AsyncDeepCrawler",
        f"**Duration**: {elapsed}s",
        "",
        "## Crawl Summary",
        f"- Pages Discovered: {result.pages_discovered}",
        f"- Pages Crawled: {result.pages_crawled}",
        f"- Sitemap-only URLs: {result.sitemap_only_urls}",
        f"- Rendered-only URLs: {result.rendered_only_urls}",
        f"- Pages Blocked: {result.pages_blocked}",
        f"- Pages Failed: {result.pages_failed}",
        f"- Completeness: {result.completeness_status}",
        "",
    ]
    
    if result.site_wide_issues:
        lines.append("## Site-Wide Issues")
        for issue in result.site_wide_issues:
            lines.append(f"- {issue}")
        lines.append("")
    
    if result.broken_links:
        lines.append("## Broken Links")
        for link in result.broken_links[:20]:  # Cap at 20
            lines.append(f"- {link}")
        if len(result.broken_links) > 20:
            lines.append(f"- ... and {len(result.broken_links) - 20} more")
        lines.append("")
    
    if result.thin_content_pages:
        lines.append("## Thin Content Pages")
        for page in result.thin_content_pages[:20]:
            lines.append(f"- {page}")
        lines.append("")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _format_row(r: Dict[str, Any]) -> str:
    """Format a result dict as a markdown table row."""
    if r["status"] == "ERROR":
        return (
            f"| {r['site']} | - | - | - | - | - | - | - | "
            f"{r.get('error', 'Unknown error')} | ERROR | {r['elapsed_sec']:.1f}s |"
        )
    coverage = f"Found {r['pages_crawled']} HTML, {r['sitemap_only_urls']} sitemap-only"
    return (
        f"| {r['site']} | {r['pages_discovered']} | {r['pages_crawled']} | "
        f"{r['sitemap_only_urls']} | {r['rendered_only_urls']} | {r['pages_blocked']} | "
        f"{r['pages_failed']} | {r['pages_queued']} | {coverage} | "
        f"{r['completeness_status']} | {r['elapsed_sec']:.1f}s |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RankIntel M6.8 Multi-Process Parallel Benchmark Runner"
    )
    parser.add_argument(
        "--workers", type=int, default=6,
        help="Number of parallel worker processes (default: 6)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=50,
        help="Maximum pages to crawl per site (default: 50)"
    )
    args = parser.parse_args()
    
    # Create output directories
    log_dir = os.path.join("benchmarks", "logs")
    audit_dir = "audits"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(audit_dir, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"  RankIntel M6.8 — Multi-Process Parallel Benchmark")
    print(f"  Sites: {len(SITES)} | Workers: {args.workers} | Max pages/site: {args.max_pages}")
    print(f"{'='*80}\n")
    
    # Table header
    header = (
        "| Site | Discovered | Crawled | Sitemap | Rendered-only | "
        "Blocked | Errors | Unfetched | Recall/coverage evidence | Status | Time |"
    )
    separator = "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|"
    
    print(header)
    print(separator)
    
    results: List[Dict[str, Any]] = []
    wall_start = time.time()
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_site = {
            executor.submit(
                _run_site_worker, site, args.max_pages, log_dir, audit_dir
            ): site
            for site in SITES
        }
        
        for future in as_completed(future_to_site):
            site = future_to_site[future]
            try:
                result = future.result(timeout=300)  # 5-minute per-site timeout
                results.append(result)
                print(_format_row(result), flush=True)
            except Exception as e:
                error_result = {
                    "site": site,
                    "domain": _get_domain(site),
                    "status": "ERROR",
                    "error": f"Process failed: {e}",
                    "elapsed_sec": 0.0,
                }
                results.append(error_result)
                print(_format_row(error_result), flush=True)
    
    wall_elapsed = round(time.time() - wall_start, 2)
    
    # Summary
    ok_count = sum(1 for r in results if r["status"] == "OK")
    err_count = sum(1 for r in results if r["status"] == "ERROR")
    
    print(f"\n{'='*80}")
    print(f"  BENCHMARK COMPLETE")
    print(f"  Total wall-clock time: {wall_elapsed:.1f}s")
    print(f"  Sites OK: {ok_count}/{len(SITES)} | Errors: {err_count}/{len(SITES)}")
    print(f"  Worker processes: {args.workers}")
    print(f"  Per-site logs: {os.path.abspath(log_dir)}/")
    print(f"  Audit reports: {os.path.abspath(audit_dir)}/")
    print(f"{'='*80}\n")
    
    # Write aggregate results JSON for programmatic consumption
    results_path = os.path.join("benchmarks", f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs("benchmarks", exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "wall_clock_sec": wall_elapsed,
            "workers": args.workers,
            "max_pages": args.max_pages,
            "sites_ok": ok_count,
            "sites_error": err_count,
            "results": results,
        }, f, indent=2)
    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
