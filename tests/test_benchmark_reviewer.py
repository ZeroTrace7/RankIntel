"""
Tests for Phase 11.2 Website-Level Intelligence Review Layer.
Validates synthesis across all 11 benchmark sites, 18-dimension schema conformance,
deterministic transformation, zero-network isolation, formula invariance (delta=0),
and Markdown/JSON output parity.
"""
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch
import pytest

from rankintel.benchmark.models import (
    ReviewDimensionStatus,
    ObservableBusinessProfile,
    EntityProfile,
    ServiceProductProfile,
    TopicTaxonomyProfile,
    SearchIntentProfile,
    TopicDistributionProfile,
    PageTopicConcentrationProfile,
    TechnicalSeoReviewProfile,
    AccessibilitySecurityProfile,
    InternalLinkStructureProfile,
    RetrievalReadinessProfile,
    AnswerabilityReviewProfile,
    ClaimGroundingReviewProfile,
    MultimodalReviewProfile,
    AgentReadinessReviewProfile,
    ExternalAiReviewProfile,
    EvidenceLimitationsProfile,
    WebsiteIntelligenceReview,
    BenchmarkReviewDataset,
    SiteIntelligencePackage,
)
from rankintel.benchmark.reviewer import WebsiteIntelligenceReviewer, _clean_domain
from rankintel.reporters.review_reporter import ReviewReporter
from audit_engine import run_review


@pytest.fixture
def packages_dir():
    return Path("benchmarks/packages")


@pytest.fixture
def all_packages(packages_dir):
    pfiles = sorted(list(packages_dir.glob("*.json")))
    assert len(pfiles) == 11, f"Expected 11 benchmark packages, found {len(pfiles)}"
    packages = []
    for pf in pfiles:
        with open(pf, "r", encoding="utf-8") as f:
            data = json.load(f)
        pkg = SiteIntelligencePackage.model_validate(data)
        packages.append(pkg)
    return packages


def test_review_models_instantiation():
    """Verify clean instantiation of all Phase 11.2 review profile models."""
    biz = ObservableBusinessProfile(
        status=ReviewDimensionStatus.AVAILABLE,
        business_name="Test Enterprise",
        branding_title="Test Title",
        primary_industry_domain="Testing",
    )
    assert biz.business_name == "Test Enterprise"
    assert biz.status == ReviewDimensionStatus.AVAILABLE

    rev = WebsiteIntelligenceReview(
        domain="example.com",
        site_url="https://example.com/",
        name="Example",
        role="competitor",
        collection_timestamp="2026-10-04",
        review_timestamp="2026-10-04",
        overall_health_score=75,
        technical_health_score=80,
        geo_readiness_score=70,
        trust_score=60,
        performance_score=90,
    )
    assert rev.overall_health_score == 75
    assert rev.domain == "example.com"
    assert rev.formula_invariance_verified is True


def test_clean_domain_utility():
    """Test domain cleaning utility with various prefixes and schemes."""
    assert _clean_domain("https://www.tcreng.com/") == "tcreng.com"
    assert _clean_domain("http://alephindia.in") == "alephindia.in"
    assert _clean_domain("www.ascgroup.in") == "ascgroup.in"
    assert _clean_domain("sunrisetesting.vercel.app/") == "sunrisetesting.vercel.app"


def test_deterministic_synthesis_all_11_sites(all_packages):
    """Verify that all 11 benchmark packages synthesize cleanly and deterministically."""
    for pkg in all_packages:
        rev1 = WebsiteIntelligenceReviewer.synthesize_review(pkg)
        rev2 = WebsiteIntelligenceReviewer.synthesize_review(pkg)

        assert isinstance(rev1, WebsiteIntelligenceReview)
        assert rev1.domain == pkg.domain
        assert rev1.overall_health_score == pkg.overall_health_score

        # Verify determinism / idempotence
        assert rev1.model_dump_json() == rev2.model_dump_json()

        # Verify all 18 profiles are populated
        assert rev1.business_profile.status in ReviewDimensionStatus
        assert rev1.entity_profile.status in ReviewDimensionStatus
        assert rev1.service_profile.status in ReviewDimensionStatus
        assert rev1.topic_taxonomy.status in ReviewDimensionStatus
        assert isinstance(rev1.dominant_concepts, list)
        assert rev1.search_intent.status in ReviewDimensionStatus
        assert rev1.topic_distribution.status in ReviewDimensionStatus
        assert rev1.concentration_and_overlap.status in ReviewDimensionStatus
        assert rev1.technical_seo.status in ReviewDimensionStatus
        assert rev1.accessibility_security.status in ReviewDimensionStatus
        assert rev1.internal_links.status in ReviewDimensionStatus
        assert rev1.retrieval_readiness.status in ReviewDimensionStatus
        assert rev1.answerability.status in ReviewDimensionStatus
        assert rev1.claim_grounding.status in ReviewDimensionStatus
        assert rev1.multimodal.status in ReviewDimensionStatus
        assert rev1.agent_readiness.status in ReviewDimensionStatus
        assert rev1.external_ai.status in ReviewDimensionStatus
        assert rev1.limitations_and_uncertainty.status in ReviewDimensionStatus


