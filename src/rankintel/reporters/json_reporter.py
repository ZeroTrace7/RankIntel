"""
JSON Reporter — Exports multi-engine SynthesisReport and ComparisonReport as formatted JSON.
Enables agentic before-and-after optimization loops and CI/CD pipelines.
"""
from __future__ import annotations
import os
from urllib.parse import urlparse
from rankintel.models.schema import SynthesisReport, ComparisonReport

class JsonReporter:
    """Serializes RankIntel evidence models to structured JSON."""

    @staticmethod
    def render_audit(report: SynthesisReport, indent: int = 2) -> str:
        """Serialize SynthesisReport to JSON string."""
        return report.model_dump_json(indent=indent)

    @staticmethod
    def render_comparison(report: ComparisonReport, indent: int = 2) -> str:
        """Serialize ComparisonReport to JSON string."""
        return report.model_dump_json(indent=indent)

    @classmethod
    def save_audit(cls, report: SynthesisReport, output_dir: str = "audits") -> str:
        """Render and save audit report to JSON file on disk."""
        os.makedirs(output_dir, exist_ok=True)
        domain_clean = report.domain.replace("www.", "").replace(":", "_")
        filename = f"{domain_clean}-{report.timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cls.render_audit(report))

        return filepath

    @classmethod
    def save_comparison(cls, report: ComparisonReport, output_dir: str = "reports") -> str:
        """Render and save comparison report to JSON file on disk."""
        os.makedirs(output_dir, exist_ok=True)
        dom_a = urlparse(report.target_a_url).netloc.replace("www.", "").replace(":", "_")
        dom_b = urlparse(report.target_b_url).netloc.replace("www.", "").replace(":", "_")
        filename = f"comparison-{dom_a}-vs-{dom_b}-{report.timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cls.render_comparison(report))

        return filepath
