"""
Unit Tests for External Visibility Intelligence Engine (Phase 10.5).
"""
import pytest
from rankintel.models.schema import (
    ExternalVisibilityProvider,
    ExternalVisibilityProviderType,
    ExternalVisibilityStatus,
    CitationRelationship,
    CitationContentMatchStatus,
    QueryInformationNeedCategory,
    ControlledVisibilityQuery,
    ExternalCitationObservation,
    ExternalMentionObservation,
    ExternalAnswerEvidence,
    ExternalAIObservation,
    ExternalVisibilityEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    EntitySignalType,
    PageTopicIntelligence,
    TopicEvidence,
    AnswerabilityEvidence,
    AnswerableInformationUnit,
    AnswerableUnitType,
    ClaimGroundingEvidence,
    ClaimEvidence,
    OnPageEvidence,
    EngineResult,
)
from rankintel.providers.base import BaseExternalVisibilityAdapter
from rankintel.providers.mock import MockVisibilityAdapter
from rankintel.providers.registry import ProviderRegistry
from rankintel.engines.external_visibility_engine import (
    ControlledQueryGenerator,
    ExternalCitationAnalyzer,
    ExternalVisibilityEngine,
)
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.evidence.conflicts import ConflictDetector


class TestProviderAdapterFoundation:
    """Tests adapter normalization, secret masking, and error handling."""

    def test_mock_adapter_target_cited(self):
        adapter = MockVisibilityAdapter(mode="target_cited")
        query = ControlledVisibilityQuery(
            query_id="q-01",
            query_text="Who is Sunrise Testing?",
            category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
            target_domain="sunrisetesting.vercel.app",
            target_url="https://sunrisetesting.vercel.app",
            derived_from_entity="Sunrise Testing",
        )
        obs = adapter.execute_query(query)

        assert obs.status == ExternalVisibilityStatus.SUCCESS
        assert obs.provider == ExternalVisibilityProvider.MOCK
        assert obs.provider_type == ExternalVisibilityProviderType.MOCK_PROVIDER
        assert obs.target_domain_cited is True
        assert obs.target_page_cited is True
        assert obs.target_domain_citations_count == 2
        assert len(obs.citations) == 3
        assert obs.mention_observation is not None
        assert obs.mention_observation.target_mentioned is True
        assert obs.latency_ms is not None
        assert obs.latency_ms >= 0

    def test_mock_adapter_no_target_citation(self):
        adapter = MockVisibilityAdapter(mode="no_target_citation")
        query = ControlledVisibilityQuery(
            query_id="q-02",
            query_text="Testing standards",
            category=QueryInformationNeedCategory.SERVICE_DISCOVERY,
            target_domain="sunrisetesting.vercel.app",
            target_url="https://sunrisetesting.vercel.app",
        )
        obs = adapter.execute_query(query)

        assert obs.status == ExternalVisibilityStatus.SUCCESS
        assert obs.target_domain_cited is False
        assert obs.target_page_cited is False
        assert obs.target_domain_citations_count == 0
        assert len(obs.citations) == 2
        for cit in obs.citations:
            assert cit.relationship == CitationRelationship.NO_TARGET_CITATION

    def test_adapter_unavailable_credentials(self):
        adapter = MockVisibilityAdapter(available=False, unavailable_reason="No API key set")
        query = ControlledVisibilityQuery(
            query_id="q-03",
            query_text="Sample query",
            category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
            target_domain="example.com",
            target_url="https://example.com",
        )
        obs = adapter.execute_query(query)

        assert obs.status == ExternalVisibilityStatus.UNAVAILABLE
        assert "No API key set" in obs.failure_reason
        assert obs.answer_evidence is None

    def test_adapter_timeout_handling(self):
        adapter = MockVisibilityAdapter(mode="timeout")
        query = ControlledVisibilityQuery(
            query_id="q-04",
            query_text="Sample query",
            category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
            target_domain="example.com",
            target_url="https://example.com",
        )
        obs = adapter.execute_query(query)

        assert obs.status == ExternalVisibilityStatus.TIMEOUT
        assert "timed out" in obs.failure_reason.lower()

    def test_adapter_rate_limit_handling(self):
        adapter = MockVisibilityAdapter(mode="rate_limit")
        query = ControlledVisibilityQuery(
            query_id="q-05",
            query_text="Sample query",
            category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
            target_domain="example.com",
            target_url="https://example.com",
        )
        obs = adapter.execute_query(query)

        assert obs.status == ExternalVisibilityStatus.RATE_LIMITED
        assert "429" in obs.failure_reason or "rate limit" in obs.failure_reason.lower()

    def test_secret_redaction(self):
        adapter = MockVisibilityAdapter()
        query = ControlledVisibilityQuery(
            query_id="q-06",
            query_text="Secret test",
            category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
            target_domain="example.com",
            target_url="https://example.com",
        )
        config_with_secret = {
            "api_key": "sk-secret-key-123",
            "auth_token": "token-xyz",
            "temperature": 0.2,
        }
        obs = adapter.execute_query(query, config=config_with_secret)

        assert obs.request_config["api_key"] == "[REDACTED]"
        assert obs.request_config["auth_token"] == "[REDACTED]"
        assert obs.request_config["temperature"] == 0.2


