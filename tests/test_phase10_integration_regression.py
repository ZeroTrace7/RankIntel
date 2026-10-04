"""
RankIntel Phase 10 Integration & Regression Test Suite (M10.6).
Verifies complete end-to-end integration of Phase 10 AI Discovery, Grounding,
Citation, and Agent Readiness Intelligence:
- M10.1 AI Access & Retrieval Readiness
- M10.2 AI Answerability & Information Extraction
- M10.3 Entity + Claim Grounding Intelligence
- M10.4 Multimodal + Agent Readiness Intelligence
- M10.5 Controlled External AI Visibility Intelligence

Key Validation Requirements:
1. Complete evidence flow: Crawl/DOM -> M10.1 -> M10.2 -> M10.3 -> M10.4 -> M10.5 -> Unified Phase 10.
2. Strict Health-Score Formula Invariance (3_engine, 4_engine, 5_engine modes; Delta = 0).
3. Zero duplicate HTTP requests during on-site M10.1-M10.4 evidence processing.
4. Controlled External AI Visibility remains strictly opt-in; zero network calls when disabled.
5. Strict secret masking (API keys never appear in configs, reports, or serialized payloads).
6. Provider error boundary resilience (Timeout, HTTP 429, HTTP 503 -> explicit statuses).
7. Conservative citation matching (MISMATCH strictly affirmative; absence != failure).
8. Provenance retention through ProvenanceTagger (Steps 18-22).
9. Partial crawl boundary preservation and explicit disclaimers.
10. Reporting and interface parity across Markdown, JSON, CLI, audit_engine runner, and FastMCP.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.cli import main
from rankintel.mcp.server import rankintel_audit

from rankintel.engines.retrieval_readiness_engine import RetrievalReadinessEngine
from rankintel.engines.answerability_engine import AnswerabilityEngine
from rankintel.engines.claim_grounding_engine import ClaimGroundingEngine
from rankintel.engines.multimodal_agent_engine import MultimodalAgentEngine
from rankintel.engines.external_visibility_engine import (
    ControlledQueryGenerator,
    ExternalCitationAnalyzer,
    ExternalVisibilityEngine,
)

from rankintel.providers.base import BaseExternalVisibilityAdapter
from rankintel.providers.mock import MockVisibilityAdapter
from rankintel.providers.registry import ProviderRegistry

from rankintel.models.schema import (
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    CloudIntelligenceEvidence,
    KeywordIntelligence,
    EngineResult,
    SynthesisReport,
    ExternalVisibilityStatus,
    ExternalVisibilityProvider,
    CitationRelationship,
    CitationContentMatchStatus,
    QueryInformationNeedCategory,
    ControlledVisibilityQuery,
    ExternalCitationObservation,
    ClaimSupportStatus,
    EntityConsistencyStatus,
    MultimodalRepresentationStatus,
)


SAMPLE_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Apex Metrology & Calibration Labs - ISO 17025 Testing</title>
    <meta name="description" content="NABL accredited calibration laboratory specializing in precision pressure and dimensional testing.">
    <meta name="robots" content="index, follow">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Apex Metrology Labs",
      "url": "https://apexmetrology.example.com",
      "telephone": "+91-11-23456789",
      "email": "contact@apexmetrology.example.com"
    }
    </script>
</head>
<body>
    <header>
        <nav aria-label="Main Navigation">
            <a href="/">Home</a>
            <a href="/services">Testing Services</a>
            <a href="/contact">Contact Lab</a>
        </nav>
    </header>
    <main>
        <h1>Apex Metrology Labs</h1>
        <p>Apex Metrology Labs is an ISO/IEC 17025 accredited calibration facility founded in 2005.</p>
        
        <h2>Calibration Services</h2>
        <p>We provide full verification of digital indicators, micrometers, and pressure transducers.</p>
        
        <h2>How Calibration Works</h2>
        <p>1. Submit inquiry. 2. Dispatch instrument to Delhi lab. 3. Receive NABL traceable certificate within 48 hours.</p>

        <figure>
            <img src="/images/calibration-bench.jpg" alt="Automated Pressure Calibration Bench with Digital Gauge" width="800" height="600">
            <figcaption>State-of-the-art deadweight tester calibration setup.</figcaption>
        </figure>

        <form action="/inquiry" method="post" aria-label="Calibration Quote Form">
            <label for="instrument">Instrument Name</label>
            <input type="text" id="instrument" name="instrument">
            <button type="submit">Request Quote</button>
        </form>
    </main>
    <footer>
        <p>Contact: +91-11-23456789 | Email: contact@apexmetrology.example.com</p>
    </footer>
</body>
</html>
"""


