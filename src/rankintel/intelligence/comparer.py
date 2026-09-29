"""
Competitor Gap Analysis & Comparison Engine.
Ported and enhanced from geo-optimizer gap_analysis.py architecture.
Audits two targets and generates an actionable competitive gap report.
"""
from __future__ import annotations
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Tuple

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.models.schema import (
    SynthesisReport,
    ComparisonReport,
    GapDelta,
    GapAction
)

class IntelligenceComparer:
    """Executes multi-engine audits on both targets and computes competitive gap intelligence."""

    def __init__(self):
        self.collector = EvidenceCollector()
        self.synthesizer = IntelligenceSynthesizer()

    def compare(self, url_a: str, url_b: str) -> ComparisonReport:
        """Run audits on both URLs and produce a competitive gap comparison report."""
        if not url_a.startswith("http"):
            url_a = "https://" + url_a
        if not url_b.startswith("http"):
            url_b = "https://" + url_b

        # Audit Target A
        results_a = self.collector.collect(url_a)
        report_a = self.synthesizer.synthesize(url_a, results_a)

        # Audit Target B
        results_b = self.collector.collect(url_b)
        report_b = self.synthesizer.synthesize(url_b, results_b)

        return self.build_comparison(report_a, report_b)

    def build_comparison(self, report_a: SynthesisReport, report_b: SynthesisReport) -> ComparisonReport:
        """Build comparison report and gap action plan from two SynthesisReports."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        score_gap = abs(report_a.overall_health_score - report_b.overall_health_score)

        if report_a.overall_health_score > report_b.overall_health_score:
            winner_url = report_a.url
        elif report_b.overall_health_score > report_a.overall_health_score:
            winner_url = report_b.url
        else:
            winner_url = "TIE"

        deltas: List[GapDelta] = []

        # 1. Overall Health
        deltas.append(GapDelta(
            category="Overall Search & GEO Health",
            target_a_val=f"{report_a.overall_health_score}/100",
            target_b_val=f"{report_b.overall_health_score}/100",
            winner=report_a.url if report_a.overall_health_score > report_b.overall_health_score else (report_b.url if report_b.overall_health_score > report_a.overall_health_score else "TIE"),
            impact="Comprehensive triangulation across technical SEO, GEO citability, trust stack, and performance."
        ))

        # 2. Technical SEO
        deltas.append(GapDelta(
            category="Technical SEO Foundation",
            target_a_val=f"{report_a.technical_health_score}/100",
            target_b_val=f"{report_b.technical_health_score}/100",
            winner=report_a.url if report_a.technical_health_score > report_b.technical_health_score else (report_b.url if report_b.technical_health_score > report_a.technical_health_score else "TIE"),
            impact="Meta tags, heading structure, canonicalization, and crawl hygiene."
        ))

        # 3. GEO Citability
        deltas.append(GapDelta(
            category="GEO / AI Search Readiness",
            target_a_val=f"{report_a.geo_readiness_score}/100",
            target_b_val=f"{report_b.geo_readiness_score}/100",
            winner=report_a.url if report_a.geo_readiness_score > report_b.geo_readiness_score else (report_b.url if report_b.geo_readiness_score > report_a.geo_readiness_score else "TIE"),
            impact="Princeton GEO scoring, answer-first density, and LLM citability."
        ))

        # 4. Trust Stack (E-E-A-T)
        deltas.append(GapDelta(
            category="Trust Stack & E-E-A-T Grade",
            target_a_val=f"{report_a.unified_trust.grade} ({report_a.trust_score}/100)",
            target_b_val=f"{report_b.unified_trust.grade} ({report_b.trust_score}/100)",
            winner=report_a.url if report_a.trust_score > report_b.trust_score else (report_b.url if report_b.trust_score > report_a.trust_score else "TIE"),
            impact="5-layer trust: security headers, identity, social proof, citations, and compliance."
        ))

        # 5. Performance / TTFB
        deltas.append(GapDelta(
            category="Server Responsiveness (TTFB)",
            target_a_val=f"{report_a.unified_performance.ttfb_ms:.0f}ms",
            target_b_val=f"{report_b.unified_performance.ttfb_ms:.0f}ms",
            winner=report_a.url if report_a.unified_performance.ttfb_ms < report_b.unified_performance.ttfb_ms else (report_b.url if report_b.unified_performance.ttfb_ms < report_a.unified_performance.ttfb_ms else "TIE"),
            impact="Time to First Byte latency affects crawl efficiency and user perception."
        ))

        # 6. /llms.txt manifest
        deltas.append(GapDelta(
            category="Machine-Readable /llms.txt",
            target_a_val="Present" if report_a.unified_geo.llms_txt_found else "Missing",
            target_b_val="Present" if report_b.unified_geo.llms_txt_found else "Missing",
            winner=report_a.url if report_a.unified_geo.llms_txt_found and not report_b.unified_geo.llms_txt_found else (report_b.url if report_b.unified_geo.llms_txt_found and not report_a.unified_geo.llms_txt_found else "TIE"),
            impact="Provides curated context to LLM crawlers (ChatGPT, Claude, Perplexity)."
        ))

        # 7. AI Search Bots Allowed
        bots_a = len([b for b in report_a.unified_robots.bot_access.values() if b.status == "ALLOWED" and b.category == "search"])
        bots_b = len([b for b in report_b.unified_robots.bot_access.values() if b.status == "ALLOWED" and b.category == "search"])
        deltas.append(GapDelta(
            category="AI Search Bots Allowed",
            target_a_val=f"{bots_a} Allowed",
            target_b_val=f"{bots_b} Allowed",
            winner=report_a.url if bots_a > bots_b else (report_b.url if bots_b > bots_a else "TIE"),
            impact="Access for OAI-SearchBot, Claude-SearchBot, PerplexityBot, and Applebot."
        ))

        # 8. Organic Traffic & Keywords (Cloud Intelligence)
        cloud_a = report_a.cloud_intelligence
        cloud_b = report_b.cloud_intelligence
        if cloud_a.available or cloud_b.available:
            traf_a = cloud_a.keywords.estimated_monthly_traffic if (cloud_a.available and cloud_a.keywords) else 0
            traf_b = cloud_b.keywords.estimated_monthly_traffic if (cloud_b.available and cloud_b.keywords) else 0
            deltas.append(GapDelta(
                category="Estimated Organic Search Traffic",
                target_a_val=f"{traf_a:,} visits/mo" if cloud_a.available else "N/A (local)",
                target_b_val=f"{traf_b:,} visits/mo" if cloud_b.available else "N/A (local)",
                winner=report_a.url if traf_a > traf_b else (report_b.url if traf_b > traf_a else "TIE"),
                impact="Estimated monthly organic visitors driven by search index keyword breadth."
            ))

        # Build Action Plan targeting the weaker site
        action_plan = self._build_gap_actions(report_a, report_b)

        return ComparisonReport(
            target_a_url=report_a.url,
            target_b_url=report_b.url,
            timestamp=timestamp,
            target_a_report=report_a,
            target_b_report=report_b,
            winner_url=winner_url,
            score_gap=score_gap,
            category_deltas=deltas,
            action_plan=action_plan
        )

    def _build_gap_actions(self, rep_a: SynthesisReport, rep_b: SynthesisReport) -> List[GapAction]:
        actions: List[GapAction] = []

        # Identify which site is weaker or compare reciprocally
        weaker, stronger = (rep_a, rep_b) if rep_a.overall_health_score <= rep_b.overall_health_score else (rep_b, rep_a)
        w_dom = urlparse(weaker.url).netloc
        s_dom = urlparse(stronger.url).netloc

        # 1. /llms.txt gap
        if stronger.unified_geo.llms_txt_found and not weaker.unified_geo.llms_txt_found:
            actions.append(GapAction(
                category="AI Discovery",
                title=f"Deploy /llms.txt manifest to close gap with {s_dom}",
                rationale=f"{s_dom} exposes a valid /llms.txt manifest giving AI crawlers clean structured documentation, while {w_dom} has none.",
                impact_points=15,
                priority="HIGH",
                winning_advantage=f"{s_dom} is indexable by Autonomous AI agents.",
                remediation_suggestion=f"Use `rankintel audit {weaker.url}` to copy-paste the auto-generated /llms.txt file to your root web server."
            ))

        # 2. Schema Organization gap
        if stronger.unified_schema.has_organization and not weaker.unified_schema.has_organization:
            actions.append(GapAction(
                category="Structured Data",
                title="Implement Organization Schema & Knowledge Graph Anchors",
                rationale=f"{s_dom} explicitly specifies an Organization entity in JSON-LD structured data, while {w_dom} lacks organization schema.",
                impact_points=12,
                priority="HIGH",
                winning_advantage=f"{s_dom} is recognized by Google Knowledge Graph and AI search models.",
                remediation_suggestion="Add Organization JSON-LD markup with name, url, logo, and sameAs social profile URLs."
            ))

        # 3. Answer-first H2 gap
        if stronger.unified_geo.answer_first_ratio > weaker.unified_geo.answer_first_ratio + 0.2:
            actions.append(GapAction(
                category="GEO Optimization",
                title="Restructure Content with Answer-First Paragraphs",
                rationale=f"{s_dom} has {int(stronger.unified_geo.answer_first_ratio * 100)}% answer-first H2 density vs {int(weaker.unified_geo.answer_first_ratio * 100)}% on {w_dom}.",
                impact_points=10,
                priority="MEDIUM",
                winning_advantage=f"{s_dom} passages are directly extractable into AI Overviews and ChatGPT summaries.",
                remediation_suggestion="Ensure each H2 heading is immediately followed by a concise 40-60 word factual answer with concrete numbers."
            ))

        # 4. Security Headers / Trust gap
        tech_s = stronger.unified_trust.layers.get("technical")
        tech_w = weaker.unified_trust.layers.get("technical")
        if tech_s and tech_w and tech_s.score > tech_w.score:
            missing_in_w = [s for s in tech_w.signals_missing if any(h in s for h in ["HSTS", "CSP", "X-Frame-Options"])]
            if missing_in_w:
                actions.append(GapAction(
                    category="Technical Trust",
                    title="Harden Security Headers (HSTS / CSP)",
                    rationale=f"{s_dom} implements rigorous security headers. {w_dom} is missing: {', '.join(missing_in_w)}.",
                    impact_points=8,
                    priority="MEDIUM",
                    winning_advantage=f"{s_dom} scores higher in technical trustworthiness and crawler reliability.",
                    remediation_suggestion="Configure web server to emit Strict-Transport-Security and Content-Security-Policy headers."
                ))

        # 5. Latency gap
        if weaker.unified_performance.ttfb_ms > stronger.unified_performance.ttfb_ms + 400:
            actions.append(GapAction(
                category="Performance",
                title="Optimize Server Response Latency (TTFB)",
                rationale=f"{w_dom} has TTFB of {weaker.unified_performance.ttfb_ms:.0f}ms compared to {stronger.unified_performance.ttfb_ms:.0f}ms on {s_dom}.",
                impact_points=8,
                priority="MEDIUM",
                winning_advantage=f"{s_dom} serves pages faster to crawlers and users.",
                remediation_suggestion="Enable Edge CDN caching (Cloudflare/Fastly) and optimize database queries for initial HTML generation."
            ))

        # 6. Authority & Backlinks Gap (Cloud Intelligence)
        cloud_s = stronger.cloud_intelligence
        cloud_w = weaker.cloud_intelligence
        if cloud_s.available and cloud_w.available:
            ref_s = cloud_s.backlinks.referring_domains if cloud_s.backlinks else 0
            ref_w = cloud_w.backlinks.referring_domains if cloud_w.backlinks else 0
            if ref_s > ref_w * 2 and ref_s > 10:
                actions.append(GapAction(
                    category="Authority & Backlinks",
                    title=f"Expand Digital PR & Referring Domains to bridge gap with {s_dom}",
                    rationale=f"{s_dom} possesses {ref_s} referring domains vs {ref_w} on {w_dom}.",
                    impact_points=12,
                    priority="HIGH",
                    winning_advantage=f"{s_dom} has a much stronger backlink moat and PageRank authority.",
                    remediation_suggestion="Execute targeted digital PR, partner integrations, and publish original statistical data to attract organic citations."
                ))

        actions.sort(key=lambda a: a.impact_points, reverse=True)
        return actions
