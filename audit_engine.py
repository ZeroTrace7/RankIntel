"""
RankIntel — Unified Multi-Engine Audit & Intelligence Entrypoint.
Backward compatible runner delegating to the RankIntel v2 Multi-Engine Platform.
"""
import sys
import os
from typing import Optional, List
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.intelligence.comparer import IntelligenceComparer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.gap_reporter import GapReporter
from rankintel.reporters.json_reporter import JsonReporter
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(highlight=False)

def run_audit(
    url: str,
    output_dir: str = "audits",
    output_format: str = "markdown",
    deep_crawl: bool = False,
    max_pages: int = 25,
    external_ai: bool = False,
    external_providers: Optional[str] = None,
):
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    providers_list = [p.strip() for p in external_providers.split(",")] if external_providers else None

    if output_format == "markdown":
        console.print(Panel.fit(
            f"[bold cyan]RankIntel Intelligence Engine v3.0[/bold cyan]\n"
            f"[dim]Triangulating:[/dim] [yellow]advertools (SEO)[/yellow] + [green]crawl4ai (Browser)[/green] + [magenta]RankIntel (GEO/AEO)[/magenta] + [blue]CWV/CrUX[/blue] + [cyan]OpenSEO MCP[/cyan]\n"
            f"[bold white]Target:[/bold white] [underline]{url}[/underline]",
            border_style="cyan"
        ))

    # Phase 1: Collect Evidence
    with console.status("[bold green]Executing multi-engine audit pass...[/bold green]", spinner="dots"):
        collector = EvidenceCollector(
            enable_external_visibility=external_ai,
            external_providers=providers_list,
        )
        engine_results = collector.collect(
            url,
            enable_external_visibility=external_ai,
            external_providers=providers_list,
        )

    # Phase 2: Synthesize Intelligence
    with console.status("[bold cyan]Reconciling evidence, provenance, and detecting cross-engine conflicts...[/bold cyan]", spinner="dots"):
        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize(url, engine_results)

    # Optional: Deep Multi-Page Crawling
    if deep_crawl:
        with console.status(f"[bold blue]Deep crawling up to {max_pages} pages for site hygiene...[/bold blue]", spinner="dots"):
            site_crawl = collector.seo_engine.crawl_site(url, max_pages=max_pages)
            report.site_crawl = site_crawl

    # Phase 3: Persist Audit Report
    if output_format == "json":
        report_file = JsonReporter.save_audit(report, output_dir=output_dir)
        console.print_json(JsonReporter.render_audit(report))
        console.print(f"\n[bold green]Report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")
        return report_file

    report_file = MarkdownReporter.save(report, output_dir=output_dir)

    console.print("\n[bold green][SUCCESS] Multi-Engine Triangulation Completed Successfully![/bold green]\n")

    table = Table(title="Executive Audit Scorecard", show_header=True, header_style="bold magenta")
    table.add_column("Telemetry Category", style="cyan")
    table.add_column("Score / Status", justify="center")
    table.add_column("Engine Agreement", style="dim")

    table.add_row(
        "Overall Search Health",
        f"[bold green]{report.overall_health_score}/100[/bold green]" if report.overall_health_score >= 70 else f"[bold yellow]{report.overall_health_score}/100[/bold yellow]",
        f"Consensus across {len(report.engines_executed)} engines"
    )
    table.add_row(
        "Technical SEO Foundation",
        f"{report.technical_health_score}/100",
        "advertools + browser DOM"
    )
    table.add_row(
        "GEO / AI Citability Score",
        f"{report.geo_readiness_score}/100",
        "Princeton GEO metrics"
    )
    table.add_row(
        "Trust Stack (E-E-A-T) Grade",
        f"[bold cyan]{report.unified_trust.grade}[/bold cyan] ({report.trust_score}/100)",
        "5-layer trust aggregation"
    )
    table.add_row(
        "Server Latency (TTFB)",
        f"{report.unified_performance.ttfb_ms:.0f}ms",
        report.unified_performance.source
    )
    table.add_row(
        "AI Search Bot Status",
        f"{len([b for b in report.unified_robots.bot_access.values() if b.status == 'ALLOWED' and b.category == 'search'])} Search Bots Allowed",
        "RFC robots parser"
    )
    table.add_row(
        "Machine-Readable /llms.txt",
        "Present" if report.unified_geo.llms_txt_found else "Missing",
        "llmstxt.org v2 check"
    )
    if getattr(report, "unified_retrieval_readiness", None):
        rr = report.unified_retrieval_readiness
        snip_str = "snippets allowed" if not rr.snippet_controls.has_nosnippet else "nosnippet active"
        table.add_row(
            "AI Retrieval Readiness",
            f"{rr.search_index_allowed_count} search indexers permitted ({snip_str})",
            "robots + headers + directives (Phase 10.1)"
        )
    elif report.site_crawl and getattr(report.site_crawl, "retrieval_readiness_intelligence", None):
        rri = report.site_crawl.retrieval_readiness_intelligence
        table.add_row(
            "Site AI Retrieval Scope",
            f"{rri.total_pages_evaluated} pages ({len(rri.pages_with_waf_challenge)} blocked, {len(rri.pages_with_nosnippet)} nosnippet)",
            "site-wide retrieval triangulation"
        )

    if getattr(report, "unified_answerability", None):
        ans = report.unified_answerability
        table.add_row(
            "AI Answerability & Extraction",
            f"{ans.total_units_detected} unit(s) ({ans.explained_topics_count} topic(s) explained)",
            "structured units + clarity + topic linkage (Phase 10.2)"
        )
    elif report.site_crawl and getattr(report.site_crawl, "answerability_intelligence", None):
        ai = report.site_crawl.answerability_intelligence
        table.add_row(
            "Site AI Answerability Scope",
            f"{ai.total_site_units_detected} units across {ai.total_pages_evaluated} pages ({len(ai.pages_with_faq)} FAQ pages)",
            "site-wide information answerability"
        )

    if getattr(report, "unified_claim_grounding", None):
        cg = report.unified_claim_grounding
        table.add_row(
            "Claim Grounding & Consistency",
            f"{cg.supported_claims_count}/{cg.total_claims_detected} claims supported ({cg.agreement_count} schema agreements)",
            "on-site grounding + multi-surface alignment (Phase 10.3)"
        )
    elif report.site_crawl and getattr(report.site_crawl, "claim_grounding_intelligence", None):
        cgi = report.site_crawl.claim_grounding_intelligence
        table.add_row(
            "Site Claim Grounding Scope",
            f"{cgi.total_site_claims} claims ({cgi.total_supported_claims} supported) across {cgi.total_pages_evaluated} pages",
            "site-wide claim corroboration"
        )

    if getattr(report, "unified_multimodal_agent", None):
        mma = report.unified_multimodal_agent
        table.add_row(
            "Multimodal & Agent Readiness",
            f"{mma.multimodal.total_visual_assets} asset(s) ({mma.multimodal.alt_represented_count} alt-repr), {mma.agent_readiness.total_forms_detected} form(s), {len(mma.access_paths)} path(s)",
            "visual representations + forms/controls + access paths (Phase 10.4)"
        )
    elif report.site_crawl and getattr(report.site_crawl, "multimodal_agent_intelligence", None):
        mmi = report.site_crawl.multimodal_agent_intelligence
        table.add_row(
            "Site Multimodal & Agent Scope",
            f"{mmi.total_site_visual_assets} visual assets, {mmi.total_site_forms} forms across {mmi.total_pages_evaluated} pages ({mmi.total_visual_only_gaps} visual gaps)",
            "site-wide multimodal & agent interaction surfaces"
        )

    if getattr(report, "unified_external_visibility", None) and report.unified_external_visibility.status.value != "DISABLED":
        evi = report.unified_external_visibility
        evi_color = "green" if evi.target_domain_cited_count > 0 else ("yellow" if evi.successful_observations_count > 0 else "red")
        table.add_row(
            "External AI Visibility",
            f"[{evi_color}]{evi.successful_observations_count}/{evi.queries_executed_count} obs[/{evi_color}] ({evi.target_domain_cited_count} cited, {evi.target_domain_mention_count} mentioned)",
            "controlled provider observations (Phase 10.5)"
        )
    elif report.site_crawl and getattr(report.site_crawl, "external_visibility_intelligence", None) and report.site_crawl.external_visibility_intelligence.status != "disabled":
        sevi = report.site_crawl.external_visibility_intelligence
        table.add_row(
            "Site External AI Visibility",
            f"{sevi.total_observations_completed}/{sevi.total_queries_planned} queries ({sevi.total_target_citations} cited, {sevi.total_target_domain_mentions} mentions)",
            "site-wide controlled provider observations"
        )

    console.print(table)

    if report.conflicts_detected:
        console.print("\n[bold yellow]Triangulation Insights & Engine Conflicts Detected:[/bold yellow]")
        for c in report.conflicts_detected:
            console.print(f"  • [bold red][{c.severity}][/bold red] [bold]{c.feature}:[/bold] {c.description}")
            console.print(f"    [dim]Interpretation:[/dim] {c.interpretation}\n")

    if hasattr(report, 'remediation_records') and report.remediation_records:
        console.print("\n[bold cyan]Remediation Intelligence:[/bold cyan]")
        for rem in report.remediation_records:
            color = "green" if rem.classification.value == "AUTO_SAFE" else "yellow"
            console.print(f"  \U0001F6E0\FE0F [{color}][{rem.classification.value}][/{color}] [bold]{rem.problem}[/bold]")
            console.print(f"    [dim]Action:[/dim] {rem.recommended_action}")

    console.print(f"[bold green]Report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")
    return report_file

