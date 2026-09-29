"""
RankIntel CLI — Autonomous Search & Intelligence Triangulation Engine.
"""
from __future__ import annotations
import sys
import click

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.reporters.markdown import MarkdownReporter

console = Console(highlight=False)

@click.group()
def main():
    """RankIntel — Multi-Engine SEO, GEO & AI Search Triangulation Platform."""
    pass

@main.command()
@click.argument("url")
@click.option("--output-dir", default="audits", help="Directory to save audit report")
def audit(url: str, output_dir: str):
    """Run full multi-engine SEO, GEO, and browser triangulation audit."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    console.print(Panel.fit(
        f"[bold cyan]RankIntel Intelligence Engine v2.0[/bold cyan]\n"
        f"[dim]Triangulating:[/dim] [yellow]advertools (SEO)[/yellow] + [green]crawl4ai (Browser)[/green] + [magenta]RankIntel (GEO/AEO)[/magenta]\n"
        f"[bold white]Target:[/bold white] [underline]{url}[/underline]",
        border_style="cyan"
    ))

    # Phase 1: Collect Evidence
    with console.status("[bold green]Executing multi-engine audit pass...[/bold green]", spinner="dots"):
        collector = EvidenceCollector()
        engine_results = collector.collect(url)

    # Phase 2: Synthesize Intelligence
    with console.status("[bold cyan]Reconciling evidence and detecting cross-engine conflicts...[/bold cyan]", spinner="dots"):
        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize(url, engine_results)

    # Phase 3: Persist Audit Report
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
        "AI Search Bot Status",
        f"{len([b for b in report.unified_robots.bot_access.values() if b.status == 'ALLOWED'])} Allowed",
        "RFC robots parser"
    )
    table.add_row(
        "Machine-Readable /llms.txt",
        "Present" if report.unified_geo.llms_txt_found else "Missing",
        "llmstxt.org v2 check"
    )

    console.print(table)

    if report.conflicts_detected:
        console.print("\n[bold yellow]Triangulation Insights & Engine Conflicts Detected:[/bold yellow]")
        for c in report.conflicts_detected:
            console.print(f"  • [bold red][{c.severity}][/bold red] [bold]{c.feature}:[/bold] {c.description}")
            console.print(f"    [dim]Interpretation:[/dim] {c.interpretation}\n")

    console.print(f"[bold green]Report saved to:[/bold green] [underline cyan]{report_file}[/underline cyan]")

if __name__ == "__main__":
    main()
