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
        lines.append(f"- **Overall Search & GEO Health Score:** {report.overall_health_score}/100")
        lines.append(f"- **Technical SEO Foundation:** {report.technical_health_score}/100")
        lines.append(f"- **GEO / AI Citability Readiness:** {report.geo_readiness_score}/100")
        lines.append(f"- **Trust Stack (E-E-A-T) Grade:** {report.unified_trust.grade} ({report.trust_score}/100)")
        lines.append(f"- **Performance & CWV Score:** {report.performance_score}/100")
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
        lines.append(f"- **Server Latency (TTFB):** {report.unified_performance.ttfb_ms:.0f}ms")
        lines.append(f"- **Redirect Detected:** {p.is_redirect}")
        lines.append(f"- **Canonical URL:** {p.canonical_url or '⚪ Not specified'}")
        lines.append(f"- **Internal Links Discovered:** {len(p.internal_links)} links")
        lines.append(f"- **External Links Discovered:** {len(p.external_links)} links")
        lines.append("")

        # Performance & CWV
        perf = report.unified_performance
        lines.append("## ⚡ PERFORMANCE & CORE WEB VITALS TELEMETRY")
        src_labels = {
            "pagespeed_crux_field": "🟢 CrUX Real-User Field Data (75th percentile)",
            "pagespeed_lighthouse_lab": "🟡 Google Lighthouse Lab Simulation",
            "local_probe": "⚪ Local Network TTFB Probe (no CrUX data)",
            "local": "⚪ Local Network TTFB Probe (no CrUX data)"
        }
        lines.append(f"- **Telemetry Source:** {src_labels.get(perf.source, perf.source)}")
        lines.append(f"- **Server Latency (TTFB):** {perf.ttfb_ms:.1f}ms")
        if perf.lcp_ms:
            lcp_label = "CrUX Real-User LCP (P75)" if perf.source == "pagespeed_crux_field" else "Lighthouse Lab LCP"
            lines.append(f"- **{lcp_label}:** {perf.lcp_ms:.1f}ms")
        if perf.cls is not None:
            lines.append(f"- **Layout Shift (CLS):** {perf.cls:.3f}")
        if perf.metrics:
            lines.append("\n| Metric | Value | Status | Target Threshold |")
            lines.append("|---|---|---|---|")
            for m in perf.metrics:
                m_icon = "🟢" if m.status == "GOOD" else ("🟡" if m.status == "NEEDS_IMPROVEMENT" else "🔴")
                lines.append(f"| **{m.name}** | {m.value}{m.unit} | {m_icon} {m.status} | ≤{m.threshold_good}{m.unit} |")
        lines.append("")

        # Trust Stack (5-Layer E-E-A-T)
        t = report.unified_trust
        lines.append("## 🛡️ TRUST STACK & E-E-A-T AUDIT (5 LAYERS)")
        lines.append(f"**Overall Trust Grade:** `{t.grade}` ({t.overall_score}/100, Raw {t.raw_score}/25)")
        lines.append(f"*{t.summary}*\n")
        lines.append("| Trust Layer | Score | Signals Detected | Missing Safeguards |")
        lines.append("|---|---|---|---|")
        for layer_name, layer in t.layers.items():
            found_str = "<br>• ".join([""] + layer.signals_found) if layer.signals_found else "None"
            missing_str = "<br>• ".join([""] + layer.signals_missing) if layer.signals_missing else "None"
            lines.append(f"| **{layer.label}** | {layer.score}/5 | {found_str} | {missing_str} |")
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

        # Multi-page site crawl
        if report.site_crawl and report.site_crawl.pages_crawled > 0:
            sc = report.site_crawl
            lines.append("## 🕸️ SITE-WIDE MULTI-PAGE ANALYSIS")
            lines.append(f"- **Pages Crawled:** {sc.pages_crawled} (Depth: {sc.crawl_depth})")
            lines.append(f"- **Pages with Hygiene Issues:** {sc.pages_with_issues}")
            lines.append(f"- **Broken Links (HTTP 4xx/5xx):** {len(sc.broken_links)}")
            lines.append(f"- **Pages Missing H1:** {len(sc.missing_h1_pages)}")
            lines.append(f"- **Thin Content Pages (<300 words):** {len(sc.thin_content_pages)}")
            lines.append(f"- **Duplicate Title Tags Detected:** {len(sc.duplicate_titles)}")
            if sc.redirect_chains:
                multi_hops = [c for c in sc.redirect_chains.values() if c.total_hops > 1]
                loops = [c for c in sc.redirect_chains.values() if c.has_loop]
                lines.append(f"- **Redirect Chains Tracked:** {len(sc.redirect_chains)} ({len(multi_hops)} multi-hop, {len(loops)} loops)")
            if sc.canonical_chains:
                c_chains = [c for c in sc.canonical_chains.values() if c.total_hops > 1]
                c_redirects = [c for c in sc.canonical_chains.values() if c.points_to_redirect]
                lines.append(f"- **Canonical Relationships:** {len(sc.canonical_chains)} ({len(c_chains)} chains, {len(c_redirects)} pointing to redirects)")
            if sc.hygiene_anomalies:
                lines.append(f"- **URL Hygiene Anomalies:** {len(sc.hygiene_anomalies)} representation discrepancies detected")
            if sc.link_graph:
                lg = sc.link_graph
                lines.append("\n### 🔗 Internal Link Graph & Equity Intelligence")
                lines.append(f"- **Total Graph Nodes:** {lg.total_nodes} ({lg.crawled_nodes_count} crawled, {lg.discovered_uncrawled_count} discovered uncrawled)")
                lines.append(f"- **Internal Hyperlink Edges:** {lg.total_internal_edges}")
                lines.append(f"- **External Outbound Links Discovered:** {lg.total_external_links_found}")
                lines.append(f"- **Max Click Depth from Root:** {lg.max_click_depth} clicks")
                if lg.deep_pages:
                    lines.append(f"- **Deep Pages (>3 Clicks from Root):** ⚠️ {len(lg.deep_pages)} pages")
                if lg.potential_orphans:
                    lines.append(f"- **Potential Orphans (0 Internal Inbound Links in Crawl):** ⚠️ {len(lg.potential_orphans)} crawled pages")
                if lg.unreachable_in_observed_graph:
                    lines.append(f"- **Unreachable in Observed Graph:** {len(lg.unreachable_in_observed_graph)} pages (no observed directed path from root)")
                if lg.dead_ends:
                    lines.append(f"- **Dead Ends (0 Outbound Internal Links):** {len(lg.dead_ends)} pages")

                if lg.weakly_connected_components > 1:
                    lines.append(f"- **Graph Connectivity:** ⚠️ {lg.weakly_connected_components} disconnected components detected")
                else:
                    lines.append("- **Graph Connectivity:** 🟢 Fully connected internal graph")

                if lg.top_equity_pages and lg.nodes:
                    lines.append("\n#### Top Pages by Internal Link Equity (Internal PageRank):")
                    lines.append("| URL | Internal Equity | Equity Percentile | Click Depth | Inbound Links | Outbound Links |")
                    lines.append("|---|---|---|---|---|---|")
                    for node_url in lg.top_equity_pages[:5]:
                        node = lg.nodes.get(node_url)
                        if node:
                            d_str = str(node.click_depth) if node.click_depth is not None else "Unreachable"
                            lines.append(f"| `{node.identity_url}` | {node.internal_equity_score:.4f} | {node.equity_percentile}% | {d_str} | {node.inbound_internal_count} | {node.outbound_internal_count} |")
            if sc.sitemap_reconciliation:
                sr = sc.sitemap_reconciliation
                lines.append("\n### 🗺️ XML Sitemap Reconciliation & Cross-Signal Triangulation")
                lines.append(f"- **Sitemaps Traversed:** {sr.total_sitemaps_discovered} ({sr.total_sitemaps_parsed} parsed)")
                lines.append(f"- **Sitemap URLs Tracked:** {sr.total_unique_sitemap_urls} unique URLs ({sr.crawled_sitemap_urls_count} crawled, {sr.uncrawled_sitemap_urls_count} uncrawled in budget)")
                lines.append(f"- **Internal URLs Missing from Sitemap:** {sr.internal_urls_missing_from_sitemap_count} (coverage discrepancy)")
                lines.append(f"- **Cross-Signal Conflicts Identified:** {len(sr.conflicts)}")

                if sr.sitemap_documents:
                    lines.append("\n#### Sitemap Documents:")
                    lines.append("| Document URL | Status | Format | URLs Found | Fetch Time |")
                    lines.append("|---|---|---|---|---|")
                    for doc in sr.sitemap_documents:
                        lines.append(f"| `{doc.url}` | {doc.status.value} | {doc.format.value} | {doc.urls_found_count} | {doc.fetch_time_sec:.3f}s |")

                if sr.conflicts:
                    lines.append("\n#### Cross-Signal Conflict Matrix:")
                    lines.append("| Affected URL | Conflict Type | Diagnostic Priority | Signal A (Sitemap) | Signal B (Empirical) | Evidence Nature | Recommended Remediation |")
                    lines.append("|---|---|---|---|---|---|---|")
                    for c in sr.conflicts:
                        lines.append(f"| `{c.url}` | {c.conflict_type.value} | {c.severity.value} | `{c.signal_a_state}` | `{c.signal_b_state}` | {c.evidence_nature.value} | {c.recommended_reconciliation} |")

                if sr.internal_urls_missing_from_sitemap:
                    lines.append("\n#### Internal URLs Omitted from Sitemap (Coverage Discrepancies):")
                    for m_url in sr.internal_urls_missing_from_sitemap[:10]:
                        lines.append(f"- `{m_url}`")
                    if len(sr.internal_urls_missing_from_sitemap) > 10:
                        lines.append(f"- *... and {len(sr.internal_urls_missing_from_sitemap) - 10} more*")

                if sr.uncrawled_sitemap_urls:
                    lines.append("\n#### Uncrawled Sitemap URLs (Discovery Evidence Only — Status UNKNOWN):")
                    for u_url in sr.uncrawled_sitemap_urls[:10]:
                        lines.append(f"- `{u_url}`")
                    if len(sr.uncrawled_sitemap_urls) > 10:
                        lines.append(f"- *... and {len(sr.uncrawled_sitemap_urls) - 10} more*")

            if sc.site_wide_issues:
                lines.append("\n### 🔴 Site-Wide Structural Findings:")
                for issue in sc.site_wide_issues:
                    lines.append(f"- {issue}")
            lines.append("")

        # Structured Data
        s = report.unified_schema
        lines.append("## 🏗️ STRUCTURED DATA (SCHEMA.ORG)")
        if s.detected_types:
            lines.append(f"- **Detected Schemas:** {', '.join(s.detected_types)}")
        else:
            lines.append("- **Detected Schemas:** 🔴 NONE DETECTED")

        if s.has_organization:
            lines.append("- **Organization Entity:** 🟢 Explicitly Defined")
        else:
            lines.append("- **Organization Entity:** 🔴 Missing")

        if s.sameas_urls:
            lines.append(f"- **Verified sameAs Profiles:** {len(s.sameas_urls)} linked")

        if s.is_injected_via_js:
            lines.append("- **Client-Side Dependency:** ⚠️ Schemas are injected via client-side JavaScript")

        if s.deprecated_types_detected:
            lines.append(f"- **Deprecated Schemas:** ⚠️ {', '.join(s.deprecated_types_detected)}")
        lines.append("")

        # Evidence Provenance Chain
        if report.provenance:
            lines.append("## 🔬 EVIDENCE PROVENANCE & ENGINE ATTRIBUTION")
            lines.append("*(Which engine produced each key finding, and cross-engine consensus status)*\n")
            lines.append("| Finding | Source Element | Primary Engine | Confidence | Cross-Engine Consensus |")
            lines.append("|---|---|---|---|---|")
            for tag in report.provenance:
                confirmed = f"🟢 Confirmed by {', '.join(tag.confirmed_by)}" if tag.confirmed_by else ""
                contradicted = f"🔴 Conflicts with {', '.join(tag.contradicted_by)}" if tag.contradicted_by else ""
                status = confirmed or contradicted or "⚪ Single source"
                lines.append(f"| {tag.finding} | `{tag.source_file}` | `{tag.engine}` | {tag.confidence.upper()} | {status} |")
            lines.append("")

        # AI Bot Matrix
        r = report.unified_robots
        lines.append("## 🤖 AI & SEARCH CRAWLER ACCESS MATRIX (RFC 9309)")
        lines.append("*(Triangulated against RFC 9309 rules across 18+ indexers and foundation scrapers)*\n")

        if r.bot_matrix and r.bot_matrix.entries:
            bm = r.bot_matrix
            lines.append(f"- **Robots.txt Status:** {'🟢 Found & Parsed' if r.found else '⚠️ Missing / Default Allow'}")
            lines.append(f"- **Search Indexers Allowed:** {bm.search_allowed_count}")
            lines.append(f"- **AI Search Agents Allowed:** {bm.ai_search_allowed_count}")
            lines.append(f"- **AI Training Scrapers Blocked:** {bm.ai_training_blocked_count} / {sum(1 for e in bm.entries if e.category == 'AI Model Training')}")
            lines.append("")
            lines.append("| Bot Name | Category | Engine / Company | Status | Match Source | Business Impact |")
            lines.append("|---|---|---|---|---|---|")
            for entry in bm.entries:
                status_icon = "🟢" if entry.status == "ALLOWED" else "⛔"
                source_label = entry.rule_source.replace("_", " ").title()
                if entry.matched_directive:
                    source_label += f" (`{entry.matched_directive}`)"
                lines.append(f"| **{entry.bot_name}** | {entry.category} | {entry.company_or_engine} | {status_icon} {entry.status} | {source_label} | {entry.business_impact} |")
            lines.append("")

            if bm.recommendations:
                lines.append("### 💡 Crawler Access Recommendations:")
                for rec in bm.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")
        else:
            lines.append("| Bot Name | Category | Status | Target Engine / Role |")
            lines.append("|---|---|---|---|")
            for bot, info in r.bot_access.items():
                icon = "🟢" if info.status == "ALLOWED" else ("🔴" if info.status in ("BLOCKED", "DISALLOWED") else "⚪")
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
        domain_clean = report.domain.replace("www.", "").replace(":", "_")
        filename = f"{domain_clean}-{report.timestamp}.md"
        path = os.path.join(output_dir, filename)
        content = MarkdownReporter.render(report)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