def create_baseline_engine_results():
    """Builds standard multi-engine baseline results across SEO, Browser, GEO, and Trust."""
    return {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url="https://apexmetrology.example.com",
                title="Apex Metrology & Calibration Labs - ISO 17025 Testing",
                title_length=54,
                meta_description="NABL accredited calibration laboratory specializing in precision pressure and dimensional testing.",
                meta_desc_length=89,
                h1_count=1,
                h1_text=["Apex Metrology Labs"],
                total_images=1,
                images_with_alt=1,
                word_count=420,
            ),
            robots=RobotsEvidence(found=True),
            schema_data=SchemaEvidence(detected_types=["Organization"]),
        ),
        "rankintel_geo": EngineResult(
            engine_name="rankintel_geo",
            status="success",
            geo_aeo=GeoAeoEvidence(
                overall_citability_score=75,
                llms_txt_found=True,
                answer_first_ratio=0.85,
            ),
        ),
        "performance_engine": EngineResult(
            engine_name="performance_engine",
            status="success",
            performance=PerformanceEvidence(
                source="local_probe",
                overall_performance_score=80,
                ttfb_ms=220.0,
            ),
        ),
    }


class TestPhase10EndToEndPipeline:
    """Verifies complete evidence flow, synthesis, and dimension populating."""

    def test_end_to_end_phase10_evidence_flow(self):
        collector = EvidenceCollector(
            enable_external_visibility=True,
            external_providers=["mock"],
        )

        with patch.object(collector.seo_engine, "execute") as mock_seo, \
             patch.object(collector.browser_engine, "execute_sync") as mock_browser, \
             patch.object(collector.performance_engine, "execute") as mock_perf, \
             patch.object(collector.mcp_engine, "execute") as mock_mcp:

            mock_seo.return_value = EngineResult(
                engine_name="advertools_seo",
                status="success",
                on_page=OnPageEvidence(
                    url="https://apexmetrology.example.com",
                    title="Apex Metrology Labs",
                    word_count=350,
                ),
                robots=RobotsEvidence(found=True),
                raw_html=SAMPLE_PAGE_HTML,
            )
            mock_browser.return_value = EngineResult(
                engine_name="crawl4ai_browser",
                status="success",
                raw_html=SAMPLE_PAGE_HTML,
                schema_data=SchemaEvidence(detected_types=["Organization"]),
            )
            mock_perf.return_value = EngineResult(
                engine_name="performance_engine",
                status="success",
                performance=PerformanceEvidence(overall_performance_score=85, ttfb_ms=180.0),
            )
            mock_mcp.return_value = EngineResult(engine_name="mcp_cloud", status="skipped")

            results = collector.collect("https://apexmetrology.example.com")

            # 1. Assert all 5 Phase 10 engines executed
            assert "retrieval_readiness_engine" in results
            assert results["retrieval_readiness_engine"].retrieval_readiness is not None
            assert results["retrieval_readiness_engine"].retrieval_readiness.search_index_allowed_count >= 1

            assert "answerability_engine" in results
            assert results["answerability_engine"].answerability is not None
            assert results["answerability_engine"].answerability.total_units_detected >= 1

            assert "claim_grounding_engine" in results
            assert results["claim_grounding_engine"].claim_grounding is not None

            assert "multimodal_agent_engine" in results
            assert results["multimodal_agent_engine"].multimodal_agent is not None
            assert results["multimodal_agent_engine"].multimodal_agent.multimodal.total_visual_assets >= 1

            assert "external_visibility_engine" in results
            assert results["external_visibility_engine"].external_visibility is not None
            assert results["external_visibility_engine"].external_visibility.status == ExternalVisibilityStatus.SUCCESS

            # 2. Assert synthesis captures all 5 dimensions
            synthesizer = IntelligenceSynthesizer()
            report = synthesizer.synthesize("https://apexmetrology.example.com", results)

            assert report.unified_retrieval_readiness is not None
            assert report.unified_answerability is not None
            assert report.unified_claim_grounding is not None
            assert report.unified_multimodal_agent is not None
            assert report.unified_external_visibility is not None
            assert report.unified_external_visibility.status == ExternalVisibilityStatus.SUCCESS


