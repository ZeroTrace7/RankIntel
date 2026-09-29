"""
RankIntel FastMCP Server — Exposes multi-engine SEO, GEO, and competitive intelligence tools.
Can be invoked by Claude, Cursor, Antigravity, or any standard MCP client.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from fastmcp import FastMCP

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.intelligence.comparer import IntelligenceComparer

mcp = FastMCP("rankintel", instructions="RankIntel Multi-Engine Search Intelligence & GEO Server")

@mcp.tool
def rankintel_audit(url: str, deep_crawl: bool = False, max_pages: int = 25) -> Dict[str, Any]:
    """
    Run full multi-engine SEO, GEO citability, Trust Stack, and CWV performance audit on a URL.
    Optionally crawls internal site pages for site-wide issues.
    """
    if not url.startswith("http"):
        url = "https://" + url

    collector = EvidenceCollector()
    results = collector.collect(url)

    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize(url, results)

    if deep_crawl:
        report.site_crawl = collector.seo_engine.crawl_site(url, max_pages=max_pages)

    return {
        "url": report.url,
        "domain": report.domain,
        "timestamp": report.timestamp,
        "overall_health_score": report.overall_health_score,
        "technical_health_score": report.technical_health_score,
        "geo_readiness_score": report.geo_readiness_score,
        "trust_score": report.trust_score,
        "trust_grade": report.unified_trust.grade,
        "performance_score": report.performance_score,
        "ttfb_ms": report.unified_performance.ttfb_ms,
        "llms_txt_present": report.unified_geo.llms_txt_found,
        "engines_executed": report.engines_executed,
        "conflicts_detected": [c.model_dump() for c in report.conflicts_detected],
        "top_prioritized_actions": [a.model_dump() for a in report.prioritized_actions[:5]],
        "provenance_chain": [p.model_dump() for p in report.provenance],
        "production_fixes": report.fixes,
        "site_crawl_summary": report.site_crawl.model_dump() if report.site_crawl else None
    }

@mcp.tool
def rankintel_compare(url_a: str, url_b: str) -> Dict[str, Any]:
    """
    Run competitive gap analysis benchmarking two websites head-to-head.
    Identifies competitive advantage, category score deltas, and strategic remediation steps.
    """
    comparer = IntelligenceComparer()
    comparison = comparer.compare(url_a, url_b)

    return {
        "target_a_url": comparison.target_a_url,
        "target_b_url": comparison.target_b_url,
        "winner_url": comparison.winner_url,
        "score_gap": comparison.score_gap,
        "target_a_score": comparison.target_a_report.overall_health_score,
        "target_b_score": comparison.target_b_report.overall_health_score,
        "category_deltas": [d.model_dump() for d in comparison.category_deltas],
        "action_plan": [a.model_dump() for a in comparison.action_plan]
    }

@mcp.tool
def rankintel_generate_fixes(url: str) -> Dict[str, str]:
    """
    Generate drop-in production code fixes for a URL:
    optimized Title/Meta Description, JSON-LD @graph structured data, /llms.txt, and hardened robots.txt.
    """
    if not url.startswith("http"):
        url = "https://" + url

    collector = EvidenceCollector()
    results = collector.collect(url)
    synthesizer = IntelligenceSynthesizer()
    report = synthesizer.synthesize(url, results)

    return report.fixes

def run_server():
    """Run MCP server via stdio transport."""
    mcp.run()

if __name__ == "__main__":
    run_server()
