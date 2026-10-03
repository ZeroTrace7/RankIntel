"""
Markdown Audit Report Generator — Formats multi-engine triangulated evidence
into copy-paste ready, executive-grade Markdown audits.
"""
from __future__ import annotations
import os
from rankintel.models.schema import SynthesisReport, SecurityStatus, WcagStatus

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
        if report.site_crawl and (report.site_crawl.pages_crawled > 0 or len(report.site_crawl.crawl_records) > 0):
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

            if getattr(sc, "content_intelligence", None):
                ci = sc.content_intelligence
                lines.append("\n### 📑 Site-Wide Content & Duplicate Intelligence")
                lines.append(f"- **Pages Evaluated:** {ci.total_pages_evaluated}")
                lines.append(f"- **Exact Duplicate Main-Content Clusters:** {ci.exact_duplicate_clusters_count}")
                lines.append(f"- **Near-Duplicate Page Pairs (SimHash + Shingling):** {ci.near_duplicate_pairs_count}")
                lines.append(f"- **Repeated Boilerplate Blocks (Shared across pages):** {ci.repeated_boilerplate_blocks_count}")

                if ci.exact_duplicate_clusters:
                    lines.append("\n#### Exact Duplicate Main-Content Clusters:")
                    lines.append("| Cluster ID | Main-Content SHA-256 | Word Count | Duplicate URLs |")
                    lines.append("|---|---|---|---|")
                    for cluster in ci.exact_duplicate_clusters:
                        urls_str = "<br>".join([f"`{u}`" for u in cluster.urls[:5]])
                        if len(cluster.urls) > 5:
                            urls_str += f"<br>*...and {len(cluster.urls) - 5} more*"
                        lines.append(f"| **{cluster.cluster_id}** | `{cluster.content_hash[:16]}...` | {cluster.word_count} | {urls_str} |")

                if ci.near_duplicate_pairs:
                    lines.append("\n#### Near-Duplicate Page Pairs:")
                    lines.append("| URL A | URL B | Shingle Similarity | SimHash Distance | Method |")
                    lines.append("|---|---|---|---|---|")
                    for pair in ci.near_duplicate_pairs[:10]:
                        lines.append(f"| `{pair.url_a}` | `{pair.url_b}` | {pair.similarity_percentage}% | {pair.hamming_distance} bits | `{pair.method}` |")

                if ci.repeated_boilerplate_blocks:
                    lines.append("\n#### Repeated Boilerplate Text Blocks:")
                    lines.append("| Text Snippet | Word Count | Page Count | Sample Pages |")
                    lines.append("|---|---|---|---|")
                    for b in ci.repeated_boilerplate_blocks[:5]:
                        sample_pages = ", ".join([f"`{p}`" for p in b.pages[:3]])
                        lines.append(f"| {b.text_snippet} | {b.word_count} words | {b.page_count} pages | {sample_pages} |")

            if getattr(sc, "entity_intelligence", None):
                ei = sc.entity_intelligence
                lines.append("\n### 🏛️ Site-Wide Entity Intelligence & Consistency")
                lines.append(f"- **Total Pages Evaluated:** {ei.total_pages_evaluated}")
                lines.append(f"- **Total Entities Detected:** {ei.total_entities_detected} ({ei.unique_entities_count} unique names)")
                lines.append(f"- **Cross-Page Attribute Inconsistencies:** {ei.inconsistencies_count}")

                if ei.primary_organization_candidate and ei.primary_organization_candidate.candidate_name:
                    poc = ei.primary_organization_candidate
                    lines.append(f"- **Primary Organization Candidate:** **{poc.candidate_name}** *(identified based on observable evidence; not definitive identity)*")
                    if poc.selection_reasons:
                        lines.append(f"  • *Selection Reasons:* {'; '.join(poc.selection_reasons)}")
                    if poc.evidence_sources:
                        lines.append(f"  • *Evidence Sources:* {', '.join(poc.evidence_sources)}")

                if ei.inconsistencies:
                    lines.append("\n#### Observable Cross-Page Attribute Inconsistencies:")
                    lines.append("| Entity Name | Attribute | Conflicting Values Observed | URLs Exhibiting Values |")
                    lines.append("|---|---|---|---|")
                    for inc in ei.inconsistencies:
                        vals_str = "<br>".join([f"`{v}` ({len(u)} pages)" for v, u in inc.conflicting_values.items()])
                        sample_urls = "<br>".join([f"`{u}`" for u in list({url for u_list in inc.conflicting_values.values() for url in u_list})[:3]])
                        lines.append(f"| **{inc.entity_name}** | `{inc.attribute}` | {vals_str} | {sample_urls} |")

            if getattr(sc, "internal_link_intelligence", None):
                ili = sc.internal_link_intelligence
                lines.append("\n### 🔗 Site-Wide Internal-Link Intelligence & Structure")
                lines.append(f"- **Total Pages Evaluated:** {ili.total_pages_evaluated}")
                lines.append(f"- **Internal Hyperlinks Discovered:** {ili.total_internal_links_discovered} ({ili.total_unique_internal_edges} unique directed edges)")
                lines.append(f"- **Pages with 0 Discovered Inlinks (Analyzed Crawl):** {len(ili.pages_with_zero_inlinks)}")
                lines.append(f"- **Pages with Limited Connectivity (1 Discovered Inlink):** {len(ili.pages_with_weak_inlinks)}")
                lines.append(f"- **Terminal / Dead-End Pages (0 Outgoing Internal Links):** {len(ili.dead_end_pages)}")
                lines.append(f"- **Pages Observed at Depth > 3:** {len(ili.deep_pages)}")
                lines.append(f"- **Broken Internal Link Targets:** {ili.broken_internal_links_count}")
                lines.append(f"- **Top-5 Concentration:** {ili.link_concentration.top_5_concentration_pct}% of observed internal links point to top 5 pages")

                if ili.broken_internal_links:
                    lines.append("\n#### Broken Internal Link Targets (Observed in Crawl Evidence):")
                    lines.append("| Source Page | Target URL | Anchor Text | Crawl Observation |")
                    lines.append("|---|---|---|---|")
                    for b in ili.broken_internal_links[:10]:
                        lines.append(f"| `{b.source_url}` | `{b.target_url}` | '{b.anchor_text or '(empty)'}' | `{b.failure_reason or 'HTTP error'}` |")

                if ili.anchor_intelligence and ili.anchor_intelligence.top_anchor_texts:
                    lines.append("\n#### Top Internal Anchor Texts:")
                    lines.append("| Anchor Phrase | Frequency |")
                    lines.append("|---|---|")
                    for text, count in ili.anchor_intelligence.top_anchor_texts[:8]:
                        lines.append(f"| '{text}' | {count} |")

                if ili.anchor_intelligence and ili.anchor_intelligence.conflicting_anchors:
                    lines.append("\n#### Ambiguous Anchor Texts (Same Anchor -> Distinct Destinations):")
                    lines.append("| Anchor Phrase | Occurrences | Distinct Destinations | Sample Targets |")
                    lines.append("|---|---|---|---|")
                    for amb in ili.anchor_intelligence.conflicting_anchors[:5]:
                        sample_targets = "<br>".join([f"`{t}`" for t in amb.target_urls[:3]])
                        lines.append(f"| '{amb.anchor_text}' | {amb.total_occurrences} | {len(amb.target_urls)} destinations | {sample_targets} |")

                if ili.anchor_intelligence and ili.anchor_intelligence.generic_anchor_occurrences:
                    lines.append("\n#### Generic Anchor Text Occurrences:")
                    lines.append("| Generic Phrase | Frequency | Sample Target |")
                    lines.append("|---|---|---|")
                    for g in ili.anchor_intelligence.generic_anchor_occurrences[:5]:
                        lines.append(f"| '{g.anchor_text}' | {g.count} | `{g.target_url}` |")

                if ili.link_concentration and ili.link_concentration.top_linked_pages:
                    lines.append("\n#### Top Linked Internal Pages (Incoming Link Concentration):")
                    lines.append("| Target URL | Unique Inlinks |")
                    lines.append("|---|---|")
                    for url_node, in_count in ili.link_concentration.top_linked_pages[:5]:
                        lines.append(f"| `{url_node}` | {in_count} |")

            if getattr(sc, "search_signal_intelligence", None):
                ssi = sc.search_signal_intelligence
                lines.append("\n### 📡 Site-Wide Recurring Search Concepts & Terminology (Layer A)")
                lines.append("> *Scope Note: Strictly observed on-site website terminology across crawled pages. External search query volume and rankings are not available in Layer A.*")
                lines.append(f"- **Total Pages Evaluated:** {ssi.total_pages_evaluated}")
                lines.append(f"- **Unique Evidenced Terms Discovered:** {ssi.total_unique_concepts}")
                lines.append(f"- **Recurring Cross-Page Concepts:** {ssi.recurring_concepts_count}")

                if ssi.recurring_concepts:
                    lines.append("\n#### Top Recurring On-Site Concepts:")
                    lines.append("| Concept / Term | Pages Count | Total Mentions | Concept Nature | Sample Observed Locations |")
                    lines.append("|---|---|---|---|---|")
                    for rc in ssi.recurring_concepts[:12]:
                        kind = f"Entity ({rc.entity_type})" if rc.is_entity else "Content/Heading"
                        locs = ", ".join(rc.observed_locations[:3])
                        lines.append(f"| **{rc.concept}** | {rc.pages_count} pages | {rc.total_occurrences} | `{kind}` | {locs} |")

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

        # Security & Web Best Practices
        sec = report.unified_security
        if sec and (sec.headers_evaluated or sec.findings or sec.tls_details or sec.overall_status not in (SecurityStatus.UNKNOWN, SecurityStatus.UNAVAILABLE)):
            lines.append("## 🛡️ SECURITY & WEB BEST PRACTICES")
            lines.append(f"- **Overall Status:** {sec.overall_status.name}")
            lines.append(f"- **HTTPS Enforced:** {'🟢 YES' if sec.is_https else '🔴 NO (Insecure HTTP)'}")
            if sec.tls_details:
                tls = sec.tls_details
                if tls.is_valid:
                    exp_info = f"({tls.days_until_expiration} days remaining)" if tls.days_until_expiration is not None else ""
                    lines.append(f"- **TLS Certificate:** 🟢 Valid {tls.protocol_version or ''} {exp_info}")
                else:
                    lines.append(f"- **TLS Certificate:** 🔴 Invalid ({tls.error_message or 'Verification failed'})")

            hsts_status = "🟢 Enabled" if sec.hsts_present else "🔴 Missing"
            if sec.hsts_preload:
                hsts_status += " (Preload ready)"
            lines.append(f"- **HSTS (Strict-Transport-Security):** {hsts_status}")
            lines.append(f"- **Content-Security-Policy (CSP):** {'🟢 Configured' if sec.csp_present else '🔴 Missing'}")
            lines.append(f"- **Clickjacking Defense (X-Frame-Options):** {sec.x_frame_options or '🔴 Missing'}")
            lines.append(f"- **MIME Protection (X-Content-Type-Options):** {sec.x_content_type_options or '🔴 Missing'}")
            lines.append(f"- **Referrer-Policy:** {sec.referrer_policy or '⚠️ Missing'}")

            if sec.mixed_content_resources:
                lines.append(f"- **Mixed Content Insecure Assets:** ⚠️ {len(sec.mixed_content_resources)} resources loaded over HTTP")

            if sec.server_leakage:
                lines.append(f"- **Server Information Leakage:** ⚠️ {', '.join(sec.server_leakage)}")

            if sec.findings:
                lines.append("\n### 🚨 Security & Best Practice Findings:")
                lines.append("| Severity | Category | Finding | Recommendation |")
                lines.append("|---|---|---|---|")
                for f in sec.findings:
                    sev_icon = "🔴" if f.severity in ("CRITICAL", "HIGH") else ("🟡" if f.severity == "MEDIUM" else "ℹ️")
                    cat_label = f.category.value.replace("_", " ").title()
                    lines.append(f"| {sev_icon} {f.severity.value} | {cat_label} | {f.title} | {f.recommendation} |")
                lines.append("")

        # Image SEO & Layout Stability
        img = report.unified_image_seo
        if img and img.total_images > 0:
            lines.append("## 🖼️ IMAGE SEO & VISUAL ASSET INTELLIGENCE")
            lines.append(f"- **Total Images Detected:** {img.total_images}")
            lines.append(f"- **Alt Attribute Coverage:** {img.images_with_alt}/{img.total_images} images declared alt text ({img.missing_alt_count} missing, {img.generic_alt_count} generic, {img.decorative_alt_count} decorative)")
            dim_declared = max(0, img.total_images - img.missing_dimensions_count)
            lines.append(f"- **Layout Stability (Explicit Dimensions):** {dim_declared}/{img.total_images} images declared width/height ({img.missing_dimensions_count} layout shift risks; static heuristic, not measured CLS)")
            lines.append(f"- **Modern Format Delivery (WebP/AVIF/SVG):** {img.modern_format_count}/{img.total_images} images ({img.legacy_format_count} legacy formats)")
            lines.append(f"- **Lazy Loading Below Fold:** {img.lazy_loaded_count} images ({img.early_lazy_lcp_risks_count} early lazy loading LCP risks)")

            if img.head_audit:
                head = img.head_audit
                lines.append("\n### 📐 HTML Head & Document Architecture:")
                lines.append(f"- **Viewport Tag:** {'🟢 Configured' if head.viewport_present else '🔴 Missing'} (`{head.viewport_configuration or 'None'}`)")
                lines.append(f"- **Document Language:** {'🟢 Declared' if head.lang_present else '🔴 Missing'} (`{head.lang_code or 'None'}`)")
                lines.append(f"- **Character Set:** {'🟢 Declared' if head.charset_present else '🔴 Missing'} (`{head.charset_declared or 'None'}`)")
                lines.append(f"- **Heading Hierarchy:** {'🟢 Valid' if head.heading_hierarchy_valid else '⚠️ Skips Detected'}")
                if head.heading_skips:
                    for skip in head.heading_skips:
                        lines.append(f"  • {skip}")
                if head.insecure_resource_urls:
                    lines.append(f"- **Insecure HTTP Assets:** ⚠️ {len(head.insecure_resource_urls)} assets loaded over plain HTTP")
            lines.append("")

        # Accessibility (WCAG 2.1/2.2 AA Automated Checks)
        a11y = report.unified_accessibility
        if a11y and (a11y.violations or a11y.total_violations > 0 or a11y.rules_evaluated_count > 0 or a11y.notes or "accessibility_engine" in report.engines_executed or a11y.wcag_aa_status not in (WcagStatus.UNKNOWN, WcagStatus.UNAVAILABLE)):
            lines.append("## ♿ ACCESSIBILITY (WCAG 2.1/2.2 AA Automated Checks)")
            lines.append(f"- **Automated WCAG Status:** {a11y.wcag_aa_status.value}")
            source_desc = "Browser-Rendered DOM (axe-core)" if a11y.browser_evaluated else "Static HTML AST Auditor"
            lines.append(f"- **Evaluation Tier:** `{a11y.engine_source}` ({source_desc})")
            lines.append(f"- **Total Violations Detected:** {a11y.total_violations} (Critical: {a11y.critical_count}, Serious: {a11y.serious_count}, Moderate: {a11y.moderate_count}, Minor: {a11y.minor_count})")
            if a11y.rules_evaluated_count > 0:
                lines.append(f"- **Automated Rules Checked:** {a11y.rules_evaluated_count} ({a11y.rules_passed_count} passed)")
            if a11y.notes:
                for note in a11y.notes:
                    lines.append(f"- *Note:* {note}")
            if a11y.violations:
                lines.append("\n### 🚨 Accessibility Violations:")
                lines.append("| Severity | Rule ID | WCAG SC | Level | Description | Failure Summary |")
                lines.append("|---|---|---|---|---|---|")
                for v in a11y.violations:
                    sev_val = v.severity.value if hasattr(v.severity, "value") else str(v.severity)
                    level_val = v.level.value if hasattr(v.level, "value") else str(v.level)
                    sev_icon = "🔴" if sev_val in ("CRITICAL", "SERIOUS") else ("🟡" if sev_val == "MODERATE" else "ℹ️")
                    lines.append(f"| {sev_icon} {sev_val} | `{v.rule_id}` | {v.wcag_sc or 'N/A'} | {level_val} | {v.description} | {v.failure_summary} |")
                lines.append("")
            lines.append("*Disclaimer: Automated checks evaluate a subset of WCAG 2.1/2.2 AA criteria and do not constitute complete manual accessibility certification.*\n")

        # Content Intelligence & Structure (Phase 8.1)
        cnt = report.unified_content
        if cnt and (cnt.main_content_word_count > 0 or (cnt.extraction_method and cnt.extraction_method.value != "UNAVAILABLE")):
            lines.append("## 📑 CONTENT INTELLIGENCE & STRUCTURE")
            lines.append(f"- **Main Editorial Content:** {cnt.main_content_word_count} words ({cnt.main_content_char_count} chars, {cnt.paragraph_count} paragraphs)")
            lines.append(f"- **Extraction Method:** `{cnt.extraction_method.value}`")
            lines.append(f"- **Total Body Words / Content Ratio:** {cnt.total_body_word_count} body words ({int(cnt.content_to_boilerplate_ratio * 100)}% editorial)")
            lines.append(f"- **Content Telemetry Bucket:** `{cnt.thin_content.word_count_tier.value}` (descriptive measurement range, not a quality grade)")
            if cnt.thin_content.placeholder_text_detected:
                lines.append(f"- **Placeholder Copy Detected:** ⚠️ {', '.join(cnt.thin_content.placeholder_snippets)}")
            lines.append(f"- **Exact Main-Content SHA-256:** `{cnt.exact_content_hash}`")
            lines.append(f"- **Full HTML SHA-256:** `{cnt.html_hash}`")
            lines.append(f"- **Deterministic SimHash (64-bit):** `{cnt.simhash}`")

            t_rel = cnt.title_h1_relationship
            if t_rel and t_rel.alignment_status.value != "UNAVAILABLE":
                lines.append("\n### 🎯 Title ↔ H1 ↔ Content Relationship:")
                lines.append(f"- **Title Tag:** {t_rel.title_text or '⚪ Missing'}")
                lines.append(f"- **Primary H1:** {t_rel.h1_text or '⚪ Missing'}")
                lines.append(f"- **Alignment Observation:** `{t_rel.alignment_status.value}` (Token overlap: {t_rel.token_overlap_ratio * 100:.1f}%)")
                lines.append(f"- **Title/H1 Key Terms in Lead 200 Words:** {t_rel.lead_content_keyword_ratio * 100:.1f}%")

            h = cnt.heading_structure
            if h and h.total_headings > 0:
                lines.append("\n### 📐 Heading Hierarchy & Content Outline:")
                lines.append(f"- **Heading Counts:** H1: {h.h1_count} | H2: {h.h2_count} | H3: {h.h3_count} | H4: {h.h4_count} | H5: {h.h5_count} | H6: {h.h6_count} (Total: {h.total_headings})")
                lines.append(f"- **Hierarchy Status:** {'🟢 Valid (no skips)' if h.heading_hierarchy_valid else '⚠️ Skips detected'}")
                if h.heading_skips:
                    for skip in h.heading_skips:
                        lines.append(f"  • {skip}")
                lines.append(f"- **Average Words per Heading Section:** {h.average_words_per_section:.1f} words ({h.empty_sections_count} empty sections)")
            lines.append("")

        # Entity Intelligence & Reconciliation (Phase 8.2)
        ent = getattr(report, "unified_entity", None)
        if ent and (ent.detected_entities or ent.relationships or ent.structured_vs_visible):
            lines.append("## 🏛️ ENTITY INTELLIGENCE & RECONCILIATION")
            lines.append(f"- **Total Entity Signals Detected:** {ent.total_entities_detected}")
            if ent.facts:
                for fact in ent.facts:
                    lines.append(f"- *Observation:* {fact}")

            if ent.detected_entities:
                lines.append("\n### 🏷️ Detected Observable Entities & Signals:")
                lines.append("| Entity Type | Name / Signal | Signal Source | Evidence Type | Key Attributes |")
                lines.append("|---|---|---|---|---|")
                for e in ent.detected_entities[:15]:
                    attrs = []
                    if e.telephone:
                        attrs.append(f"Tel: {e.telephone}")
                    if e.address:
                        short_addr = e.address[:40] + ("..." if len(e.address) > 40 else "")
                        attrs.append(f"Addr: {short_addr}")
                    if e.email:
                        attrs.append(f"Email: {e.email}")
                    if e.same_as:
                        attrs.append(f"{len(e.same_as)} sameAs")
                    if e.structured_data_type:
                        attrs.append(f"Schema: `{e.structured_data_type}`")
                    attr_str = ", ".join(attrs) if attrs else "—"
                    lines.append(f"| `{e.entity_type.value}` | **{e.name}** | `{e.source.value}` | `{e.signal_type.value}` | {attr_str} |")

            if ent.relationships:
                lines.append("\n### 🔗 Observable Entity Relationships:")
                lines.append("| Subject | Relationship | Object | Context / Source |")
                lines.append("|---|---|---|---|")
                for r in ent.relationships[:10]:
                    lines.append(f"| **{r.subject_name}** (`{r.subject_type.value}`) | `{r.relation.value}` | **{r.object_name}** (`{r.object_type}`) | {r.evidence_text or r.source} |")

            if ent.structured_vs_visible:
                lines.append("\n### ⚖️ Structured Data ↔ Visible Content Alignment:")
                lines.append("| Attribute | Structured Value | Visible Signal | Alignment Status | Notes |")
                lines.append("|---|---|---|---|---|")
                for comp in ent.structured_vs_visible:
                    status_icon = "🟢" if comp.alignment_status.value in ("EXACT_MATCH", "NORMALIZED_MATCH") else ("🟡" if comp.alignment_status.value == "PARTIAL_MATCH" else "ℹ️")
                    lines.append(f"| `{comp.attribute_name}` | {comp.structured_value or '—'} | {comp.visible_value or '—'} | {status_icon} `{comp.alignment_status.value}` | {comp.notes} |")
            lines.append("")

        # Internal Link & Anchor Intelligence (Phase 8.3)
        lnk = getattr(report, "unified_internal_link", None)
        if lnk and (lnk.total_links_found > 0 or lnk.facts):
            lines.append("## 🔗 INTERNAL LINK & ANCHOR INTELLIGENCE")
            lines.append(f"- **Total Links Observed on Page:** {lnk.total_links_found}")
            lines.append(f"- **Internal Hyperlinks:** {lnk.internal_links_count} ({lnk.unique_internal_outlinks_count} unique destinations)")
            lines.append(f"- **External Outbound Links:** {lnk.external_links_count} ({lnk.unique_external_outlinks_count} unique external destinations)")
            lines.append(f"- **Special / Fragment Links:** {lnk.special_links_count}")
            lines.append(f"- **Nofollow Links Declared:** {lnk.nofollow_links_count}")
            lines.append(f"- **Empty / Unlabeled Internal Anchors:** {lnk.empty_anchor_count}")
            lines.append(f"- **Generic Anchor Occurrences:** {lnk.generic_anchor_count}")
            if lnk.facts:
                for f in lnk.facts:
                    lines.append(f"- *Observation:* {f}")
            if lnk.observations:
                for obs in lnk.observations:
                    lines.append(f"- *Opportunity:* {obs}")
            if lnk.generic_anchors:
                lines.append("\n### 🏷️ Generic Anchor Text Observed:")
                lines.append("| Anchor Phrase | Target Destination | Frequency |")
                lines.append("|---|---|---|")
                for g in lnk.generic_anchors[:5]:
                    lines.append(f"| `{g.anchor_text}` | `{g.target_url}` | {g.count} |")
            lines.append("")

        # Search Signal Intelligence (Phase 9.1 - Layer A)
        sig = getattr(report, "unified_search_signal", None)
        if sig and (sig.total_signals_detected > 0 or sig.facts):
            lines.append("## 📡 SEARCH SIGNAL INTELLIGENCE (Layer A: On-Site Evidenced Signals)")
            lines.append("> *Evidence Boundary: Contains strictly observed on-site terminology, structural concepts, and entity signals. External Google SERP positions, search volume, CTR, and search intent are excluded (Layer A boundary).*")
            lines.append(f"- **Total Evidenced Signal Terms:** {sig.total_signals_detected}")
            lines.append(f"- **Unique Evidenced Concepts:** {sig.unique_terms_count}")
            if sig.title_terms:
                lines.append(f"- **Title Evidenced Terms:** {', '.join(sig.title_terms[:8])}")
            if sig.heading_terms:
                lines.append(f"- **Heading Terms (H1–H3):** {', '.join(sig.heading_terms[:8])}")
            if sig.meta_description_terms:
                lines.append(f"- **Meta Description Terms:** {', '.join(sig.meta_description_terms[:8])}")
            if sig.url_path_terms:
                lines.append(f"- **URL Path Terms:** {', '.join(sig.url_path_terms[:8])}")

            if sig.signals:
                lines.append("\n### 🔍 Prominent Evidenced Terms & Structural Placements:")
                lines.append("| Term / Concept | Evidence Level | Structural Locations | Mentions | Prominence |")
                lines.append("|---|---|---|---|---|")
                for s_item in sig.signals[:15]:
                    loc_names = ", ".join([loc.value for loc in s_item.locations[:3]])
                    prom_names = ", ".join(s_item.prominence_locations) if s_item.prominence_locations else "body/path"
                    lines.append(f"| **{s_item.term}** | `{s_item.confidence.value}` | {loc_names} | {s_item.total_occurrences} | `{prom_names}` |")

            if sig.facts or sig.analyses:
                lines.append("\n### 📑 Observations & Structural Analyses:")
                for fact in sig.facts:
                    lines.append(f"- **FACT:** {fact}")
                for analysis in sig.analyses:
                    lines.append(f"- **ANALYSIS:** {analysis}")
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
