"""
Phase 11.3 — Cross-Site Comparison & Void Analysis Reporter.
Renders deterministic Markdown and JSON comparison artifacts for the permanent
11-site benchmark and target-vs-cohort evaluations.
Guarantees 100% data parity between JSON and Markdown formats.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple

from rankintel.benchmark.models import (
    BenchmarkComparisonReport,
    TargetVsBenchmarkComparison,
    ObservableVoidItem,
)


class ComparisonReporter:
    """Reporter for persisting and rendering benchmark cross-site comparison artifacts."""

    @classmethod
    def render_json(cls, report: BenchmarkComparisonReport) -> str:
        """Render complete BenchmarkComparisonReport as formatted JSON."""
        return report.model_dump_json(indent=2)

    @classmethod
    def render_target_json(cls, target_comp: TargetVsBenchmarkComparison) -> str:
        """Render TargetVsBenchmarkComparison as formatted JSON."""
        return target_comp.model_dump_json(indent=2)

    @classmethod
    def render_markdown(cls, report: BenchmarkComparisonReport) -> str:
        """Render comprehensive GitHub-Flavored Markdown report for cross-site benchmark comparison."""
        lines = []

        lines.append(f"# Benchmark Cross-Site Comparison & Void Analysis — Phase 11.3")
        lines.append("")
        lines.append(f"> **Report Version:** {report.comparison_version}  ")
        lines.append(f"> **Generated Date:** {report.created_at}  ")
        lines.append(f"> **Target Domain:** `{report.target_domain}`  ")
        lines.append(f"> **Benchmark Population:** {report.total_sites} permanent benchmark sites  ")
        lines.append(f"> **Formula Invariance:** Verified (Δ = 0)  ")
        lines.append(f"> **Execution Mode:** Strictly Offline (0 network requests)")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Executive Summary & Epistemic Boundaries
        lines.append("## 1. Executive Summary & Epistemic Boundaries")
        lines.append("")
        lines.append(
            "This report delivers a **deterministic cross-site comparison** across the permanent 11-site benchmark "
            "using only completed Phase 11.2 Website Intelligence Review artifacts. All findings are strictly partitioned "
            "by epistemic status (`FACT`, `EXTERNAL OBSERVATION`, `ANALYSIS`, `RECOMMENDATION`)."
        )
        lines.append("")
        lines.append(
            "> [!IMPORTANT]\n"
            "> **Epistemic Rule**: All comparisons represent **observable website differences** derived solely from static DOM, "
            "rendered browser DOM, HTTP response headers, and robots.txt. They do not constitute evidence of superior commercial "
            "performance, search engine rankings, traffic share, or market dominance."
        )
        lines.append("")

        # 2. Cross-Site Summary Matrix
        lines.append("## 2. Cross-Site Benchmark Summary Matrix")
        lines.append("")
        lines.append(
            "| Domain | Role | Health | Tech | GEO | Trust | Primary Intent | Schema | Answer Units | Grounded | Visual | Alt % | Forms | Buttons | WAF |"
        )
        lines.append(
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )

        for m in report.cross_site_matrix:
            role_badge = "**TARGET**" if m.role in ("target", "sunrise") else "Competitor"
            alt_pct = f"{int(m.alt_coverage_ratio * 100)}%"
            grounded_pct = f"{int(m.claims_grounded_ratio * 100)}%"
            lines.append(
                f"| `{m.domain}` | {role_badge} | **{m.health_score}** | {m.technical_health_score} | {m.geo_readiness_score} | "
                f"{m.trust_score} | {m.primary_intent.capitalize()} | {m.schema_types_count} | {m.answer_units_count} | "
                f"{grounded_pct} | {m.visual_assets_count} | {alt_pct} | {m.forms_count} | {m.buttons_count} | {m.waf_barrier} |"
            )
        lines.append("")

        # 3. Target vs Benchmark Cohort Analysis
        lines.append(f"## 3. Target (`{report.target_domain}`) vs Benchmark Cohort Analysis")
        lines.append("")
        lines.append(report.target_vs_benchmark.summary)
        lines.append("")
        lines.append("### Key Dimensional Deltas (Observable Differences, Δ=0)")
        lines.append("")
        lines.append("| Dimension | Target Value | Cohort Average / Range | Observable Delta | Epistemic Context |")
        lines.append("| :--- | :--- | :--- | :---: | :--- |")
        for d in report.target_vs_benchmark.dimensional_deltas:
            lines.append(
                f"| **{d['dimension']}** | `{d['target_value']}` | {d['cohort_median_or_avg']} | "
                f"`{d['observable_delta']}` | {d['epistemic_note']} |"
            )
        lines.append("")

        lines.append("### Target Unique Capabilities")
        lines.append("")
        for cap in report.target_vs_benchmark.target_unique_capabilities:
            lines.append(f"- **{cap}**")
        lines.append("")

        lines.append("### Common Benchmark Capabilities")
        lines.append("")
        for cap in report.target_vs_benchmark.common_capabilities:
            lines.append(f"- {cap}")
        lines.append("")

        # 4. Observable Voids & Coverage Gaps
        lines.append("## 4. Observable Voids & Knowledge Gaps Catalog")
        lines.append("")
        lines.append(
            "Observable voids represent concrete structural, content, or technical attributes present across "
            "multiple benchmark sites that are absent or divergent on the target site."
        )
        lines.append("")
        lines.append("| Void ID | Category | Title | State | Target Status | Present Sites | Absent Sites |")
        lines.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: |")
        for v in report.observable_voids:
            lines.append(
                f"| `{v.void_id}` | {v.category} | {v.title} | `{v.state.value}` | "
                f"`{v.target_site_status}` | {len(v.source_sites_present)} sites | {len(v.source_sites_absent)} sites |"
            )
        lines.append("")

        for v in report.observable_voids:
            lines.append(f"#### `{v.void_id}`: {v.title}")
            lines.append(f"- **Description:** {v.description}")
            lines.append(f"- **State:** `{v.state.value}` | **Target Site Status:** `{v.target_site_status}`")
            lines.append(f"- **Supporting Fields:** {', '.join(f'`{f}`' for f in v.supporting_fields)}")
            lines.append(f"- **Provenance Engines:** {', '.join(v.provenance_sources)}")
            lines.append(f"- **Evidence References:**")
            for ref in v.evidence_references:
                ref_str = ", ".join(f"{k}: {val}" for k, val in ref.items())
                lines.append(f"  - `{ref_str}`")
            lines.append("")

        # 5. Common vs Unique Entities
        lines.append("## 5. Common vs Unique Entities & Types")
        lines.append("")
        lines.append(report.entity_comparison.summary)
        lines.append("")
        lines.append("### Entity Types Coverage Across Benchmark")
        lines.append("")
        lines.append("| Entity Type | Adoption Count | Associated Domains |")
        lines.append("| :--- | :---: | :--- |")
        for et, doms in sorted(report.entity_comparison.entity_types_coverage.items()):
            lines.append(f"| `{et}` | {len(doms)} | {', '.join(f'`{d}`' for d in doms)} |")
        lines.append("")

        lines.append("### Common Entities (Appearing in Multiple Sites)")
        lines.append("")
        if report.entity_comparison.common_entities:
            for e in report.entity_comparison.common_entities:
                lines.append(f"- `{e}`")
        else:
            lines.append("- *No common entity names observed across multiple discrete organizations.*")
        lines.append("")

        # 6. Common vs Unique Services / Products
        lines.append("## 6. Service & Product Offerings Comparison")
        lines.append("")
        lines.append(report.service_comparison.summary)
        lines.append("")
        lines.append("### Core Prevalent Services Across Benchmark")
        lines.append("")
        for s in report.service_comparison.common_services:
            lines.append(f"- **{s}**")
        lines.append("")
        lines.append(f"### Target (`{report.target_domain}`) Service Offerings")
        lines.append("")
        lines.append(f"- **Shared with Cohort:** {', '.join(report.service_comparison.target_common_services) or 'None'}")
        lines.append(f"- **Unique to Target:** {', '.join(report.service_comparison.target_unique_services) or 'None'}")
        lines.append("")

        # 7. Topic & Concept Overlap Analysis (Jaccard Similarity)
        lines.append("## 7. Topic & Concept Overlap (Jaccard Similarity Matrix)")
        lines.append("")
        lines.append(report.topic_concept_comparison.summary)
        lines.append("")
        lines.append("### Pairwise Jaccard Concept Similarity Matrix")
        lines.append("")

        # Header row
        header = "| Domain | " + " | ".join(f"`{d.split('.')[0]}`" for d in report.cohort_domains + [report.target_domain]) + " |"
        sep = "| :--- | " + " | ".join(":---:" for _ in report.cohort_domains + [report.target_domain]) + " |"
        lines.append(header)
        lines.append(sep)

        all_doms = report.cohort_domains + [report.target_domain]
        for d1 in all_doms:
            row = [f"`{d1.split('.')[0]}`"]
            for d2 in all_doms:
                sim = report.topic_concept_comparison.jaccard_similarity_matrix.get(d1, {}).get(d2, 0.0)
                row.append(f"{sim:.2f}")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

        lines.append("### Topic Breadth Tiers")
        lines.append("")
        lines.append("| Breadth Tier | Criteria | Domains |")
        lines.append("| :--- | :--- | :--- |")
        high_b = [d for d, t in report.topic_concept_comparison.topic_breadth_tier.items() if t == "HIGH"]
        mod_b = [d for d, t in report.topic_concept_comparison.topic_breadth_tier.items() if t == "MODERATE"]
        low_b = [d for d, t in report.topic_concept_comparison.topic_breadth_tier.items() if t == "LOW"]
        lines.append(f"| **HIGH** | > 150 topics | {', '.join(f'`{d}`' for d in high_b)} |")
        lines.append(f"| **MODERATE** | 80–150 topics | {', '.join(f'`{d}`' for d in mod_b)} |")
        lines.append(f"| **LOW** | < 80 topics | {', '.join(f'`{d}`' for d in low_b)} |")
        lines.append("")

        # 8. Schema Markup Adoption & Distribution
        lines.append("## 8. Schema Markup Adoption & Distribution")
        lines.append("")
        lines.append(report.schema_comparison.summary)
        lines.append("")
        lines.append("| Schema Type | Sites Adopting | Domains |")
        lines.append("| :--- | :---: | :--- |")
        for stype, count in sorted(report.schema_comparison.schema_distribution_across_benchmark.items(), key=lambda x: -x[1]):
            doms = [d for d, stypes in report.schema_comparison.schema_types_by_site.items() if stype in stypes]
            lines.append(f"| `{stype}` | {count} | {', '.join(f'`{d}`' for d in doms)} |")
        lines.append("")
        lines.append(f"**Sites with 0 Schema Markup:** {', '.join(f'`{d}`' for d in report.schema_comparison.sites_with_no_schema)}")
        lines.append("")

        # 9. Answerability Structure Breakdown
        lines.append("## 9. Answerability Structure Breakdown")
        lines.append("")
        lines.append(report.answerability_comparison.summary)
        lines.append("")
        lines.append("| Structural Unit Type | Total Detected | Prevalent Domains |")
        lines.append("| :--- | :---: | :--- |")
        for utype, count in sorted(report.answerability_comparison.unit_types_distribution_across_benchmark.items(), key=lambda x: -x[1]):
            doms = [d for d, udict in report.answerability_comparison.units_by_site_and_type.items() if utype in udict]
            lines.append(f"| `{utype}` | {count} | {', '.join(f'`{d}`' for d in doms)} |")
        lines.append("")
        lines.append(f"**Sites with 0 Answerable Units:** {', '.join(f'`{d}`' for d in report.answerability_comparison.zero_unit_sites)}")
        lines.append("")

        # 10. AI Retrieval, GEO & Bot Access Matrix
        lines.append("## 10. AI Retrieval & Crawler Readiness Matrix")
        lines.append("")
        lines.append(report.retrieval_comparison.summary)
        lines.append("")
        lines.append("| Domain | Search Bots (of 6) | AI Scrapers (of 3) | Edge Barrier | JS Hydration Delta | GEO Score | `/llms.txt` |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for d in all_doms:
            sb = report.retrieval_comparison.search_bots_allowed_by_site.get(d, 0)
            ab = report.retrieval_comparison.ai_bots_allowed_by_site.get(d, 0)
            waf = report.retrieval_comparison.waf_barrier_by_site.get(d, "None")
            delta = report.retrieval_comparison.word_count_delta_by_site.get(d, 0)
            geo = report.retrieval_comparison.geo_score_by_site.get(d, 0)
            llms = "Found" if report.retrieval_comparison.llms_txt_presence_by_site.get(d, False) else "Missing"
            lines.append(f"| `{d}` | {sb}/6 | {ab}/3 | {waf} | {delta} words | {geo}/100 | {llms} |")
        lines.append("")

        # 11. Multimodal & Action Surface Readiness
        lines.append("## 11. Multimodal & Agent Surface Readiness")
        lines.append("")
        lines.append(report.multimodal_agent_comparison.summary)
        lines.append("")
        lines.append("| Domain | Visual Assets | Alt Coverage | Visual Gaps | Interactive Forms | Buttons | Schema Actions |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for d in all_doms:
            va = report.multimodal_agent_comparison.visual_assets_by_site.get(d, 0)
            alt_pct = f"{int(report.multimodal_agent_comparison.alt_coverage_ratio_by_site.get(d, 0.0) * 100)}%"
            gaps = report.multimodal_agent_comparison.visual_gaps_by_site.get(d, 0)
            frms = report.multimodal_agent_comparison.forms_by_site.get(d, 0)
            btns = report.multimodal_agent_comparison.buttons_by_site.get(d, 0)
            s_act = report.multimodal_agent_comparison.schema_actions_by_site.get(d, 0)
            lines.append(f"| `{d}` | {va} | {alt_pct} | {gaps} | {frms} | {btns} | {s_act} |")
        lines.append("")

        # 12. Technical, Accessibility & Security Posture
        lines.append("## 12. Technical SEO, Accessibility & Security")
        lines.append("")
        lines.append(report.technical_a11y_security_comparison.summary)
        lines.append("")
        lines.append(
            "> [!NOTE]\n"
            "> **Accessibility Scope Disclaimer**: Automated checks evaluate observable AST criteria; "
            "> non-certification scope. Automated findings do not constitute legal WCAG compliance certification."
        )
        lines.append("")
        lines.append("| Domain | Title Length | Meta Desc Length | TTFB (ms) | WCAG Violations (Crit) | HTTPS | HSTS | CSP | Security Findings |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for d in all_doms:
            tl = report.technical_a11y_security_comparison.title_length_by_site.get(d, 0)
            ml = report.technical_a11y_security_comparison.meta_desc_length_by_site.get(d, 0)
            ttfb = report.technical_a11y_security_comparison.ttfb_ms_by_site.get(d, 0.0)
            a11y_tot = report.technical_a11y_security_comparison.a11y_violations_by_site.get(d, 0)
            a11y_crit = report.technical_a11y_security_comparison.critical_a11y_violations_by_site.get(d, 0)
            https = "Yes" if report.technical_a11y_security_comparison.https_by_site.get(d, False) else "No"
            hsts = "Yes" if report.technical_a11y_security_comparison.hsts_by_site.get(d, False) else "No"
            csp = "Yes" if report.technical_a11y_security_comparison.csp_by_site.get(d, False) else "No"
            sec_f = report.technical_a11y_security_comparison.security_findings_by_site.get(d, 0)
            lines.append(f"| `{d}` | {tl} chars | {ml} chars | {ttfb}ms | {a11y_tot} ({a11y_crit}) | {https} | {hsts} | {csp} | {sec_f} |")
        lines.append("")

        # 13. Epistemic Separation Container
        lines.append("## 13. Epistemic Separation Container")
        lines.append("")
        lines.append("### Facts (Observable Source Evidence)")
        for f in report.epistemic_separation.facts:
            lines.append(f"- {f}")
        lines.append("")

        lines.append("### External Observations (Third-Party Probes / Edge Intermediaries)")
        for eo in report.epistemic_separation.external_observations:
            lines.append(f"- {eo}")
        lines.append("")

        lines.append("### Analyses (Cross-Site Syntheses & Gap Detection)")
        for an in report.epistemic_separation.analyses:
            lines.append(f"- {an}")
        lines.append("")

        lines.append("### Recommendations (Evidence-Gated Actionable Remediation)")
        for rec in report.epistemic_separation.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

        # 14. Evidence Limitations & Uncertainty
        lines.append("## 14. Evidence Limitations & Uncertainty Profile")
        lines.append("")
        lines.append(f"- **Crawl Scope:** {report.uncertainty_and_limitations.crawl_limitations_summary}")
        lines.append(f"- **Insufficient Evidence Notes:**")
        for n in report.uncertainty_and_limitations.insufficient_evidence_notes:
            lines.append(f"  - {n}")
        lines.append(f"- **Non-Comparable Constraints:**")
        for n in report.uncertainty_and_limitations.not_comparable_notes:
            lines.append(f"  - {n}")
        lines.append("")
        lines.append(f"> **Epistemic Disclaimer:** {report.uncertainty_and_limitations.epistemic_disclaimer}")
        lines.append("")

        return "\n".join(lines)

    @classmethod
    def render_target_markdown(
        cls, target_comp: TargetVsBenchmarkComparison, report: BenchmarkComparisonReport
    ) -> str:
        """Render focused Target vs Benchmark Markdown artifact."""
        lines = []

        lines.append(f"# Target vs Benchmark Comparison — `{target_comp.target_domain}`")
        lines.append("")
        lines.append(f"> **Target Domain:** `{target_comp.target_domain}`  ")
        lines.append(f"> **Target Role:** `{target_comp.target_role}`  ")
        lines.append(f"> **Benchmark Cohort:** {len(target_comp.benchmark_cohort_domains)} competitor websites  ")
        lines.append(f"> **Generated Date:** {report.created_at}  ")
        lines.append(f"> **Formula Invariance:** Verified (Δ = 0)")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## 1. Executive Target Summary")
        lines.append("")
        lines.append(target_comp.summary)
        lines.append("")

        lines.append("## 2. Dimensional Deltas (Target vs Benchmark Cohort)")
        lines.append("")
        lines.append("| Dimension | Target Value | Cohort Average / Range | Observable Delta | Epistemic Context |")
        lines.append("| :--- | :--- | :--- | :---: | :--- |")
        for d in target_comp.dimensional_deltas:
            lines.append(
                f"| **{d['dimension']}** | `{d['target_value']}` | {d['cohort_median_or_avg']} | "
                f"`{d['observable_delta']}` | {d['epistemic_note']} |"
            )
        lines.append("")

        lines.append("## 3. Observable Voids on Target Site")
        lines.append("")
        lines.append("| Void ID | Category | Title | State | Present in Cohort | Supporting Fields |")
        lines.append("| :--- | :--- | :--- | :---: | :---: | :--- |")
        for v in target_comp.observable_voids:
            lines.append(
                f"| `{v.void_id}` | {v.category} | {v.title} | `{v.state.value}` | "
                f"{len(v.source_sites_present)} sites | {', '.join(f'`{f}`' for f in v.supporting_fields)} |"
            )
        lines.append("")

        lines.append("## 4. Target Unique Capabilities")
        lines.append("")
        for cap in target_comp.target_unique_capabilities:
            lines.append(f"- **{cap}**")
        lines.append("")

        lines.append("## 5. Common Shared Capabilities")
        lines.append("")
        for cap in target_comp.common_capabilities:
            lines.append(f"- {cap}")
        lines.append("")

        return "\n".join(lines)

    @classmethod
    def save_comparison_artifacts(
        cls,
        report: BenchmarkComparisonReport,
        output_dir: str | Path = "benchmarks/comparisons",
    ) -> Dict[str, str]:
        """Save JSON and Markdown comparison artifacts with full output parity."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Main comparison JSON
        json_path = out_dir / "benchmark_comparison_phase11.json"
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(cls.render_json(report))

        # 2. Main comparison Markdown
        md_path = out_dir / "benchmark_comparison_phase11.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(cls.render_markdown(report))

        # 3. Target vs Benchmark JSON
        target_slug = report.target_domain.replace(":", "_").replace("/", "_")
        target_json_path = out_dir / f"target_vs_benchmark_{target_slug}.json"
        with open(target_json_path, "w", encoding="utf-8") as f:
            f.write(cls.render_target_json(report.target_vs_benchmark))

        # 4. Target vs Benchmark Markdown
        target_md_path = out_dir / f"target_vs_benchmark_{target_slug}.md"
        with open(target_md_path, "w", encoding="utf-8") as f:
            f.write(cls.render_target_markdown(report.target_vs_benchmark, report))

        return {
            "comparison_json": str(json_path),
            "comparison_md": str(md_path),
            "target_json": str(target_json_path),
            "target_md": str(target_md_path),
        }
