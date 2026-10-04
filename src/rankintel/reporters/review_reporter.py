"""
Review Reporter — Formats and persists Phase 11.2 Website Intelligence Reviews.
Supports both structured JSON and detailed Markdown representations with 100% output parity.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from rankintel.benchmark.models import WebsiteIntelligenceReview, BenchmarkReviewDataset
from rankintel.benchmark.reviewer import WebsiteIntelligenceReviewer, _clean_domain


class ReviewReporter:
    """Reporter interface for rendering and persisting Website Intelligence Reviews."""

    @staticmethod
    def render_json(review: WebsiteIntelligenceReview, indent: int = 2) -> str:
        """Render WebsiteIntelligenceReview as JSON string."""
        return review.model_dump_json(indent=indent)

    @staticmethod
    def render_markdown(review: WebsiteIntelligenceReview) -> str:
        """Render WebsiteIntelligenceReview as detailed GitHub Markdown."""
        return WebsiteIntelligenceReviewer.render_markdown(review)

    @classmethod
    def save_review_json(
        cls,
        review: WebsiteIntelligenceReview,
        output_dir: str = "benchmarks/reviews",
    ) -> str:
        """Save JSON representation of a review."""
        os.makedirs(output_dir, exist_ok=True)
        clean_dom = _clean_domain(review.domain)
        filepath = os.path.join(output_dir, f"{clean_dom}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cls.render_json(review))
        return filepath

    @classmethod
    def save_review_markdown(
        cls,
        review: WebsiteIntelligenceReview,
        output_dir: str = "benchmarks/reviews",
    ) -> str:
        """Save Markdown representation of a review."""
        os.makedirs(output_dir, exist_ok=True)
        clean_dom = _clean_domain(review.domain)
        filepath = os.path.join(output_dir, f"{clean_dom}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cls.render_markdown(review))
        return filepath

    @classmethod
    def save_review_pair(
        cls,
        review: WebsiteIntelligenceReview,
        output_dir: str = "benchmarks/reviews",
    ) -> Tuple[str, str]:
        """Save both JSON and Markdown representation of a review."""
        json_file = cls.save_review_json(review, output_dir=output_dir)
        md_file = cls.save_review_markdown(review, output_dir=output_dir)
        return json_file, md_file

    @classmethod
    def save_benchmark_dataset(
        cls,
        dataset: BenchmarkReviewDataset,
        output_dir: str = "benchmarks/reviews",
    ) -> str:
        """Save aggregate BenchmarkReviewDataset to disk."""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "benchmark_reviews_phase11.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(dataset.model_dump_json(indent=2))
        return filepath