class TestControlledQueryGenerator:
    """Tests deterministic query generation across 10 categories with budget limits."""

    def test_deterministic_query_generation(self):
        ent_ev = EntityEvidence(
            detected_entities=[
                DetectedEntity(
                    name="Sunrise Testing Laboratory",
                    entity_type=EntityType.ORGANIZATION,
                    source=EntitySource.VISIBLE_HTML,
                    signal_type=EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL,
                )
            ]
        )
        top_ev = PageTopicIntelligence(
            topics=[
                TopicEvidence(topic_name="BIS Certification Testing", normalized_name="bis certification testing"),
                TopicEvidence(topic_name="RoHS Chemical Analysis", normalized_name="rohs chemical analysis"),
            ]
        )
        ans_ev = AnswerabilityEvidence(
            units=[
                AnswerableInformationUnit(
                    unit_id="u-01",
                    unit_type=AnswerableUnitType.SERVICE_DESCRIPTION,
                    snippet="We provide BIS product testing.",
                    content_location="body",
                    structural_type="paragraph",
                    section_heading="BIS Testing Overview",
                ),
                AnswerableInformationUnit(
                    unit_id="u-02",
                    unit_type=AnswerableUnitType.PROCEDURE_STEPS,
                    snippet="Step 1: submit sample.",
                    content_location="body",
                    structural_type="ordered_list",
                    section_heading="Testing Procedure",
                ),
            ]
        )
        cg_ev = ClaimGroundingEvidence(
            claims=[
                ClaimEvidence(
                    claim_id="clm-01",
                    claim_text="Accredited for NABL ISO/IEC 17025:2017",
                )
            ]
        )

        queries = ControlledQueryGenerator.generate_queries(
            target_url="https://sunrisetesting.vercel.app",
            domain="sunrisetesting.vercel.app",
            entity_evidence=ent_ev,
            topic_evidence=top_ev,
            answerability_evidence=ans_ev,
            claim_evidence=cg_ev,
            max_queries=10,
            trials_count=1,
        )

        assert len(queries) == 10
        categories = [q.category for q in queries]
        assert QueryInformationNeedCategory.ENTITY_IDENTIFICATION in categories
        assert QueryInformationNeedCategory.SERVICE_DISCOVERY in categories
        assert QueryInformationNeedCategory.SERVICE_EXPLANATION in categories
        assert QueryInformationNeedCategory.CERTIFICATION_STANDARD in categories
        assert QueryInformationNeedCategory.LOCATION_CONTACT in categories
        assert QueryInformationNeedCategory.PROCEDURE_HOWTO in categories
        assert QueryInformationNeedCategory.REQUIREMENT_ELIGIBILITY in categories
        assert QueryInformationNeedCategory.COMPARISON_DECISION in categories
        assert QueryInformationNeedCategory.TOPIC_SPECIFIC_PHASE9 in categories
        assert QueryInformationNeedCategory.CLAIM_SPECIFIC_M10_3 in categories

        # Verify exact derivations
        q_entity = next(q for q in queries if q.category == QueryInformationNeedCategory.ENTITY_IDENTIFICATION)
        assert "Sunrise Testing Laboratory" in q_entity.query_text

        q_claim = next(q for q in queries if q.category == QueryInformationNeedCategory.CLAIM_SPECIFIC_M10_3)
        assert q_claim.derived_from_claim_id == "clm-01"

    def test_query_budget_limit(self):
        queries = ControlledQueryGenerator.generate_queries(
            target_url="https://example.com",
            domain="example.com",
            max_queries=4,
            trials_count=1,
        )
        assert len(queries) == 4

    def test_repeated_measurement_trials(self):
        queries = ControlledQueryGenerator.generate_queries(
            target_url="https://example.com",
            domain="example.com",
            max_queries=3,
            trials_count=2,
        )
        assert len(queries) == 6
        assert queries[0].trial_index == 1
        assert queries[1].trial_index == 2


