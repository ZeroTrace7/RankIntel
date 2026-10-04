"""
Phase 11.4 — Capability Gap Reporter.
Renders and persists CapabilityGapAnalysisReport artifacts in JSON and Markdown with 100% data parity.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from rankintel.benchmark.models import CapabilityGapAnalysisReport
from rankintel.benchmark.gap_analyzer import CapabilityGapAnalyzer


class CapabilityGapReporter:
    """Reporter interface for Phase 11.4 capability gap discovery artifacts."""

    @classmethod
    def render_markdown(cls, report: CapabilityGapAnalysisReport) -> str:
        """Render comprehensive GitHub-Flavored Markdown report."""
        return CapabilityGapAnalyzer.render_markdown(report)

    @classmethod
    def render_json(cls, report: CapabilityGapAnalysisReport) -> str:
        """Render formatted JSON."""
        return report.model_dump_json(indent=2)

    @classmethod
    def save_reports(
        cls,
        report: CapabilityGapAnalysisReport,
        output_dir: str = "benchmarks/capabilities",
    ) -> Tuple[str, str]:
        """Save both JSON and Markdown artifacts to output directory with 100% data parity."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        json_file = out_path / "capability_gaps_phase11.json"
        md_file = out_path / "capability_gaps_phase11.md"

        with open(json_file, "w", encoding="utf-8") as f:
            f.write(cls.render_json(report))

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(cls.render_markdown(report))

        return str(json_file), str(md_file)