def test_formula_invariance_delta_zero(all_packages):
    """Assert formula invariance: all 5 health scores remain delta = 0."""
    for pkg in all_packages:
        rev = WebsiteIntelligenceReviewer.synthesize_review(pkg)
        assert rev.overall_health_score == pkg.overall_health_score
        assert rev.technical_health_score == pkg.technical_health_score
        assert rev.geo_readiness_score == pkg.geo_readiness_score
        assert rev.trust_score == pkg.trust_score
        assert rev.performance_score == pkg.performance_score
        assert rev.score_formula_mode == pkg.score_formula_mode
        assert rev.formula_invariance_verified is True


def test_zero_network_calls_during_review(all_packages):
    """Assert that review synthesis introduces zero network socket calls."""
    def guarded_connect(*args, **kwargs):
        raise RuntimeError("Network call attempted during offline review synthesis!")

    with patch.object(socket.socket, "connect", side_effect=guarded_connect):
        for pkg in all_packages:
            rev = WebsiteIntelligenceReviewer.synthesize_review(pkg)
            assert rev is not None
            # Also test markdown and json rendering under network guard
            md = WebsiteIntelligenceReviewer.render_markdown(rev)
            assert len(md) > 500
            js = rev.model_dump_json()
            assert len(js) > 500


def test_epistemic_separation_preservation(all_packages):
    """Verify that epistemic separation is strictly preserved across all 11 reviews."""
    for pkg in all_packages:
        rev = WebsiteIntelligenceReviewer.synthesize_review(pkg)
        ep = rev.epistemic_separation
        assert isinstance(ep.facts, list)
        assert isinstance(ep.external_observations, list)
        assert isinstance(ep.analyses, list)
        assert isinstance(ep.recommendations, list)
        assert len(ep.facts) > 0
        assert len(ep.analyses) > 0


def test_provenance_preservation(all_packages):
    """Verify that provenance tags and engine attributions are attached."""
    for pkg in all_packages:
        rev = WebsiteIntelligenceReviewer.synthesize_review(pkg)
        assert len(rev.provenance_tags) == len(pkg.provenance_tags)
        assert len(rev.engines_executed) == len(pkg.engines_executed)
        for tag in rev.provenance_tags:
            assert "engine" in tag
            assert "finding" in tag
            assert "confidence" in tag


def test_output_parity_markdown_and_json(all_packages):
    """Verify output parity: markdown and JSON contain identical facts and figures."""
    for pkg in all_packages:
        rev = WebsiteIntelligenceReviewer.synthesize_review(pkg)
        md = WebsiteIntelligenceReviewer.render_markdown(rev)
        js_data = json.loads(rev.model_dump_json())

        # Assert key numbers are identically present in markdown text
        assert str(rev.overall_health_score) in md
        assert str(rev.technical_health_score) in md
        assert str(rev.geo_readiness_score) in md
        assert str(rev.trust_score) in md
        assert str(rev.performance_score) in md
        assert rev.domain in md
        assert str(rev.entity_profile.total_entities_detected) in md
        assert str(rev.topic_taxonomy.total_topics_detected) in md
        assert str(rev.answerability.total_units_detected) in md
        assert str(rev.claim_grounding.total_claims_detected) in md
        assert str(rev.multimodal.total_visual_assets) in md

        # Assert JSON data matches review object
        assert js_data["overall_health_score"] == rev.overall_health_score
        assert js_data["entity_profile"]["total_entities_detected"] == rev.entity_profile.total_entities_detected


def test_review_reporter_persistence(tmp_path, all_packages):
    """Verify ReviewReporter saves valid JSON and Markdown files."""
    pkg = all_packages[0]
    rev = WebsiteIntelligenceReviewer.synthesize_review(pkg)

    json_file, md_file = ReviewReporter.save_review_pair(rev, output_dir=str(tmp_path))
    assert os.path.exists(json_file)
    assert os.path.exists(md_file)

    with open(json_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["domain"] == rev.domain
    assert loaded["overall_health_score"] == rev.overall_health_score

    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()
    assert rev.domain in md_text


def test_review_all_generates_aggregate_dataset(tmp_path):
    """Verify WebsiteIntelligenceReviewer.review_all constructs complete dataset."""
    dataset = WebsiteIntelligenceReviewer.review_all(
        packages_dir="benchmarks/packages",
        output_dir=str(tmp_path),
    )
    assert isinstance(dataset, BenchmarkReviewDataset)
    assert dataset.total_sites == 11
    assert dataset.sites_reviewed == 11
    assert len(dataset.reviews) == 11
    assert len(dataset.summary_index) == 11

    agg_file = tmp_path / "benchmark_reviews_phase11.json"
    assert agg_file.exists()
    with open(agg_file, "r", encoding="utf-8") as f:
        agg_data = json.load(f)
    assert agg_data["total_sites"] == 11


def test_cli_run_review_all(tmp_path):
    """Test CLI runner review for all benchmark sites."""
    out_dir = run_review(target="all", output_dir=str(tmp_path), output_format="markdown")
    assert out_dir == str(tmp_path)
    assert (tmp_path / "benchmark_reviews_phase11.json").exists()


def test_cli_run_review_single_site(tmp_path):
    """Test CLI runner review for a single site."""
    out_file = run_review(target="alephindia.in", output_dir=str(tmp_path), output_format="markdown")
    assert out_file is not None
    assert Path(out_file).exists()
    assert "alephindia.in.md" in out_file