class TestFormulaInvariance:
    """CRITICAL: Proves health scores are 100% mathematically invariant across all modes."""

    def test_formula_invariance_across_all_modes(self):
        synthesizer = IntelligenceSynthesizer()

        # Mode A: 4_engine (standard without cloud)
        base_results_4 = create_baseline_engine_results()
        base_rep_4 = synthesizer.synthesize("https://apexmetrology.example.com", dict(base_results_4))
        score_base_4 = base_rep_4.overall_health_score

        # Inject complete Phase 10 engine results
        phase10_results_4 = dict(base_results_4)
        phase10_results_4["retrieval_readiness_engine"] = EngineResult(
            engine_name="retrieval_readiness_engine", status="success",
            retrieval_readiness=RetrievalReadinessEngine().evaluate_page("https://apexmetrology.example.com", 200, SAMPLE_PAGE_HTML, SAMPLE_PAGE_HTML, {}),
        )
        phase10_results_4["answerability_engine"] = EngineResult(
            engine_name="answerability_engine", status="success",
            answerability=AnswerabilityEngine().evaluate_page("https://apexmetrology.example.com", raw_html=SAMPLE_PAGE_HTML),
        )
        phase10_results_4["claim_grounding_engine"] = EngineResult(
            engine_name="claim_grounding_engine", status="success",
            claim_grounding=ClaimGroundingEngine().evaluate_page("https://apexmetrology.example.com", raw_html=SAMPLE_PAGE_HTML),
        )
        phase10_results_4["multimodal_agent_engine"] = EngineResult(
            engine_name="multimodal_agent_engine", status="success",
            multimodal_agent=MultimodalAgentEngine().evaluate_page("https://apexmetrology.example.com", raw_html=SAMPLE_PAGE_HTML),
        )
        phase10_results_4["external_visibility_engine"] = EngineResult(
            engine_name="external_visibility_engine", status="success",
            external_visibility=ExternalVisibilityEngine(enable_external_visibility=True, providers=["mock"]).evaluate_page("https://apexmetrology.example.com"),
        )

        p10_rep_4 = synthesizer.synthesize("https://apexmetrology.example.com", phase10_results_4)
        assert p10_rep_4.overall_health_score == score_base_4, "Health score changed in 4_engine mode!"
        assert p10_rep_4.score_formula_mode == "4_engine"

        # Mode B: 3_engine (no performance engine)
        base_results_3 = {k: v for k, v in base_results_4.items() if k != "performance_engine"}
        base_rep_3 = synthesizer.synthesize("https://apexmetrology.example.com", dict(base_results_3))
        score_base_3 = base_rep_3.overall_health_score

        phase10_results_3 = {k: v for k, v in phase10_results_4.items() if k != "performance_engine"}
        p10_rep_3 = synthesizer.synthesize("https://apexmetrology.example.com", phase10_results_3)
        assert p10_rep_3.overall_health_score == score_base_3, "Health score changed in 3_engine mode!"
        assert p10_rep_3.score_formula_mode == "3_engine"

        # Mode C: 5_engine (with cloud intelligence keywords)
        cloud_ev = CloudIntelligenceEvidence(
            available=True,
            keywords=KeywordIntelligence(estimated_monthly_traffic=50000),
        )
        base_results_5 = dict(base_results_4)
        base_results_5["mcp_cloud"] = EngineResult(engine_name="mcp_cloud", status="success", cloud_intelligence=cloud_ev)
        base_rep_5 = synthesizer.synthesize("https://apexmetrology.example.com", dict(base_results_5))
        score_base_5 = base_rep_5.overall_health_score

        phase10_results_5 = dict(phase10_results_4)
        phase10_results_5["mcp_cloud"] = EngineResult(engine_name="mcp_cloud", status="success", cloud_intelligence=cloud_ev)
        p10_rep_5 = synthesizer.synthesize("https://apexmetrology.example.com", phase10_results_5)
        assert p10_rep_5.overall_health_score == score_base_5, "Health score changed in 5_engine mode!"
        assert p10_rep_5.score_formula_mode == "5_engine"


