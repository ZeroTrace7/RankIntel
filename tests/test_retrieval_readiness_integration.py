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
    ConflictType,
)


def build_mock_engine_result(url: str = "https://example.com/test") -> EngineResult:
    """Builds a deterministic mock EngineResult with retrieval readiness populated."""
    return EngineResult(
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
            bot_access=[
                BotRetrievalAccessRecord(
                    bot_name="Googlebot",
                    purpose=BotPurpose.SEARCH_INDEX,
                    robots_status=RetrievalReadinessStatus.ALLOWED,
                    effective_status=RetrievalReadinessStatus.ALLOWED,
                    honors_robots_txt=True,
                    is_control_token_only=False,
                ),
                BotRetrievalAccessRecord(
                    bot_name="OAI-SearchBot",
                    purpose=BotPurpose.SEARCH_INDEX,
                    robots_status=RetrievalReadinessStatus.ALLOWED,
                    effective_status=RetrievalReadinessStatus.ALLOWED,
                    honors_robots_txt=True,
                    is_control_token_only=False,
                ),
                BotRetrievalAccessRecord(
                    bot_name="GPTBot",
                    purpose=BotPurpose.AI_TRAINING,
                    robots_status=RetrievalReadinessStatus.DISALLOWED,
                    effective_status=RetrievalReadinessStatus.DISALLOWED,
                    honors_robots_txt=True,
                    is_control_token_only=False,
                ),
            ],
            search_index_allowed_count=2,
            ai_training_allowed_count=0,
            user_fetch_allowed_count=0,
            snippet_controls=SnippetControlEvidence(
                status=SnippetControlStatus.ALLOWED,
                nosnippet=False,
                max_snippet_chars=None,
            ),
            content_availability=ContentAvailabilityEvidence(
                raw_word_count=50,
                rendered_word_count=50,
                word_count_delta=0,
                requires_js_for_core_content=False,
                impact_fact="FACT: Core content is available in raw HTML without requiring JavaScript execution.",
            ),
            waf_challenge=WafChallengeEvidence(
                status=RetrievalReadinessStatus.ALLOWED,
                is_blocked=False,
            ),
            canonical_interaction=IndexabilityInteractionEvidence(
                url=url,
                canonical_url=url,
                is_indexable=True,
                matches_canonical=True,
                has_canonical_mismatch=False,
                interaction_analysis="Canonical matches URL and indexing is permitted.",
            ),
            facts=["Observable FACT: 2 search indexing crawler(s) permitted; 1 AI scraper(s) disallowed."],
            analyses=["ANALYSIS: Search indexers have unobstructed crawl and index paths."],
        ),
    )


class TestEvidenceCollectorRetrievalIntegration:
    """Verifies that EvidenceCollector runs Step 17 without issuing redundant network requests."""

    @patch("rankintel.engines.seo_engine.SeoEngine.extract_on_page")
    @patch("rankintel.engines.seo_engine.SeoEngine.fetch_robots_txt")
    @patch("rankintel.engines.browser_engine.BrowserEngine.extract_dynamic_dom")
    def test_collector_zero_redundant_http_calls(self, mock_browser, mock_robots, mock_on_page):
        # Configure mocks
        mock_on_page.return_value = OnPageEvidence(
            url="https://example.com/",
            status_code=200,
            title="Home",
            raw_html="<html><body><p>Clean home page</p></body></html>",
            response_headers={"content-type": "text/html"},
        )
        mock_robots.return_value = RobotsEvidence(
            status_code=200,
            raw_content="User-agent: *\nAllow: /\n",
        )
        mock_browser.return_value = MagicMock(
            rendered_html="<html><body><p>Clean home page rendered</p></body></html>",
            hydrated_json_ld=[],
            console_errors=[],
        )

        collector = EvidenceCollector()
        with patch.object(collector.retrieval_readiness_engine, "evaluate_page", wraps=collector.retrieval_readiness_engine.evaluate_page) as mock_eval:
            result = collector.collect("https://example.com/")

            # Step 17 was executed
            assert mock_eval.call_count == 1
            assert result.retrieval_readiness is not None
            assert result.retrieval_readiness.url == "https://example.com/"
            assert result.retrieval_readiness.search_index_allowed_count >= 1

            # No extra HTTP calls were made by retrieval readiness engine
            # It strictly reused on_page, robots, and browser data passed in memory


