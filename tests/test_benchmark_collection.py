"""
Tests for Phase 11.1 Benchmark Intelligence Collection Layer.
Validates normalization across all 15 dimensions, epistemic separation,
formula invariance, provenance preservation, and network isolation.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from rankintel.benchmark.models import (
    BenchmarkDimensionStatus,
    CrawlDiscoveryDimension,
    TechnicalSeoDimension,
    AccessibilityDimension,
    SecurityDimension,
    ContentDimension,
    EntityDimension,
    InternalLinkDimension,
    SearchTopicQueryIntentDimension,
    CannibalizationSearchGapDimension,
    RetrievalReadinessDimension,
    AnswerabilityDimension,
    ClaimGroundingDimension,
    MultimodalDimension,
    AgentReadinessDimension,
    ExternalAiDimension,
    SiteIntelligencePackage,
    BenchmarkCollectionDataset,
)
from rankintel.benchmark.normalizer import BenchmarkNormalizer
from rankintel.benchmark.collector import (
    BenchmarkCollector,
    PERMANENT_11_SITES,
    _clean_domain,
)
from rankintel.models.schema import (
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    SecurityEvidence,
    SecurityStatus,
    AccessibilityEvidence,
    WcagStatus,
    ContentEvidence,
    EntityEvidence,
    InternalLinkEvidence,
    SearchSignalEvidence,
    PageTopicIntelligence,
    PageQueryEvidence,
    PageIntentEvidence,
    PageCannibalizationEvidence,
    RetrievalReadinessEvidence,
    AnswerabilityEvidence,
    ClaimGroundingEvidence,
    MultimodalAgentIntelligence,
    ExternalVisibilityEvidence,
    ExternalVisibilityStatus,
    EvidenceProvenanceTag,
    ConflictFinding,
    PrioritizedAction,
)


def _build_mock_synthesis_report(url: str = "https://example.com") -> SynthesisReport:
    """Helper to build a complete SynthesisReport with all Phase 6-10 telemetry."""
    return SynthesisReport(
        url=url,
        domain="example.com",
        timestamp="2026-10-04",
        overall_health_score=78,
        technical_health_score=85,
        geo_readiness_score=70,
        trust_score=75,
        performance_score=80,
        score_formula_mode="4_engine",
        engines_executed=["advertools_seo", "browser_engine", "rankintel_geo", "performance_engine"],
        unified_on_page=OnPageEvidence(
            url=url,
            status_code=200,
            title="Example Title",
            title_length=13,
            meta_description="Example meta description for testing.",
            meta_desc_length=38,
            h1_count=1,
            h1_text=["Main Heading"],
            h2_count=3,
            h3_count=2,
            word_count=500,
            canonical_url=url,
            internal_links=["https://example.com/about", "https://example.com/services"],
            external_links=["https://external.org/partner"],
        ),
        unified_robots=RobotsEvidence(
            found=True,
            robots_url="https://example.com/robots.txt",
            sitemaps=["https://example.com/sitemap.xml"],
        ),
        unified_schema=SchemaEvidence(
            detected_types=["Organization", "WebSite"],
            blocks_count=2,
            validation_issues=[],
        ),
        unified_geo=GeoAeoEvidence(
            overall_citability_score=70,
            llms_txt_found=True,
        ),
        unified_trust=TrustStackResult(
            overall_score=75,
            grade="B",
        ),
        unified_performance=PerformanceEvidence(
            source="local_probe",
            overall_performance_score=80,
            ttfb_ms=120.5,
        ),
        unified_security=SecurityEvidence(
            url=url,
            is_https=True,
            overall_status=SecurityStatus.PASS,
            findings=[],
        ),
        unified_accessibility=AccessibilityEvidence(
            url=url,
            wcag_aa_status=WcagStatus.PASS,
            total_violations=0,
            rules_evaluated_count=35,
            rules_passed_count=35,
        ),
        unified_content=ContentEvidence(
            url=url,
            main_content_word_count=420,
            total_body_word_count=500,
            content_to_boilerplate_ratio=0.84,
            exact_content_hash="abc123hash",
            simhash="sim123hash",
        ),
        unified_entity=EntityEvidence(
            url=url,
            total_entities_detected=3,
            facts=["Found Organization entity Example Corp"],
        ),
        unified_internal_link=InternalLinkEvidence(
            url=url,
            total_internal_links=2,
            empty_anchor_count=0,
        ),
        unified_search_signal=SearchSignalEvidence(
            url=url,
        ),
        unified_topic=PageTopicIntelligence(
            url=url,
        ),
        unified_query_page=PageQueryEvidence(
            url=url,
            total_concepts_mapped=4,
        ),
        unified_search_intent=PageIntentEvidence(
            url=url,
        ),
        unified_cannibalization=PageCannibalizationEvidence(
            url=url,
        ),
        unified_retrieval_readiness=RetrievalReadinessEvidence(
            url=url,
            search_index_allowed_count=6,
            ai_training_allowed_count=3,
            user_fetch_allowed_count=3,
            facts=["All 6 search indexers permitted"],
        ),
        unified_answerability=AnswerabilityEvidence(
            url=url,
            total_units_detected=8,
            units_by_type={"FAQ": 2, "DEFINITION": 2, "PROCEDURE_STEPS": 4},
            explained_topics_count=5,
            mentioned_only_topics_count=3,
            facts=["Extracted 8 information units across 3 types"],
        ),
        unified_claim_grounding=ClaimGroundingEvidence(
            url=url,
            total_claims_detected=6,
            supported_claims_count=5,
            agreement_count=2,
            facts=["5 of 6 claims grounded on-site"],
        ),
        unified_multimodal_agent=MultimodalAgentIntelligence(
            url=url,
            facts=["Audited visual assets and agent interaction controls"],
        ),
        unified_external_visibility=ExternalVisibilityEvidence(
            url=url,
            status=ExternalVisibilityStatus.DISABLED,
            facts=["External AI visibility measurement is disabled"],
        ),
        provenance=[
            EvidenceProvenanceTag(
                finding="HTTP Status: 200",
                source_file="https://example.com",
                engine="advertools_seo",
                confidence="high",
            )
        ],
        conflicts_detected=[
            ConflictFinding(
                category="Metadata",
                severity="LOW",
                feature="Meta Description Length",
                description="Short meta description",
                engine_a_finding="38 chars",
                engine_b_finding="Expected 120-160 chars",
                interpretation="Editorial copy is brief",
            )
        ],
        prioritized_actions=[
            PrioritizedAction(
                level="MEDIUM",
                title="Expand Meta Description",
                finding="Meta description is 38 chars",
                rationale="Ideal length is 120-160 characters for SERP snippets",
                engine_confidence="high",
            )
        ],
    )


class TestBenchmarkModels:
    """Tests data models for benchmark intelligence collection."""

    def test_site_intelligence_package_serialization(self):
        pkg = SiteIntelligencePackage(
            site_url="https://example.com/",
            domain="example.com",
            name="Example Site",
            role="competitor",
            collection_timestamp="2026-10-04",
            collection_status="SUCCESS",
            overall_health_score=78,
            technical_health_score=85,
            geo_readiness_score=70,
            trust_score=75,
            performance_score=80,
            score_formula_mode="4_engine",
            formula_invariance_verified=True,
        )
        data_json = pkg.model_dump_json()
        assert "example.com" in data_json
        assert '"overall_health_score":78' in data_json or '"overall_health_score": 78' in data_json

        loaded = SiteIntelligencePackage.model_validate_json(data_json)
        assert loaded.domain == "example.com"
        assert loaded.overall_health_score == 78
        assert loaded.formula_invariance_verified is True

    def test_benchmark_collection_dataset_assembly(self):
        pkg1 = SiteIntelligencePackage(
            site_url="https://site1.com/",
            domain="site1.com",
            collection_timestamp="2026-10-04",
            overall_health_score=65,
        )
        pkg2 = SiteIntelligencePackage(
            site_url="https://site2.com/",
            domain="site2.com",
            collection_timestamp="2026-10-04",
            overall_health_score=82,
        )
        dataset = BenchmarkCollectionDataset(
            benchmark_version="11.1",
            created_at="2026-10-04T12:00:00",
            total_sites=2,
            sites_succeeded=2,
            packages={"site1.com": pkg1, "site2.com": pkg2},
            summary_matrix=[
                {"domain": "site1.com", "overall_health_score": 65},
                {"domain": "site2.com", "overall_health_score": 82},
            ],
        )
        assert len(dataset.packages) == 2
        assert dataset.packages["site1.com"].overall_health_score == 65
        assert dataset.packages["site2.com"].overall_health_score == 82
        assert len(dataset.summary_matrix) == 2


class TestBenchmarkNormalizer:
    """Tests normalizer extraction across all 15 dimensions."""

    def test_all_15_dimensions_populated(self):
        report = _build_mock_synthesis_report("https://example.com")
        pkg = BenchmarkNormalizer.normalize(
            url="https://example.com",
            report=report,
            engine_results={},
            name="Example Site",
            role="competitor",
            execution_time_sec=4.25,
        )

        assert pkg.domain == "example.com"
        assert pkg.name == "Example Site"
        assert pkg.role == "competitor"
        assert pkg.collection_status == "SUCCESS"
        assert pkg.execution_time_sec == 4.25

        # 1. Crawl / discovery
        assert pkg.crawl_discovery.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.crawl_discovery.http_status_code == 200
        assert pkg.crawl_discovery.internal_links_count == 2
        assert pkg.crawl_discovery.robots_txt_found is True

        # 2. Technical SEO
        assert pkg.technical_seo.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.technical_seo.title == "Example Title"
        assert pkg.technical_seo.h1_count == 1
        assert "Organization" in pkg.technical_seo.detected_schema_types
        assert pkg.technical_seo.ttfb_ms == 120.5

        # 3. Accessibility
        assert pkg.accessibility.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.accessibility.wcag_status == "PASS"
        assert pkg.accessibility.total_violations == 0

        # 4. Security
        assert pkg.security.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.security.overall_status == "PASS"
        assert pkg.security.is_https is True

        # 5. Content
        assert pkg.content.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.content.main_content_words == 420
        assert pkg.content.exact_content_hash == "abc123hash"

        # 6. Entity
        assert pkg.entity.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.entity.total_entities_detected == 3

        # 7. Internal Links
        assert pkg.internal_links.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.internal_links.total_internal_links == 2

        # 8. Search / Topic / Query / Intent
        assert pkg.search_topic_query_intent.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.search_topic_query_intent.query_page_concepts_count == 4

        # 9. Cannibalization / Search gaps
        assert pkg.cannibalization_search_gaps.status == BenchmarkDimensionStatus.AVAILABLE

        # 10. Retrieval Readiness (Phase 10.1)
        assert pkg.retrieval_readiness.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.retrieval_readiness.search_index_allowed_count == 6
        assert pkg.retrieval_readiness.ai_training_allowed_count == 3

        # 11. Answerability (Phase 10.2)
        assert pkg.answerability.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.answerability.total_units_detected == 8
        assert pkg.answerability.units_by_type.get("FAQ") == 2

        # 12. Claim Grounding (Phase 10.3)
        assert pkg.claim_grounding.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.claim_grounding.supported_claims_count == 5

        # 13. Multimodal (Phase 10.4)
        assert pkg.multimodal.status == BenchmarkDimensionStatus.AVAILABLE

        # 14. Agent Readiness (Phase 10.4)
        assert pkg.agent_readiness.status == BenchmarkDimensionStatus.AVAILABLE

        # 15. External AI (Phase 10.5) - Defaults to DISABLED
        assert pkg.external_ai.status == BenchmarkDimensionStatus.DISABLED

    def test_epistemic_separation_strictness(self):
        report = _build_mock_synthesis_report("https://example.com")
        pkg = BenchmarkNormalizer.normalize(
            url="https://example.com",
            report=report,
            engine_results={},
        )
        ep = pkg.epistemic_separation
        assert len(ep.facts) > 0
        assert len(ep.external_observations) > 0
        assert len(ep.analyses) > 0
        assert len(ep.recommendations) > 0

        # Facts must contain observable HTML/HTTP attributes
        assert any("HTTP response code: 200" in f for f in ep.facts)
        assert any("Title: 'Example Title'" in f for f in ep.facts)

        # External observations must explicitly note status
        assert any("External AI measurement was disabled" in obs for obs in ep.external_observations)

        # Analyses must contain calculated health score
        assert any("Health score computed: 78/100" in a for a in ep.analyses)

        # Recommendations must contain prioritized action
        assert any("Expand Meta Description" in r for r in ep.recommendations)

    def test_formula_invariance_verification(self):
        report = _build_mock_synthesis_report("https://example.com")
        pkg = BenchmarkNormalizer.normalize(
            url="https://example.com",
            report=report,
            engine_results={},
        )
        assert pkg.overall_health_score == 78
        assert pkg.technical_health_score == 85
        assert pkg.geo_readiness_score == 70
        assert pkg.trust_score == 75
        assert pkg.performance_score == 80
        assert pkg.score_formula_mode == "4_engine"
        assert pkg.formula_invariance_verified is True

    def test_waf_blocked_status_propagation(self):
        report = _build_mock_synthesis_report("https://example.com")
        report.unified_retrieval_readiness.waf_challenge.is_blocked = True
        report.unified_retrieval_readiness.waf_challenge.waf_or_challenge_detected = True
        report.unified_retrieval_readiness.waf_challenge.waf_provider = "Cloudflare"

        pkg = BenchmarkNormalizer.normalize(
            url="https://example.com",
            report=report,
            engine_results={},
        )
        assert pkg.retrieval_readiness.status == BenchmarkDimensionStatus.BLOCKED
        assert pkg.retrieval_readiness.waf_blocked is True
        assert pkg.retrieval_readiness.waf_provider == "Cloudflare"

    def test_provenance_and_conflicts_preserved(self):
        report = _build_mock_synthesis_report("https://example.com")
        pkg = BenchmarkNormalizer.normalize(
            url="https://example.com",
            report=report,
            engine_results={},
        )
        assert len(pkg.provenance_tags) == 1
        assert pkg.provenance_tags[0]["finding"] == "HTTP Status: 200"
        assert pkg.provenance_tags[0]["engine"] == "advertools_seo"

        assert len(pkg.conflicts_detected) == 1
        assert pkg.conflicts_detected[0]["feature"] == "Meta Description Length"


class TestBenchmarkCollector:
    """Tests the benchmark collection orchestrator."""

    def test_permanent_11_sites_list(self):
        assert len(PERMANENT_11_SITES) == 11
        domains = [s["domain"] for s in PERMANENT_11_SITES]
        expected_domains = [
            "alephindia.in",
            "tcreng.com",
            "zaubacorp.com",
            "yadavmeasurements.com",
            "uniquemeasurement.com",
            "qualityinternational.org",
            "ascgroup.in",
            "standphillindia.in",
            "umspcs.in",
            "sqccertification.com",
            "sunrisetesting.vercel.app",
        ]
        assert domains == expected_domains

    def test_clean_domain_utility(self):
        assert _clean_domain("https://www.tcreng.com/") == "tcreng.com"
        assert _clean_domain("https://sunrisetesting.vercel.app/") == "sunrisetesting.vercel.app"

    def test_zero_redundant_http_calls_during_benchmark_collection(self):
        """Verifies that BenchmarkNormalizer and collector perform no extra network calls."""
        report = _build_mock_synthesis_report("https://example.com")
        with patch("requests.get") as mock_req, patch("httpx.Client") as mock_httpx:
            pkg = BenchmarkNormalizer.normalize(
                url="https://example.com",
                report=report,
                engine_results={},
            )
            # Normalization must perform zero HTTP calls
            mock_req.assert_not_called()
            mock_httpx.assert_not_called()
            assert pkg.overall_health_score == 78

    def test_external_ai_enabled_normalization(self):
        """Verifies normalization when external AI is enabled."""
        report = _build_mock_synthesis_report("https://example.com")
        from rankintel.models.schema import ExternalAIObservation, ControlledVisibilityQuery, QueryInformationNeedCategory, ExternalVisibilityProvider
        report.unified_external_visibility = ExternalVisibilityEvidence(
            url="https://example.com",
            status=ExternalVisibilityStatus.SUCCESS,
            providers_evaluated=["mock"],
            queries_executed_count=3,
            successful_observations_count=3,
            target_domain_cited_count=2,
            target_domain_mention_count=3,
            total_external_citations_returned=5,
            observations=[
                ExternalAIObservation(
                    observation_id="obs-1",
                    provider=ExternalVisibilityProvider.MOCK,
                    query=ControlledVisibilityQuery(
                        query_id="q-1",
                        query_text="sample",
                        category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
                        target_domain="example.com",
                        target_url="https://example.com",
                    ),
                    target_domain="example.com",
                    target_url="https://example.com",
                    timestamp="2026-10-04T12:00:00",
                    status=ExternalVisibilityStatus.SUCCESS,
                    target_domain_cited=True,
                    target_domain_citations_count=1,
                    citations=[],
                )
            ],
            facts=["3 provider observations completed."],
        )
        pkg = BenchmarkNormalizer.normalize(
            url="https://example.com",
            report=report,
            engine_results={},
        )
        assert pkg.external_ai.status == BenchmarkDimensionStatus.AVAILABLE
        assert pkg.external_ai.providers_evaluated == ["mock"]
        assert pkg.external_ai.queries_executed_count == 3
        assert pkg.external_ai.target_domain_cited_count == 2
        assert pkg.external_ai.target_domain_mentioned_count == 3

    def test_collector_mock_site_worker(self, tmp_path):
        """Tests the execution of _execute_site_worker with mocked pipeline."""
        from rankintel.benchmark.collector import _execute_site_worker

        mock_report = _build_mock_synthesis_report("https://example.com")
        site_def = {"name": "Example", "domain": "example.com", "url": "https://example.com", "role": "competitor"}

        with patch("rankintel.benchmark.collector.EvidenceCollector") as mock_ec_cls, \
             patch("rankintel.benchmark.collector.IntelligenceSynthesizer") as mock_syn_cls:
            mock_ec = MagicMock()
            mock_ec.collect.return_value = {}
            mock_ec_cls.return_value = mock_ec

            mock_syn = MagicMock()
            mock_syn.synthesize.return_value = mock_report
            mock_syn_cls.return_value = mock_syn

            res = _execute_site_worker(
                site_info=site_def,
                audits_dir=str(tmp_path / "audits"),
                packages_dir=str(tmp_path / "packages"),
                external_ai=False,
            )

            assert res["domain"] == "example.com"
            assert res["collection_status"] == "SUCCESS"
            assert res["overall_health_score"] == 78
            # File persistence check
            pkg_file = tmp_path / "packages" / "example.com.json"
            assert pkg_file.exists()
            loaded_pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            assert loaded_pkg["domain"] == "example.com"
            assert loaded_pkg["overall_health_score"] == 78