def run_compare(url_a: str, url_b: str, output_dir: str = "reports", output_format: str = "markdown"):
    if not url_a.startswith("http://") and not url_a.startswith("https://"):
        url_a = "https://" + url_a
    if not url_b.startswith("http://") and not url_b.startswith("https://"):
        url_b = "https://" + url_b

    dom_a = urlparse(url_a).netloc
    dom_b = urlparse(url_b).netloc

    if output_format == "markdown":
        console.print(Panel.fit(
            f"[bold cyan]RankIntel Competitive Intelligence Engine[/bold cyan]\n"
            f"[dim]Benchmarking:[/dim] [yellow]{dom_a}[/yellow] vs [green]{dom_b}[/green]\n"
            f"[dim]Triangulating technical SEO, Princeton GEO, 5-layer Trust Stack, and CWV[/dim]",
            border_style="cyan"
        ))

    with console.status(f"[bold green]Auditing {dom_a} and {dom_b} across all engines...[/bold green]", spinner="dots"):
        comparer = IntelligenceComparer()
        comparison = comparer.compare(url_a, url_b)

    if output_format == "json":
        report_file = JsonReporter.save_comparison(comparison, output_dir=output_dir)
        console.print_json(JsonReporter.render_comparison(comparison))
        console.print(f"\n[bold green]Detailed gap report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")
        return report_file

    report_file = GapReporter.save(comparison, output_dir=output_dir)

    console.print("\n[bold green][SUCCESS] Competitive Gap Analysis Completed![/bold green]\n")

    winner_dom = urlparse(comparison.winner_url).netloc if comparison.winner_url != "TIE" else "Statistical Tie"
    comp_table = Table(title=f"Head-to-Head Comparison: {dom_a} vs {dom_b}", show_header=True, header_style="bold magenta")
    comp_table.add_column("Telemetry Category", style="cyan")
    comp_table.add_column(dom_a, justify="center")
    comp_table.add_column(dom_b, justify="center")
    comp_table.add_column("Advantage", style="bold")

    for d in comparison.category_deltas:
        w_dom = urlparse(d.winner).netloc if d.winner not in ("TIE", "") else "TIE"
        if w_dom == dom_a:
            adv_str = f"[green]{dom_a}[/green]"
        elif w_dom == dom_b:
            adv_str = f"[cyan]{dom_b}[/cyan]"
        else:
            adv_str = "[dim]Tie[/dim]"
        comp_table.add_row(d.category, str(d.target_a_val), str(d.target_b_val), adv_str)

    console.print(comp_table)
    console.print(f"\n[bold yellow]Overall Leader:[/bold yellow] [bold green]{winner_dom}[/bold green] (Gap: {comparison.score_gap} pts)")

    if comparison.action_plan:
        console.print("\n[bold cyan]Top Competitive Remediation Actions:[/bold cyan]")
        for idx, act in enumerate(comparison.action_plan[:4], 1):
            console.print(f"  {idx}. [bold red][+{act.impact_points} pts][/bold red] [bold]{act.title}[/bold]")
            console.print(f"     [dim]Advantage:[/dim] {act.winning_advantage}\n")

    console.print(f"[bold green]Detailed gap report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")
    return report_file