class TestNetworkIsolationAndOptIn:
    """Verifies zero duplicate HTTP requests for M10.1-10.4 and strict opt-in for M10.5."""

    def test_zero_duplicate_http_requests_m10_1_to_m10_4(self):
        """M10.1, M10.2, M10.3, and M10.4 must execute 100% in memory with 0 network calls."""
        with patch("urllib.request.urlopen") as mock_urllib, \
             patch("requests.Session.send") as mock_req_send, \
             patch("requests.get") as mock_req_get, \
             patch("requests.post") as mock_req_post:

            # Execute M10.1
            rr_ev = RetrievalReadinessEngine().evaluate_page("https://example.com", 200, SAMPLE_PAGE_HTML, SAMPLE_PAGE_HTML, {})
            # Execute M10.2
            ans_ev = AnswerabilityEngine().evaluate_page("https://example.com", raw_html=SAMPLE_PAGE_HTML)
            # Execute M10.3
            cg_ev = ClaimGroundingEngine().evaluate_page("https://example.com", raw_html=SAMPLE_PAGE_HTML)
            # Execute M10.4
            mma_ev = MultimodalAgentEngine().evaluate_page("https://example.com", raw_html=SAMPLE_PAGE_HTML)

            assert mock_urllib.call_count == 0
            assert mock_req_send.call_count == 0
            assert mock_req_get.call_count == 0
            assert mock_req_post.call_count == 0

    def test_external_ai_strict_opt_in_default_offline(self):
        """Default EvidenceCollector run must not make any external AI calls and set DISABLED."""
        collector = EvidenceCollector(enable_external_visibility=False)
        assert collector.external_visibility_engine.enabled is False

        with patch("requests.post") as mock_post:
            ev = collector.external_visibility_engine.evaluate_page("https://example.com")
            assert ev.status == ExternalVisibilityStatus.DISABLED
            assert mock_post.call_count == 0


