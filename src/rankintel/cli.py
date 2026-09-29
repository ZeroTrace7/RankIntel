"""
RankIntel CLI — Autonomous Search & Intelligence Triangulation Engine.
"""
from __future__ import annotations
import sys
import click
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.intelligence.comparer import IntelligenceComparer
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.gap_reporter import GapReporter
from rankintel.reporters.json_reporter import JsonReporter

console = Console(highlight=False)

@click.group()
def main():
    """RankIntel — Multi-Engine SEO, GEO & AI Search Triangulation Platform."""
    pass

@main.command()
@click.argument("url")
@click.option("--output-dir", default="audits", help="Directory to save audit report")
@click.option("--format", "output_format", default="markdown", type=click.Choice(["markdown", "json"], case_sensitive=False), help="Output format: 'markdown' (default) or 'json'")
@click.option("--deep-crawl", is_flag=True, default=False, help="Crawl internal pages for site-wide hygiene issues")
@click.option("--max-pages", default=25, help="Maximum pages to crawl in deep mode")
def audit(url: str, output_dir: str, output_format: str, deep_crawl: bool, max_pages: int):
    """Run full multi-engine SEO, GEO, browser, and performance triangulation audit."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    if output_format == "markdown":
        console.print(Panel.fit(
            f"[bold cyan]RankIntel Intelligence Engine v3.0[/bold cyan]\n"
            f"[dim]Triangulating:[/dim] [yellow]advertools (SEO)[/yellow] + [green]crawl4ai (Browser)[/green] + [magenta]RankIntel (GEO/AEO)[/magenta] + [blue]CWV/CrUX[/blue] + [cyan]OpenSEO MCP[/cyan]\n"
            f"[bold white]Target:[/bold white] [underline]{url}[/underline]",
            border_style="cyan"
        ))

    # Phase 1: Collect Evidence
    with console.status("[bold green]Executing multi-engine audit pass...[/bold green]", spinner="dots"):
        collector = EvidenceCollector()
        engine_results = collector.collect(url)

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
        return

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
    if report.cloud_intelligence.available:
        traf = report.cloud_intelligence.keywords.estimated_monthly_traffic if report.cloud_intelligence.keywords else 0
        table.add_row(
            "Organic Search Traffic",
            f"{traf:,} visits/mo",
            "OpenSEO MCP"
        )
    if report.site_crawl:
        table.add_row(
            "Site-Wide Multi-Page Scope",
            f"{report.site_crawl.pages_crawled} pages audited ({report.site_crawl.pages_with_issues} issues)",
            "advertools multi-page spider"
        )

    console.print(table)

    if report.conflicts_detected:
        console.print("\n[bold yellow]Triangulation Insights & Engine Conflicts Detected:[/bold yellow]")
        for c in report.conflicts_detected:
            console.print(f"  • [bold red][{c.severity}][/bold red] [bold]{c.feature}:[/bold] {c.description}")
            console.print(f"    [dim]Interpretation:[/dim] {c.interpretation}\n")

    console.print(f"[bold green]Report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")

@main.command()
@click.argument("target_a")
@click.argument("args", nargs=-1, required=True)
@click.option("--output-dir", default="reports", help="Directory to save comparison report")
@click.option("--format", "output_format", default="markdown", type=click.Choice(["markdown", "json"], case_sensitive=False), help="Output format: 'markdown' (default) or 'json'")
def compare(target_a: str, args: tuple, output_dir: str, output_format: str):
    """Run competitive gap analysis between two URLs (e.g. `rankintel compare url1 vs url2`)."""
    if len(args) == 0:
        console.print("[bold red]Error: Please specify the second URL to compare against.[/bold red]")
        sys.exit(1)

    target_b = args[1] if args[0].lower() == "vs" and len(args) > 1 else args[0]

    if not target_a.startswith("http://") and not target_a.startswith("https://"):
        target_a = "https://" + target_a
    if not target_b.startswith("http://") and not target_b.startswith("https://"):
        target_b = "https://" + target_b

    dom_a = urlparse(target_a).netloc
    dom_b = urlparse(target_b).netloc

    if output_format == "markdown":
        console.print(Panel.fit(
            f"[bold cyan]RankIntel Competitive Intelligence Engine[/bold cyan]\n"
            f"[dim]Benchmarking:[/dim] [yellow]{dom_a}[/yellow] vs [green]{dom_b}[/green]\n"
            f"[dim]Triangulating technical SEO, Princeton GEO, 5-layer Trust Stack, and CWV[/dim]",
            border_style="cyan"
        ))

    with console.status(f"[bold green]Auditing {dom_a} and {dom_b} across all engines...[/bold green]", spinner="dots"):
        comparer = IntelligenceComparer()
        comparison = comparer.compare(target_a, target_b)

    # Save and output report
    if output_format == "json":
        report_file = JsonReporter.save_comparison(comparison, output_dir=output_dir)
        console.print_json(JsonReporter.render_comparison(comparison))
        console.print(f"\n[bold green]Detailed gap report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")
        return

    report_file = GapReporter.save(comparison, output_dir=output_dir)

    console.print("\n[bold green][SUCCESS] Competitive Gap Analysis Completed![/bold green]\n")

    # Display comparison table
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

if __name__ == "__main__":
    main()
