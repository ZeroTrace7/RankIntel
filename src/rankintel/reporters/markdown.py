"""
Markdown Audit Report Generator — Formats multi-engine triangulated evidence
into copy-paste ready, executive-grade Markdown audits.
"""
from __future__ import annotations
import os
from rankintel.models.schema import SynthesisReport

class MarkdownReporter:
    """Generates comprehensive, beautifully formatted Markdown audits."""

    @staticmethod
    def render(report: SynthesisReport) -> str:
        lines: list[str] = []

        lines.append(f"# RANKINTEL INTELLIGENCE REPORT — {report.domain}")
        lines.append(f"**URL:** {report.url}")
        lines.append(f"**Date:** {report.timestamp}")
        lines.append(f"**Audit Platform:** RankIntel Multi-Engine Intelligence v2.0")
        lines.append(f"**Engines Triangulated:** {', '.join(report.engines_executed)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Executive Scorecard
        lines.append("## 📊 EXECUTIVE SCORECARD")
        lines.append(f"- **Overall Search Health Score:** {report.overall_health_score}/100")
        lines.append(f"- **Technical SEO Score:** {report.technical_health_score}/100")
        lines.append(f"- **GEO / AI Search Readiness:** {report.geo_readiness_score}/100")
        lines.append("")

        # Cross-Engine Conflicts
        if report.conflicts_detected:
            lines.append("## 🔍 CROSS-ENGINE TRIANGULATION & CONFLICTS")
            lines.append("*(Discrepancies discovered when reconciling static, browser DOM, and GEO engines)*\n")
            for c in report.conflicts_detected:
                sev_icon = "🔴" if c.severity in ("HIGH", "CRITICAL") else "🟡"
                lines.append(f"### {sev_icon} [{c.severity}] {c.feature}")
                lines.append(f"- **Observation:** {c.description}")
                lines.append(f"- **Engine A:** {c.engine_a_finding}")
                lines.append(f"- **Engine B:** {c.engine_b_finding}")
                lines.append(f"- **RankIntel Interpretation:** {c.interpretation}\n")
        else:
            lines.append("## 🔍 CROSS-ENGINE TRIANGULATION")
            lines.append("🟢 **Engine Consensus:** Static crawler, browser renderer, and GEO analyzers are in full agreement across core telemetry.\n")

        # Technical Foundation
        p = report.unified_on_page
        lines.append("## ⚙️ TECHNICAL FOUNDATION")
        lines.append(f"- **HTTP Status Code:** {p.status_code}")
        lines.append(f"- **Server Latency (TTFB):** {p.response_time_sec}s")
        lines.append(f"- **Redirect Detected:** {p.is_redirect}")
        lines.append(f"- **Canonical URL:** {p.canonical_url or '⚪ Not specified'}")
        lines.append("")

        # On-Page Signals
        lines.append("## 📝 ON-PAGE ARCHITECTURE")
        lines.append(f"- **Title Tag:** {p.title} ({p.title_length} chars)")
        lines.append(f"- **Meta Description:** {p.meta_description} ({p.meta_desc_length} chars)")
        lines.append(f"- **Word Count:** ~{p.word_count} words")
        lines.append(f"- **H1 Tags ({p.h1_count}):** {', '.join(p.h1_text) if p.h1_text else '🔴 NONE FOUND'}")
        lines.append(f"- **H2 Tags ({p.h2_count}):** {len(p.h2_text)} found")
        
        alt_pct = round(p.images_with_alt / p.total_images * 100, 1) if p.total_images > 0 else 100.0
        lines.append(f"- **Image Alt Coverage:** {p.images_with_alt} / {p.total_images} images have alt attributes ({alt_pct}%)")
        lines.append("")

        # Structured Data
        s = report.unified_schema
        lines.append("## 🏗️ STRUCTURED DATA (SCHEMA.ORG)")
        if s.detected_types:
            lines.append(f"- **Detected Schemas:** {', '.join(s.detected_types)}")
        else:
            lines.append("- **Detected Schemas:** 🔴 NONE DETECTED")

        if s.is_injected_via_js:
            lines.append("- **Client-Side Dependency:** ⚠️ Schemas are injected via client-side JavaScript")

        if s.deprecated_types_detected:
            lines.append(f"- **Deprecated Schemas:** ⚠️ {', '.join(s.deprecated_types_detected)}")
        lines.append("")

        # AI Bot Matrix
        r = report.unified_robots
        lines.append("## 🤖 AI CRAWLER ACCESS MATRIX")
        lines.append("*(Triangulated against RFC-compliant robots.txt rules)*\n")
        lines.append("| Bot Name | Category | Status | Target Engine / Role |")
        lines.append("|---|---|---|---|")
        for bot, info in r.bot_access.items():
            icon = "🟢" if info.status == "ALLOWED" else ("🔴" if info.status == "BLOCKED" else "⚪")
            lines.append(f"| **{bot}** | {info.category.upper()} | {icon} {info.status} | {info.role_or_purpose or info.engine} |")
        lines.append("")

        # GEO Citability
        g = report.unified_geo
        lines.append("## 🧠 GENERATIVE ENGINE OPTIMIZATION (GEO / AEO)")
        lines.append(f"- **Princeton GEO Citability Score:** {g.overall_citability_score}/100")
        lines.append(f"- **Machine-Readable /llms.txt:** {'🟢 PRESENT' if g.llms_txt_found else '🔴 MISSING'}")
        lines.append(f"- **Answer-First H2 Ratio:** {int(g.answer_first_ratio * 100)}% of H2 sections begin with direct factual answers")
        lines.append(f"- **Dense Citability Passages:** {int(g.passage_density_ratio * 100)}% of paragraphs contain high-density numeric data")
        lines.append(f"- **Statistical Data Density:** {g.statistical_density_per_1000} data points per 1,000 words")
        lines.append(f"- **Authoritative Outbound Citations:** {g.authoritative_citations_count} verified high-authority citations")
        lines.append("")

        if g.question_h2s:
            lines.append(f"### Interrogative H2 Queries Identified ({len(g.question_h2s)}):")
            for q in g.question_h2s[:6]:
                lines.append(f"- {q}")
            lines.append("")

        # Prioritized Action Plan
        lines.append("## 📋 PRIORITIZED ACTION PLAN")
        for action in report.prioritized_actions:
            icon = "🔴" if action.level == "CRITICAL" else ("🟠" if action.level == "HIGH" else ("🟡" if action.level == "MEDIUM" else "🟢"))
            lines.append(f"### {icon} [{action.level}] {action.title}")
            lines.append(f"- **Finding:** {action.finding}")
            lines.append(f"- **Rationale:** {action.rationale}")
            lines.append(f"- **Confidence:** {action.engine_confidence}\n")

        # Copy-Paste Ready Production Assets
        lines.append("## 🚀 PRODUCTION-READY FIXES (COPY & PASTE)")
        
        lines.append("### 1. Optimized Metadata")
        lines.append(f"**Target Title ({report.fixes.get('title_length', 55)} chars):**")
        lines.append(f"```html\n<title>{report.fixes.get('optimized_title', '')}</title>\n```")
        lines.append(f"**Target Description ({report.fixes.get('desc_length', 150)} chars):**")
        lines.append(f"```html\n<meta name=\"description\" content=\"{report.fixes.get('optimized_description', '')}\">\n```\n")

        lines.append("### 2. Valid Schema.org JSON-LD Markup")
        lines.append("```html")
        lines.append(report.fixes.get("jsonld_schema", ""))
        lines.append("```\n")

        lines.append("### 3. Machine-Readable /llms.txt")
        lines.append("```markdown")
        lines.append(report.fixes.get("llms_txt", ""))
        lines.append("```\n")

        lines.append("### 4. Hardened AI robots.txt")
        lines.append("```robots.txt")
        lines.append(report.fixes.get("hardened_robots", ""))
        lines.append("```\n")

        return "\n".join(lines)

    @staticmethod
    def save(report: SynthesisReport, output_dir: str = "audits") -> str:
        os.makedirs(output_dir, exist_ok=True)
        domain_clean = report.domain.replace("www.", "")
        filename = f"{domain_clean}-{report.timestamp}.md"
        path = os.path.join(output_dir, filename)
        content = MarkdownReporter.render(report)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