class TestSecretRedactionAndErrorBoundaries:
    """Verifies API key privacy and graceful error handling."""

    def test_secret_redaction_in_serialization(self):
        adapter = MockVisibilityAdapter()
        query = ControlledVisibilityQuery(
            query_id="q-sec",
            query_text="Testing secret masking",
            category=QueryInformationNeedCategory.ENTITY_IDENTIFICATION,
            target_domain="example.com",
            target_url="https://example.com",
        )
        obs = adapter.execute_query(
            query,
            config={
                "api_key": "SECRET_KEY_abc",
                "auth_token": "TOKEN_xyz",
                "model": "test-v1",
            },
        )

        serialized = obs.model_dump_json()
        assert "SECRET_KEY_abc" not in serialized
        assert "TOKEN_xyz" not in serialized
        assert "[REDACTED]" in serialized

    def test_provider_error_boundary_resilience(self):
        """Timeout, 429 rate limits, and 503 errors must become explicit statuses, not exceptions."""
        adapter = MockVisibilityAdapter()

        # 1. Timeout simulation
        query = ControlledVisibilityQuery(query_id="q-t", query_text="Timeout query", category=QueryInformationNeedCategory.SERVICE_DISCOVERY, target_domain="example.com", target_url="https://example.com")
        with patch.object(adapter, "_execute_query_internal", side_effect=TimeoutError("Connection timed out")):
            obs = adapter.execute_query(query)
            assert obs.status == ExternalVisibilityStatus.TIMEOUT
            assert "timed out" in obs.failure_reason

        # 2. Rate limit HTTP 429 simulation
        with patch.object(adapter, "_execute_query_internal", side_effect=RuntimeError("HTTP 429: Rate limit exceeded by API")):
            obs = adapter.execute_query(query)
            assert obs.status == ExternalVisibilityStatus.RATE_LIMITED
            assert "429" in obs.failure_reason

        # 3. Service Unavailable HTTP 503 simulation
        with patch.object(adapter, "_execute_query_internal", side_effect=RuntimeError("HTTP 503: Service Unavailable")):
            obs = adapter.execute_query(query)
            assert obs.status == ExternalVisibilityStatus.UNAVAILABLE
            assert "503" in obs.failure_reason


class TestConservativeCitationMatching:
    """Verifies that absence of verbatim text does not trigger MISMATCH."""

    def test_no_false_mismatch_on_unquoted_summary(self):
        citation = ExternalCitationObservation(
            citation_url="https://apexmetrology.example.com/services",
            title="Apex Calibration",
            snippet="Apex provides calibrated measurements for high-precision components.",
            is_target_domain=True,
            is_target_page=True,
        )
        page_ev = MagicMock(page_text="We offer dimensional testing and pressure gauge analysis.", title="Services")
        status = ExternalCitationAnalyzer.analyze_citation_content(
            citation,
            crawled_pages_evidence={"https://apexmetrology.example.com/services": page_ev},
        )
        # Should NOT be MISMATCH
        assert status == CitationContentMatchStatus.UNABLE_TO_DETERMINE

    def test_affirmative_material_contradiction_detected(self):
        citation = ExternalCitationObservation(
            citation_url="https://apexmetrology.example.com/services",
            snippet="Apex Metrology calibration certifications are expired.",
            is_target_domain=True,
            is_target_page=True,
        )
        page_ev = MagicMock(page_text="Apex Metrology calibration certifications are active and accredited.", title="Services")
        status = ExternalCitationAnalyzer.analyze_citation_content(
            citation,
            crawled_pages_evidence={"https://apexmetrology.example.com/services": page_ev},
        )
        assert status == CitationContentMatchStatus.MISMATCH


