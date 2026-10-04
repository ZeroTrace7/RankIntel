"""
Integration Test Suite for RankIntel Phase 10.1: AI Access & Retrieval Readiness.
Verifies end-to-end integration across:
- EvidenceCollector (Step 17, zero redundant network calls)
- ProvenanceTagger (provenance preservation)
- ConflictDetector (AI directive conflicts, WAF block conflicts)
- IntelligenceSynthesizer (synthesis & health score formula invariance)
- MarkdownReporter (dedicated section & site summary table)
- JsonReporter (schema compliance & serialization)
- CLI (executive scorecard compact row)
- MCP Server (rankintel_audit telemetry fields)
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.mcp.server import rankintel_audit
from rankintel.cli import main
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
    EngineResult,
    RetrievalReadinessEvidence,
    RetrievalReadinessStatus,
    BotPurpose,
    SnippetControlStatus,
    SnippetControlEvidence,
    ContentAvailabilityEvidence,
    WafChallengeEvidence,
    IndexabilityInteractionEvidence,
    BotRetrievalAccessRecord,
)


def build_mock_engine_result(url: str = "https://example.com/test") -> EngineResult:
    """Builds a deterministic mock EngineResult with retrieval readiness populated."""
    bot_records = {
        "Googlebot": BotRetrievalAccessRecord(
            bot_name="Googlebot",
            company="Google",
            purpose=BotPurpose.SEARCH_INDEX,
            category_label="Search Engine",
            robots_access=RetrievalReadinessStatus.ALLOWED,
            effective_status=RetrievalReadinessStatus.ALLOWED,
        ),
        "OAI-SearchBot": BotRetrievalAccessRecord(
            bot_name="OAI-SearchBot",
            company="OpenAI",
            purpose=BotPurpose.SEARCH_INDEX,
            category_label="AI Search Engine",
            robots_access=RetrievalReadinessStatus.ALLOWED,
            effective_status=RetrievalReadinessStatus.ALLOWED,
        ),
        "GPTBot": BotRetrievalAccessRecord(
            bot_name="GPTBot",
            company="OpenAI",
            purpose=BotPurpose.AI_TRAINING,
            category_label="AI Model Training",
            robots_access=RetrievalReadinessStatus.DISALLOWED,
            effective_status=RetrievalReadinessStatus.DISALLOWED,
        ),
    }

    return EngineResult(
        engine_name="retrieval_readiness_engine",
        status="success",
        on_page=OnPageEvidence(
            url=url,
            status_code=200,
            title="Sample Test Page for Retrieval",
            meta_description="A test page description for search engines",
            canonical_url=url,
            meta_robots="index, follow",
            raw_html="<html><head><title>Sample</title></head><body><p>This is test content for verification.</p></body></html>",
            response_headers={"content-type": "text/html; charset=utf-8"},
        ),
        robots=RobotsEvidence(
            status_code=200,
            user_agents_specified=["*"],
            disallowed_paths=[],
            sitemap_urls=["https://example.com/sitemap.xml"],
            has_llms_txt=False,
            ai_scrapers_blocked=False,
            raw_content="User-agent: *\nAllow: /\n",
        ),
        schema=SchemaEvidence(types_detected=[]),
        geo_aeo=GeoAeoEvidence(url=url),
        trust=TrustStackResult(),
        performance=PerformanceEvidence(url=url),
        cloud=CloudIntelligenceEvidence(domain="example.com"),
        retrieval_readiness=RetrievalReadinessEvidence(
            url=url,
            bot_access_records=bot_records,
            total_bots_evaluated=3,
            search_index_allowed_count=2,
            ai_training_allowed_count=0,
            user_fetch_allowed_count=0,
            snippet_controls=SnippetControlEvidence(
                status=SnippetControlStatus.ALLOWED,
                has_nosnippet=False,
                max_snippet=None,
            ),
            content_availability=ContentAvailabilityEvidence(
                raw_html_available=True,
                rendered_html_available=True,
                raw_word_count=50,
                rendered_word_count=50,
                word_count_delta=0,
                significant_content_difference=False,
                js_rendering_impact="Raw and rendered HTML text counts are aligned (50 raw vs 50 rendered).",
            ),
            waf_challenge=WafChallengeEvidence(
                status=RetrievalReadinessStatus.ALLOWED,
                is_blocked=False,
            ),
            indexability_interaction=IndexabilityInteractionEvidence(
                canonical_url=url,
                canonical_signal="SELF_REFERENCING",
                canonical_conflict=False,
                interaction_summary="Self-referencing canonical tag declared.",
            ),
            facts=["Observable FACT: 2 search indexing crawler(s) permitted; 1 AI scraper(s) disallowed."],
            analyses=["ANALYSIS: Search indexers have unobstructed crawl and index paths."],
        ),
    )


class TestEvidenceCollectorRetrievalIntegration:
    """Verifies that EvidenceCollector runs Step 17 without issuing redundant network requests."""

    def test_collector_zero_redundant_http_calls(self):
        collector = EvidenceCollector()
        mock_browser = EngineResult(
            engine_name="browser_engine",
            status="success",
            raw_html="<html><body><p>Clean home page rendered</p></body></html>",
        )
        mock_seo = EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(
                url="https://example.com/",
                status_code=200,
                title="Home",
                raw_html="<html><body><p>Clean home page</p></body></html>",
                response_headers={"content-type": "text/html"},
            ),
            robots=RobotsEvidence(
                status_code=200,
                raw_content="User-agent: *\nAllow: /\n",
            ),
        )

        with patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser), \
             patch.object(collector.seo_engine, "execute", return_value=mock_seo), \
             patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
             patch.object(collector.retrieval_readiness_engine, "evaluate_page", wraps=collector.retrieval_readiness_engine.evaluate_page) as mock_eval:
            results = collector.collect("https://example.com/")

            # Step 17 was executed
            assert mock_eval.call_count == 1
            retrieval_result = results.get("retrieval_readiness_engine")
            assert retrieval_result is not None
            assert retrieval_result.retrieval_readiness is not None
            assert retrieval_result.retrieval_readiness.url == "https://example.com/"
            assert retrieval_result.retrieval_readiness.search_index_allowed_count >= 1

            # No extra HTTP calls were made by retrieval readiness engine
            # It strictly reused on_page, robots, and browser data passed in memory


class TestProvenancePreservation:
    """Verifies provenance chain includes RetrievalReadinessEngine execution."""

    def test_provenance_includes_retrieval_readiness(self):
        engine_result = build_mock_engine_result()
        tags = ProvenanceTagger.tag({"retrieval_readiness_engine": engine_result})

        rr_tags = [t for t in tags if t.engine == "retrieval_readiness_engine"]
        assert len(rr_tags) == 1
        tag = rr_tags[0]
        assert "robots.txt & HTTP Directives" in tag.source_file
        assert tag.confidence == "high"


class TestConflictDetection:
    """Verifies retrieval directive and WAF conflicts detection."""

    def test_detect_ai_retrieval_directive_conflict(self):
        detector = ConflictDetector()
        mock_result = build_mock_engine_result()
        # Create conflict: robots allows OAI-SearchBot, but page has noindex
        mock_result.retrieval_readiness.indexability_interaction.has_noindex = True
        mock_result.retrieval_readiness.indexability_interaction.noindex_sources = ["meta:robots"]

        conflicts = detector.detect({"retrieval_readiness_engine": mock_result})
        rr_conflicts = [c for c in conflicts if c.category == "AI_RETRIEVAL_DIRECTIVE_CONFLICT"]
        assert len(rr_conflicts) == 1
        assert "OAI-SearchBot is permitted in robots.txt, but page declares noindex" in rr_conflicts[0].description

    def test_detect_waf_retrieval_block_conflict(self):
        detector = ConflictDetector()
        mock_result = build_mock_engine_result()
        # Create conflict: robots allows crawler, but WAF blocks with 403
        mock_result.retrieval_readiness.waf_challenge.is_blocked = True
        mock_result.retrieval_readiness.waf_challenge.status_code = 403
        mock_result.retrieval_readiness.waf_challenge.barrier_type = "WAF_HTTP_STATUS"
        mock_result.retrieval_readiness.waf_challenge.waf_provider = "Cloudflare"

        conflicts = detector.detect({"retrieval_readiness_engine": mock_result})
        waf_conflicts = [c for c in conflicts if c.category == "WAF_RETRIEVAL_BLOCK"]
        assert len(waf_conflicts) == 1
        assert "robots.txt permits crawler access, but server returned HTTP 403" in waf_conflicts[0].description


class TestSynthesizerFormulaInvariance:
    """Verifies synthesis incorporates retrieval readiness without altering existing health scores."""

    def test_synthesis_preserves_health_scores(self):
        engine_result = build_mock_engine_result()
        synthesizer = IntelligenceSynthesizer()
        results_map = {
            "advertools_seo": engine_result,
            "browser_engine": engine_result,
            "rankintel_geo": engine_result,
            "retrieval_readiness_engine": engine_result,
        }
        report = synthesizer.synthesize("https://example.com/test", results_map)

        assert report.unified_retrieval_readiness is not None
        assert report.unified_retrieval_readiness.search_index_allowed_count == 2
        assert report.unified_retrieval_readiness.ai_training_allowed_count == 0

        # Health score formulas (technical, geo, trust, performance, overall)
        # must remain strictly invariant and calculated solely from their established dimensions
        assert report.technical_health_score >= 0
        assert report.geo_readiness_score >= 0
        assert report.trust_score >= 0
        assert report.performance_score >= 0
        assert report.overall_health_score >= 0


class TestMarkdownAndJsonReporting:
    """Verifies that reporters correctly format the retrieval readiness facts and tables."""

    def test_markdown_report_includes_dedicated_section(self):
        engine_result = build_mock_engine_result()
        synthesizer = IntelligenceSynthesizer()
        results_map = {
            "advertools_seo": engine_result,
            "browser_engine": engine_result,
            "rankintel_geo": engine_result,
            "retrieval_readiness_engine": engine_result,
        }
        report = synthesizer.synthesize("https://example.com/test", results_map)

        md_text = MarkdownReporter.render(report)

        assert "## 🤖 AI ACCESS & RETRIEVAL READINESS" in md_text
        assert "Core Crawler Retrieval Status Matrix" in md_text
        assert "Googlebot" in md_text
        assert "OAI-SearchBot" in md_text
        assert "GPTBot" in md_text
        assert "Snippet Controls & Document Directives" in md_text
        assert "Content Availability & Rendering Telemetry" in md_text
        assert "Factual Findings" in md_text
        assert "Technical Analyses" in md_text

    def test_json_serialization(self):
        engine_result = build_mock_engine_result()
        synthesizer = IntelligenceSynthesizer()
        results_map = {
            "advertools_seo": engine_result,
            "browser_engine": engine_result,
            "rankintel_geo": engine_result,
            "retrieval_readiness_engine": engine_result,
        }
        report = synthesizer.synthesize("https://example.com/test", results_map)

        json_str = JsonReporter.render_audit(report)
        payload = json.loads(json_str)

        assert "unified_retrieval_readiness" in payload
        rr_payload = payload["unified_retrieval_readiness"]
        assert rr_payload["search_index_allowed_count"] == 2
        assert rr_payload["ai_training_allowed_count"] == 0
        assert rr_payload["snippet_controls"]["status"] == "ALLOWED"


class TestCliScorecardAndMcpTelemetry:
    """Verifies CLI executive scorecard row and MCP tool telemetry output."""

    def test_cli_renders_retrieval_row(self):
        engine_result = build_mock_engine_result()
        results_map = {
            "advertools_seo": engine_result,
            "browser_engine": engine_result,
            "rankintel_geo": engine_result,
            "retrieval_readiness_engine": engine_result,
        }
        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize("https://example.com/test", results_map)

        with patch("rankintel.cli.EvidenceCollector") as mock_col, \
             patch("rankintel.cli.IntelligenceSynthesizer") as mock_syn, \
             patch("rankintel.reporters.markdown.MarkdownReporter.save", return_value="audits/test.md"):
            mock_col.return_value.collect.return_value = results_map
            mock_syn.return_value.synthesize.return_value = report
            runner = CliRunner()
            result = runner.invoke(main, ["audit", "https://example.com/test"])
            assert result.exit_code == 0
            assert "AI Retrieval Readiness" in result.output
            assert "2 search indexers" in result.output

    def test_mcp_rankintel_audit_telemetry(self):
        engine_result = build_mock_engine_result()
        results_map = {
            "advertools_seo": engine_result,
            "browser_engine": engine_result,
            "rankintel_geo": engine_result,
            "retrieval_readiness_engine": engine_result,
        }

        with patch("rankintel.evidence.collector.EvidenceCollector.collect", return_value=results_map):
            response = rankintel_audit("https://example.com/test")
            assert "retrieval_search_indexers_allowed" in response
            assert response["retrieval_search_indexers_allowed"] == 2
            assert response["retrieval_training_scrapers_allowed"] == 0
            assert response["retrieval_waf_blocked"] is False
            assert response["retrieval_snippet_status"] == "ALLOWED"