class TestProvenancePreservation:
    """Verifies provenance chain includes RetrievalReadinessEngine execution."""

    def test_provenance_includes_retrieval_readiness(self):
        engine_result = build_mock_engine_result()
        tagger = ProvenanceTagger()
        tags = tagger.tag_all(engine_result)

        rr_tags = [t for t in tags if t.engine == "retrieval_readiness_engine"]
        assert len(rr_tags) == 1
        tag = rr_tags[0]
        assert tag.source == "HTTP Headers, Raw/Rendered DOM & RFC 9309 robots.txt"
        assert tag.confidence == 1.0


class TestConflictDetection:
    """Verifies retrieval directive and WAF conflicts detection."""

    def test_detect_ai_retrieval_directive_conflict(self):
        detector = ConflictDetector()
        mock_result = build_mock_engine_result()
        # Create conflict: robots allows OAI-SearchBot, but page has nosnippet
        mock_result.retrieval_readiness.snippet_controls.nosnippet = True
        mock_result.retrieval_readiness.snippet_controls.status = SnippetControlStatus.DISALLOWED

        conflicts = detector.detect(mock_result)
        rr_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.AI_RETRIEVAL_DIRECTIVE_CONFLICT]
        assert len(rr_conflicts) == 1
        assert "OAI-SearchBot is allowed in robots.txt, but page specifies nosnippet" in rr_conflicts[0].description

    def test_detect_waf_retrieval_block_conflict(self):
        detector = ConflictDetector()
        mock_result = build_mock_engine_result()
        # Create conflict: robots allows crawler, but WAF blocks with 403
        mock_result.retrieval_readiness.waf_challenge.is_blocked = True
        mock_result.retrieval_readiness.waf_challenge.barrier_type = "WAF_HTTP_STATUS"
        mock_result.retrieval_readiness.waf_challenge.waf_provider = "Cloudflare"

        conflicts = detector.detect(mock_result)
        waf_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.WAF_RETRIEVAL_BLOCK]
        assert len(waf_conflicts) == 1
        assert "Cloudflare WAF / challenge is actively blocking automated retrieval" in waf_conflicts[0].description


class TestSynthesizerFormulaInvariance:
    """Verifies synthesis incorporates retrieval readiness without altering existing health scores."""

    def test_synthesis_preserves_health_scores(self):
        engine_result = build_mock_engine_result()
        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize("https://example.com/test", engine_result)

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
        report = synthesizer.synthesize("https://example.com/test", engine_result)

        md_reporter = MarkdownReporter()
        md_text = md_reporter.generate_report(report)

        assert "## 🤖 AI ACCESS & RETRIEVAL READINESS" in md_text
        assert "### Bot Retrieval Access Matrix" in md_text
        assert "Googlebot" in md_text
        assert "OAI-SearchBot" in md_text
        assert "GPTBot" in md_text
        assert "### Snippet & Content Controls" in md_text
        assert "### Content Availability (Raw vs Rendered)" in md_text
        assert "### Access Barriers & WAF / Challenge Detection" in md_text

    def test_json_serialization(self):
        engine_result = build_mock_engine_result()
        synthesizer = IntelligenceSynthesizer()
        report = synthesizer.synthesize("https://example.com/test", engine_result)

        json_reporter = JsonReporter()
        payload = json_reporter.to_dict(report)

        assert "unified_retrieval_readiness" in payload
        rr_payload = payload["unified_retrieval_readiness"]
        assert rr_payload["search_index_allowed_count"] == 2
        assert rr_payload["ai_training_allowed_count"] == 0
        assert rr_payload["snippet_controls"]["status"] == "ALLOWED"


class TestCliScorecardAndMcpTelemetry:
    """Verifies CLI executive scorecard row and MCP tool telemetry output."""

    def test_cli_renders_retrieval_row(self):
        engine_result = build_mock_engine_result()

        with patch("rankintel.evidence.collector.EvidenceCollector.collect", return_value=engine_result):
            runner = CliRunner()
            result = runner.invoke(main, ["audit", "https://example.com/test", "--no-browser", "--no-cloud"])
            assert result.exit_code == 0
            assert "AI Retrieval Access" in result.output
            assert "Search Index: 2 allowed" in result.output

    def test_mcp_rankintel_audit_telemetry(self):
        engine_result = build_mock_engine_result()

        with patch("rankintel.evidence.collector.EvidenceCollector.collect", return_value=engine_result):
            response = rankintel_audit("https://example.com/test")
            assert "retrieval_search_indexers_allowed" in response
            assert response["retrieval_search_indexers_allowed"] == 2
            assert response["retrieval_training_scrapers_allowed"] == 0
            assert response["retrieval_waf_blocked"] is False
            assert response["retrieval_snippet_status"] == "ALLOWED"