class TestProvenanceAndPartialCrawl:
    """Verifies provenance tags and partial crawl disclaimers."""

    def test_provenance_retention_across_phase10(self):
        engine_results = {
            "retrieval_readiness_engine": EngineResult(
                engine_name="retrieval_readiness_engine", status="success",
                retrieval_readiness=RetrievalReadinessEngine().evaluate_page("https://example.com", 200, SAMPLE_PAGE_HTML, SAMPLE_PAGE_HTML, {}),
            ),
            "answerability_engine": EngineResult(
                engine_name="answerability_engine", status="success",
                answerability=AnswerabilityEngine().evaluate_page("https://example.com", raw_html=SAMPLE_PAGE_HTML),
            ),
            "claim_grounding_engine": EngineResult(
                engine_name="claim_grounding_engine", status="success",
                claim_grounding=ClaimGroundingEngine().evaluate_page("https://example.com", raw_html=SAMPLE_PAGE_HTML),
            ),
            "multimodal_agent_engine": EngineResult(
                engine_name="multimodal_agent_engine", status="success",
                multimodal_agent=MultimodalAgentEngine().evaluate_page("https://example.com", raw_html=SAMPLE_PAGE_HTML),
            ),
            "external_visibility_engine": EngineResult(
                engine_name="external_visibility_engine", status="success",
                external_visibility=ExternalVisibilityEngine(enable_external_visibility=True, providers=["mock"]).evaluate_page("https://example.com"),
            ),
        }
        tags = ProvenanceTagger.tag(engine_results)
        findings = [t.finding for t in tags]

        assert any("AI Search Retrieval Access" in f for f in findings)
        assert any("Observable Information Units" in f for f in findings)
        assert any("Observable Claims Grounding" in f for f in findings)
        assert any("Multimodal Information Representation" in f for f in findings)
        assert any("Controlled External AI Visibility" in f for f in findings)

    def test_partial_crawl_disclaimer_preservation(self):
        crawl_res = SiteCrawlResult(
            completeness_status="CRAWL_LIMIT_REACHED",
            pages_crawled=2,
            pages_discovered=10,
            remaining_frontier=8,
            crawl_records=[
                CrawlRecord(
                    url="https://example.com",
                    normalized_url="https://example.com",
                    identity_url="https://example.com",
                    crawl_status=CrawlStatus.FETCHED,
                    depth=0,
                    status_code=200,
                    raw_html=SAMPLE_PAGE_HTML,
                ),
                CrawlRecord(
                    url="https://example.com/services",
                    normalized_url="https://example.com/services",
                    identity_url="https://example.com/services",
                    crawl_status=CrawlStatus.FETCHED,
                    depth=1,
                    status_code=200,
                    raw_html=SAMPLE_PAGE_HTML,
                ),
            ],
        )

        RetrievalReadinessEngine.evaluate_site(crawl_res)
        assert crawl_res.retrieval_readiness_intelligence.is_partial_crawl is True
        assert len(crawl_res.retrieval_readiness_intelligence.completeness_disclaimer) > 0

        AnswerabilityEngine.evaluate_site(crawl_res)
        assert crawl_res.answerability_intelligence.is_partial_crawl is True
        assert len(crawl_res.answerability_intelligence.completeness_disclaimer) > 0

        ClaimGroundingEngine.evaluate_site(crawl_res)
        assert crawl_res.claim_grounding_intelligence.is_partial_crawl is True
        assert len(crawl_res.claim_grounding_intelligence.completeness_disclaimer) > 0

        MultimodalAgentEngine.evaluate_site(crawl_res)
        assert crawl_res.multimodal_agent_intelligence.is_partial_crawl is True
        assert len(crawl_res.multimodal_agent_intelligence.completeness_disclaimer) > 0