def run_review(
    target: Optional[str] = None,
    output_dir: str = "benchmarks/reviews",
    output_format: str = "markdown",
):
    import json
    from pathlib import Path
    from rankintel.benchmark.reviewer import WebsiteIntelligenceReviewer, _clean_domain
    from rankintel.reporters.review_reporter import ReviewReporter

    if target in (None, "", "all", "--all"):
        console.print(Panel.fit(
            f"[bold cyan]RankIntel Phase 11.2 — Website Intelligence Reviewer[/bold cyan]\n"
            f"[dim]Synthesizing 18 Intelligence Dimensions across Permanent 11-Site Benchmark[/dim]",
            border_style="cyan"
        ))
        with console.status("[bold green]Synthesizing website intelligence reviews from benchmark packages...[/bold green]", spinner="dots"):
            dataset = WebsiteIntelligenceReviewer.review_all(packages_dir="benchmarks/packages", output_dir=output_dir)

        if output_format == "json":
            console.print_json(dataset.model_dump_json(indent=2))
            return output_dir

        table = Table(title="11-Site Website Intelligence Review Matrix", show_header=True, header_style="bold magenta")
        table.add_column("Domain", style="cyan")
        table.add_column("Role", justify="center")
        table.add_column("Health", justify="center")
        table.add_column("Entities", justify="center")
        table.add_column("Topics", justify="center")
        table.add_column("Answer Units", justify="center")
        table.add_column("Claims Grounded", justify="center")
        table.add_column("Visual Assets", justify="center")
        table.add_column("WAF Barrier", justify="center")

        for item in dataset.summary_index:
            table.add_row(
                item["domain"],
                item["role"],
                str(item["health_score"]),
                str(item["entities_detected"]),
                str(item["topics_detected"]),
                str(item["answer_units"]),
                item["claims_grounded"],
                str(item["visual_assets"]),
                "Cloudflare" if item["waf_detected"] else "None",
            )
        console.print(table)
        console.print(f"\n[bold green][SUCCESS] Successfully reviewed {dataset.sites_reviewed} benchmark sites![/bold green]")
        console.print(f"Reports saved to: [underline cyan]{output_dir}/[/underline cyan] (.json & .md)")
        return output_dir
    else:
        clean_target = _clean_domain(target)
        pkg_file = os.path.join("benchmarks", "packages", f"{clean_target}.json")
        if not os.path.exists(pkg_file):
            matched = False
            for p in Path("benchmarks/packages").glob("*.json"):
                with open(p, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                if _clean_domain(pdata.get("domain", "")) == clean_target:
                    pkg_file = str(p)
                    matched = True
                    break
            if not matched:
                console.print(f"[bold red]Error:[/bold red] Benchmark package for '{target}' not found in benchmarks/packages/.")
                return None

        pkg = WebsiteIntelligenceReviewer.load_package(pkg_file)
        review = WebsiteIntelligenceReviewer.synthesize_review(pkg)
        json_path, md_path = ReviewReporter.save_review_pair(review, output_dir=output_dir)

        if output_format == "json":
            console.print_json(ReviewReporter.render_json(review))
            return json_path

        console.print(Panel.fit(
            f"[bold cyan]Website Intelligence Review: {review.name or review.domain}[/bold cyan]\n"
            f"[dim]URL:[/dim] {review.site_url} | [dim]Health Score:[/dim] {review.overall_health_score}/100 | [dim]Invariance:[/dim] Δ=0\n"
            f"[dim]Industry:[/dim] {review.business_profile.primary_industry_domain}\n"
            f"[dim]Intent:[/dim] {review.search_intent.primary_intent} | [dim]Entities:[/dim] {review.entity_profile.total_entities_detected} | [dim]Topics:[/dim] {review.topic_taxonomy.total_topics_detected}\n"
            f"[dim]Answer Units:[/dim] {review.answerability.total_units_detected} | [dim]Claims Grounded:[/dim] {review.claim_grounding.supported_claims_count}/{review.claim_grounding.total_claims_detected}",
            border_style="cyan"
        ))
        console.print(f"[bold green]Markdown Review:[/bold green] [underline cyan]{md_path}[/underline cyan]")
        console.print(f"[bold green]JSON Profile:[/bold green] [underline cyan]{json_path}[/underline cyan]")
        return md_path


def run_compare_benchmark(
    target: Optional[str] = None,
    reviews_file: str = "benchmarks/reviews/benchmark_reviews_phase11.json",
    output_dir: str = "benchmarks/comparisons",
    output_format: str = "markdown",
):
    from rankintel.benchmark.comparator import CrossSiteComparator
    from rankintel.reporters.comparison_reporter import ComparisonReporter

    console.print(Panel.fit(
        f"[bold cyan]RankIntel Phase 11.3 — Cross-Site Benchmark Comparison & Void Analysis[/bold cyan]\n"
        f"[dim]Deterministic analysis across 11-site benchmark without superiority scoring (Δ=0)[/dim]",
        border_style="cyan"
    ))

    with console.status("[bold green]Executing deterministic cross-site comparison & void analysis...[/bold green]", spinner="dots"):
        report = CrossSiteComparator.compare(reviews_file, target_domain=target)
        saved_paths = ComparisonReporter.save_comparison_artifacts(report, output_dir=output_dir)

    if output_format == "json":
        console.print_json(ComparisonReporter.render_json(report))
        return saved_paths["comparison_json"]

    table = Table(title="Cross-Site Benchmark Intelligence Matrix", show_header=True, header_style="bold magenta")
    table.add_column("Domain", style="cyan")
    table.add_column("Role", justify="center")
    table.add_column("Health", justify="center")
    table.add_column("Tech", justify="center")
    table.add_column("GEO", justify="center")
    table.add_column("Schema", justify="center")
    table.add_column("Answer Units", justify="center")
    table.add_column("Grounded %", justify="center")
    table.add_column("Alt %", justify="center")
    table.add_column("Forms", justify="center")
    table.add_column("Buttons", justify="center")
    table.add_column("WAF", justify="center")

    for item in report.cross_site_matrix:
        role_str = "[bold green]TARGET[/bold green]" if item.role in ("target", "sunrise") else "Competitor"
        table.add_row(
            item.domain,
            role_str,
            str(item.health_score),
            str(item.technical_health_score),
            str(item.geo_readiness_score),
            str(item.schema_types_count),
            str(item.answer_units_count),
            f"{int(item.claims_grounded_ratio * 100)}%",
            f"{int(item.alt_coverage_ratio * 100)}%",
            str(item.forms_count),
            str(item.buttons_count),
            item.waf_barrier,
        )
    console.print(table)

    void_table = Table(title=f"Observable Voids Detected for Target: {report.target_domain}", show_header=True, header_style="bold yellow")
    void_table.add_column("Void ID", style="cyan")
    void_table.add_column("Category", justify="center")
    void_table.add_column("Title", style="white")
    void_table.add_column("State", justify="center")
    void_table.add_column("Cohort Preval.", justify="center")

    for v in report.target_vs_benchmark.observable_voids:
        void_table.add_row(
            v.void_id,
            v.category,
            v.title,
            v.state.value,
            f"{len(v.source_sites_present)} sites",
        )
    console.print(void_table)

    console.print(f"\n[bold green][SUCCESS] Cross-site comparison completed across {report.total_sites} sites![/bold green]")
    console.print(f"Main Comparison Markdown: [underline cyan]{saved_paths['comparison_md']}[/underline cyan]")
    console.print(f"Main Comparison JSON:     [underline cyan]{saved_paths['comparison_json']}[/underline cyan]")
    console.print(f"Target vs Benchmark MD:   [underline cyan]{saved_paths['target_md']}[/underline cyan]")
    console.print(f"Target vs Benchmark JSON: [underline cyan]{saved_paths['target_json']}[/underline cyan]")
    return saved_paths["comparison_md"]


def run_analyze_gaps(
    comparison_file: str = "benchmarks/comparisons/benchmark_comparison_phase11.json",
    output_dir: str = "benchmarks/capabilities",
    output_format: str = "markdown",
):
    from rankintel.benchmark.gap_analyzer import CapabilityGapAnalyzer
    from rankintel.reporters.capability_gap_reporter import CapabilityGapReporter

    console.print(Panel.fit(
        f"[bold cyan]RankIntel Phase 11.4 — Capability-Gap Discovery & Engine Evolution Analysis[/bold cyan]\n"
        f"[dim]Deterministic analysis identifying RankIntel capability gaps vs website deficiencies (Δ=0)[/dim]",
        border_style="cyan"
    ))

    with console.status("[bold green]Executing deterministic capability-gap analysis...[/bold green]", spinner="dots"):
        report, json_path, md_path = CapabilityGapAnalyzer.run_analysis(
            comparison_path=comparison_file,
            output_dir=output_dir,
        )

    if output_format == "json":
        console.print_json(CapabilityGapReporter.render_json(report))
        return json_path

    # Summary table of priority distribution
    p_table = Table(title="Capability Gap Severity Distribution", show_header=True, header_style="bold magenta")
    p_table.add_column("Severity", justify="center", style="cyan")
    p_table.add_column("Count", justify="center", style="green")
    p_table.add_column("Description", style="white")

    p_table.add_row("P0", str(report.priority_breakdown.get("P0", 0)), "Critical architectural or detection gap causing total engine blindness")
    p_table.add_row("P1", str(report.priority_breakdown.get("P1", 0)), "Major semantic or extraction gap causing substantial analysis distortion")
    p_table.add_row("P2", str(report.priority_breakdown.get("P2", 0)), "Moderate heuristic, sanitization, or coverage limitation")
    p_table.add_row("P3", str(report.priority_breakdown.get("P3", 0)), "Minor cosmetic or peripheral reporting discrepancy")
    console.print(p_table)

    # Catalog table
    gap_table = Table(title="Discovered RankIntel Capability Gaps Catalog", show_header=True, header_style="bold yellow")
    gap_table.add_column("Gap ID", style="cyan")
    gap_table.add_column("Category", justify="center")
    gap_table.add_column("Engine", style="green")
    gap_table.add_column("Sev", justify="center")
    gap_table.add_column("Title", style="white")
    gap_table.add_column("Conf.", justify="center")

    for g in report.gaps:
        gap_table.add_row(
            g.gap_id,
            g.category.value,
            g.affected_engine.split("/")[-1],
            g.severity.value,
            g.title[:45] + ("..." if len(g.title) > 45 else ""),
            f"{int(g.confidence * 100)}%",
        )
    console.print(gap_table)

    # Exclusions table
    ex_table = Table(title="False-Gap Exclusions (Confirmed Website Deficiencies)", show_header=True, header_style="bold blue")
    ex_table.add_column("Exclusion ID", style="cyan")
    ex_table.add_column("Candidate Finding", style="white")
    ex_table.add_column("Classification", justify="center", style="green")
    for ex in report.false_gap_exclusions:
        ex_table.add_row(
            ex.exclusion_id,
            ex.candidate_gap[:50] + ("..." if len(ex.candidate_gap) > 50 else ""),
            ex.classification.value,
        )
    console.print(ex_table)

    console.print(f"\n[bold green][SUCCESS] Capability gap analysis completed across {report.total_sites_analyzed} benchmark sites![/bold green]")
    console.print(f"Capability Gaps Markdown: [underline cyan]{md_path}[/underline cyan]")
    console.print(f"Capability Gaps JSON:     [underline cyan]{json_path}[/underline cyan]")
    return md_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] python audit_engine.py <url> [--format json] [--deep-crawl] [--external-ai] [--external-providers gemini,mock] OR python audit_engine.py compare <url1> vs <url2> [--format json] OR python audit_engine.py benchmark [--external-ai] OR python audit_engine.py review [<domain>|all] [--format json] OR python audit_engine.py compare-benchmark [--target <domain>] [--format json] OR python audit_engine.py analyze-gaps [--format json]")
        sys.exit(1)


    fmt = "json" if "--format" in sys.argv and "json" in sys.argv else ("json" if "--json" in sys.argv else "markdown")
    deep = "--deep-crawl" in sys.argv
    ext_ai = "--external-ai" in sys.argv

    ext_prov = None
    if "--external-providers" in sys.argv:
        try:
            prov_idx = sys.argv.index("--external-providers") + 1
            if prov_idx < len(sys.argv) and not sys.argv[prov_idx].startswith("--"):
                ext_prov = sys.argv[prov_idx]
        except (ValueError, IndexError):
            pass

    target_opt = None
    if "--target" in sys.argv:
        try:
            t_idx = sys.argv.index("--target") + 1
            if t_idx < len(sys.argv) and not sys.argv[t_idx].startswith("--"):
                target_opt = sys.argv[t_idx]
        except (ValueError, IndexError):
            pass

    cleaned_args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in ("json", "markdown") and (ext_prov is None or a != ext_prov) and (target_opt is None or a != target_opt)]

    if cleaned_args and cleaned_args[0].lower() in ("analyze-gaps", "capability-gaps", "gap-analysis"):
        run_analyze_gaps(output_format=fmt)
    elif cleaned_args and cleaned_args[0].lower() in ("compare-benchmark", "void-analysis"):
        t_site = cleaned_args[1] if len(cleaned_args) > 1 else target_opt
        run_compare_benchmark(target=t_site, output_format=fmt)

    elif cleaned_args and cleaned_args[0].lower() == "compare" and len(cleaned_args) > 1 and cleaned_args[1].lower() == "benchmark":
        t_site = cleaned_args[2] if len(cleaned_args) > 2 else target_opt
        run_compare_benchmark(target=t_site, output_format=fmt)
    elif cleaned_args and cleaned_args[0].lower() == "compare":
        if len(cleaned_args) < 3:
            console.print("[bold red]Usage:[/bold red] python audit_engine.py compare <url1> vs <url2> [--format json]")
            sys.exit(1)
        url1 = cleaned_args[1]
        url2 = cleaned_args[3] if len(cleaned_args) > 3 and cleaned_args[2].lower() == "vs" else cleaned_args[2]
        run_compare(url1, url2, output_format=fmt)
    elif cleaned_args and cleaned_args[0].lower() in ("benchmark", "benchmarks"):
        from rankintel.benchmark.collector import BenchmarkCollector
        collector = BenchmarkCollector(
            external_ai=ext_ai,
            external_providers=[p.strip() for p in ext_prov.split(",")] if ext_prov else None,
        )
        collector.collect_all(workers=3)
    elif cleaned_args and cleaned_args[0].lower() in ("review", "reviews"):
        target_site = cleaned_args[1] if len(cleaned_args) > 1 else None
        run_review(target=target_site, output_format=fmt)
    elif cleaned_args:
        target_url = cleaned_args[0]
        run_audit(
            target_url,
            output_format=fmt,
            deep_crawl=deep,
            external_ai=ext_ai,
            external_providers=ext_prov,
        )