class TestCitationAnalyzer:
    """Tests conservative citation content comparison."""

    def test_content_match(self):
        cit = ExternalCitationObservation(
            citation_url="https://sunrisetesting.vercel.app/services",
            snippet="Sunrise Testing provides comprehensive BIS certification and NABL laboratory testing.",
            is_target_domain=True,
            is_target_page=False,
        )
        on_page = OnPageEvidence(
            url="https://sunrisetesting.vercel.app/services",
            title="Sunrise Testing Laboratory BIS Certification Testing Services",
        )
        res = ExternalCitationAnalyzer.analyze_citation_content(
            cit,
            crawled_pages_evidence={"https://sunrisetesting.vercel.app/services": on_page},
        )
        assert res in (CitationContentMatchStatus.MATCHES_PAGE_EVIDENCE, CitationContentMatchStatus.PARTIALLY_MATCHES)

    def test_conservative_mismatch_only_on_material_contradiction(self):
        # Case A: Material contradiction (e.g. "expired" vs "active")
        cit = ExternalCitationObservation(
            citation_url="https://sunrisetesting.vercel.app/cert",
            snippet="The BIS testing license is expired and prohibited from commercial reporting.",
            is_target_domain=True,
        )
        on_page = OnPageEvidence(
            url="https://sunrisetesting.vercel.app/cert",
            title="Active BIS license and certified commercial operations permitted.",
        )
        res = ExternalCitationAnalyzer.analyze_citation_content(
            cit,
            crawled_pages_evidence={"https://sunrisetesting.vercel.app/cert": on_page},
        )
        assert res == CitationContentMatchStatus.MISMATCH

        # Case B: Words simply not found does NOT equal MISMATCH (per user feedback #5)
        cit_absent = ExternalCitationObservation(
            citation_url="https://sunrisetesting.vercel.app/cert",
            snippet="The laboratory was founded by chemical engineers in central Bangalore.",
            is_target_domain=True,
        )
        res_absent = ExternalCitationAnalyzer.analyze_citation_content(
            cit_absent,
            crawled_pages_evidence={"https://sunrisetesting.vercel.app/cert": on_page},
        )
        assert res_absent == CitationContentMatchStatus.UNABLE_TO_DETERMINE