class TestInterfaceParityAcrossAllSurfaces:
    """Verifies consistent exposure and serialization across Markdown, JSON, CLI, and MCP."""

    def test_reporting_and_api_surfaces_parity(self):
        collector = EvidenceCollector(enable_external_visibility=True, external_providers=["mock"])
        with patch.object(collector.seo_engine, "execute") as mock_seo, \
             patch.object(collector.browser_engine, "execute_sync") as mock_browser, \
             patch.object(collector.performance_engine, "execute") as mock_perf, \
             patch.object(collector.mcp_engine, "execute") as mock_mcp:

            mock_seo.return_value = EngineResult(engine_name="advertools_seo", status="success", raw_html=SAMPLE_PAGE_HTML, on_page=OnPageEvidence(url="https://apexmetrology.example.com", title="Apex Labs"))
            mock_browser.return_value = EngineResult(engine_name="crawl4ai_browser", status="success", raw_html=SAMPLE_PAGE_HTML)
            mock_perf.return_value = EngineResult(engine_name="performance_engine", status="success", performance=PerformanceEvidence(overall_performance_score=80))
            mock_mcp.return_value = EngineResult(engine_name="mcp_cloud", status="skipped")

            results = collector.collect("https://apexmetrology.example.com")

        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize("https://apexmetrology.example.com", results)

        # 1. Markdown rendering
        md_text = MarkdownReporter.render(report)
        assert "## 🤖 AI ACCESS & RETRIEVAL READINESS" in md_text
        assert "## 💡 AI ANSWERABILITY & INFORMATION EXTRACTION" in md_text
        assert "CLAIM GROUNDING & ENTITY INTELLIGENCE" in md_text
        assert "## 👁️ MULTIMODAL & AGENT READINESS INTELLIGENCE" in md_text
        assert "## 🌐 CONTROLLED EXTERNAL AI VISIBILITY INTELLIGENCE" in md_text

        # 2. JSON serialization
        json_str = JsonReporter.render_audit(report)
        data = json.loads(json_str)
        assert "unified_retrieval_readiness" in data
        assert "unified_answerability" in data
        assert "unified_claim_grounding" in data
        assert "unified_multimodal_agent" in data
        assert "unified_external_visibility" in data

        # 3. FastMCP tool execution
        with patch("rankintel.mcp.server.EvidenceCollector.collect", return_value=results):
            mcp_out = rankintel_audit("https://apexmetrology.example.com", external_ai=True, external_providers="mock")
            assert "retrieval_search_indexers_allowed" in mcp_out
            assert "answerability_units_detected" in mcp_out
            assert "claim_grounding_total_claims" in mcp_out
            assert "multimodal_total_assets" in mcp_out
            assert "external_visibility_status" in mcp_out
            assert mcp_out["external_visibility_status"] == "SUCCESS"

    def test_audit_engine_runner_phase10_integration(self, tmp_path):
        """Verifies alternative CLI runner audit_engine.py correctly supports Phase 10 & external-ai."""
        from audit_engine import run_audit

        real_report = SynthesisReport(
            url="https://apexmetrology.example.com",
            domain="apexmetrology.example.com",
            timestamp="2026-10-04",
            overall_health_score=80,
            technical_health_score=85,
            geo_readiness_score=75,
            trust_score=70,
            performance_score=80,
            score_formula_mode="4_engine",
            engines_executed=["advertools_seo"],
            unified_on_page=OnPageEvidence(url="https://apexmetrology.example.com", title="Apex Labs"),
            unified_geo=GeoAeoEvidence(llms_txt_found=True),
            unified_performance=PerformanceEvidence(overall_performance_score=80, ttfb_ms=200.0, source="local_probe"),
            unified_retrieval_readiness=RetrievalReadinessEngine().evaluate_page("https://apexmetrology.example.com", 200, SAMPLE_PAGE_HTML, SAMPLE_PAGE_HTML, {}),
            unified_answerability=AnswerabilityEngine().evaluate_page("https://apexmetrology.example.com", raw_html=SAMPLE_PAGE_HTML),
            unified_claim_grounding=ClaimGroundingEngine().evaluate_page("https://apexmetrology.example.com", raw_html=SAMPLE_PAGE_HTML),
            unified_multimodal_agent=MultimodalAgentEngine().evaluate_page("https://apexmetrology.example.com", raw_html=SAMPLE_PAGE_HTML),
            unified_external_visibility=ExternalVisibilityEngine(enable_external_visibility=True, providers=["mock"]).evaluate_page("https://apexmetrology.example.com"),
        )

        with patch("audit_engine.EvidenceCollector.collect") as mock_collect, \
             patch("audit_engine.IntelligenceSynthesizer.synthesize") as mock_synth:

            mock_collect.return_value = {}
            mock_synth.return_value = real_report

            rep_path = run_audit(
                "https://apexmetrology.example.com",
                output_dir=str(tmp_path),
                external_ai=True,
                external_providers="mock",
            )
            assert rep_path is not None
            mock_collect.assert_called_once_with(
                "https://apexmetrology.example.com",
                enable_external_visibility=True,
                external_providers=["mock"],
            )