class TestEngineAndProvenance:
    """Tests ExternalVisibilityEngine, ProvenanceTagger, and ConflictDetector."""

    def test_engine_disabled_by_default(self):
        engine = ExternalVisibilityEngine(enable_external_visibility=False)
        ev = engine.evaluate_page("https://sunrisetesting.vercel.app")
        assert ev.status == ExternalVisibilityStatus.DISABLED
        assert ev.queries_executed_count == 0

    def test_engine_opt_in_execution(self):
        engine = ExternalVisibilityEngine(
            enable_external_visibility=True,
            providers=["mock"],
            max_queries_per_site=5,
        )
        ev = engine.evaluate_page("https://sunrisetesting.vercel.app")
        assert ev.status == ExternalVisibilityStatus.SUCCESS
        assert ev.queries_executed_count == 5
        assert ev.successful_observations_count == 5
        assert ev.target_domain_cited_count > 0
        assert len(ev.evidence_linkages) == 5

    def test_provenance_step_22(self):
        tagger = ProvenanceTagger()
        ev = ExternalVisibilityEvidence(
            status=ExternalVisibilityStatus.SUCCESS,
            providers_evaluated=["gemini"],
            successful_observations_count=5,
            target_domain_mention_count=4,
            target_domain_cited_count=3,
            total_external_citations_returned=10,
            observations=[
                ExternalAIObservation(
                    observation_id="obs-01",
                    provider=ExternalVisibilityProvider.GEMINI,
                    model_version="gemini-2.5-flash",
                    query=ControlledVisibilityQuery(
                        query_id="q-01",
                        query_text="Who is Sunrise?",
                        category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
                        target_domain="sunrisetesting.vercel.app",
                        target_url="https://sunrisetesting.vercel.app",
                    ),
                    target_domain="sunrisetesting.vercel.app",
                    target_url="https://sunrisetesting.vercel.app",
                    timestamp="2026-10-04T00:00:00Z",
                    status=ExternalVisibilityStatus.SUCCESS,
                    target_domain_cited=True,
                )
            ]
        )
        engine_results = {
            "external_visibility_engine": EngineResult(
                engine_name="external_visibility_engine",
                status="success",
                external_visibility=ev,
            )
        }
        tags = tagger.tag(engine_results)
        ext_tags = [t for t in tags if t.engine == "external_visibility_engine"]
        assert len(ext_tags) == 2
        assert "Controlled External AI Visibility" in ext_tags[0].finding
        assert "Observable Query [gemini]" in ext_tags[1].finding

    def test_conflict_detection_step_12(self):
        detector = ConflictDetector()
        obs = ExternalAIObservation(
            observation_id="obs-01",
            provider=ExternalVisibilityProvider.GEMINI,
            query=ControlledVisibilityQuery(
                query_id="q-01",
                query_text="BIS License",
                category=QueryInformationNeedCategory.CERTIFICATION_STANDARD,
                target_domain="sunrisetesting.vercel.app",
                target_url="https://sunrisetesting.vercel.app",
            ),
            target_domain="sunrisetesting.vercel.app",
            target_url="https://sunrisetesting.vercel.app",
            timestamp="2026-10-04T00:00:00Z",
            status=ExternalVisibilityStatus.SUCCESS,
            citations=[
                ExternalCitationObservation(
                    citation_url="https://sunrisetesting.vercel.app/bis",
                    snippet="Testing license is cancelled and invalid.",
                    content_match_status=CitationContentMatchStatus.MISMATCH,
                )
            ]
        )
        ev = ExternalVisibilityEvidence(
            status=ExternalVisibilityStatus.SUCCESS,
            observations=[obs],
        )
        conflicts = detector.detect({
            "external_visibility_engine": EngineResult(
                engine_name="external_visibility_engine",
                status="success",
                external_visibility=ev,
            )
        })
        mismatch_conflicts = [c for c in conflicts if c.category == "EXTERNAL_CITATION_MATERIAL_MISMATCH"]
        assert len(mismatch_conflicts) == 1
        assert "External Citation Material Contradiction" in mismatch_conflicts[0].feature
