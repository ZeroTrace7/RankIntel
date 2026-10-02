"""
Unit & Integration Tests for RFC 9309 BotMatrixEngine & Crawler Access Triangulator.
"""
import pytest
import httpx
from unittest.mock import patch, MagicMock

from rankintel.engines.bot_matrix_engine import (
    BotMatrixEngine,
    DirectiveRule,
    UserAgentBlock,
)
from rankintel.models.schema import (
    BotAccessStatus,
    BotCategory,
    BotMatrixReport,
    BotMatrixEntry,
    RobotsEvidence,
    SynthesisReport,
    OnPageEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
)
from rankintel.engines.seo_engine import SeoEngine
from rankintel.reporters.markdown import MarkdownReporter


SAMPLE_ROBOTS_HARDENED = """
# Production Hardened robots.txt
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /cart/
Disallow: /private/*

# Protect against AI scrapers / training
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: CCBot
Disallow: /

# Ensure AI search and discovery are explicitly allowed
User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Googlebot
Allow: /

Sitemap: https://example.com/sitemap.xml
"""

SAMPLE_ROBOTS_BLANKET_BLOCK = """
User-agent: *
Disallow: /
"""

SAMPLE_ROBOTS_AI_SEARCH_BLOCKED = """
User-agent: *
Allow: /

User-agent: OAI-SearchBot
Disallow: /

User-agent: PerplexityBot
Disallow: /
"""


class TestBotMatrixEngine:
    @pytest.fixture
    def engine(self):
        return BotMatrixEngine()

    def test_directive_rule_longest_match_and_regex(self):
        rule1 = DirectiveRule("disallow", "/blog/", 1)
        rule2 = DirectiveRule("allow", "/blog/post-1", 2)
        rule3 = DirectiveRule("disallow", "/*.php$", 3)

        assert rule1.matches("/blog/anything")
        assert not rule1.matches("/other")

        assert rule2.matches("/blog/post-1")
        assert rule2.pattern_len > rule1.pattern_len

        assert rule3.matches("/index.php")
        assert not rule3.matches("/index.php/details")
        assert not rule3.matches("/index.html")

    def test_parse_multi_agent_blocks(self, engine):
        content = """
        User-agent: botA
        User-agent: botB
        Disallow: /secret
        """
        blocks = engine.parse_robots_txt(content)
        assert len(blocks) == 1
        assert "bota" in blocks[0].user_agents
        assert "botb" in blocks[0].user_agents
        assert len(blocks[0].rules) == 1
        assert blocks[0].rules[0].pattern == "/secret"

    def test_evaluate_hardened_robots(self, engine):
        report = engine.evaluate_robots_content(SAMPLE_ROBOTS_HARDENED, target_path="/")
        assert report.robots_found is True
        assert report.total_bots_evaluated >= 15

        # Check Googlebot allowed
        googlebot = next(e for e in report.entries if e.bot_name == "Googlebot")
        assert googlebot.status == BotAccessStatus.ALLOWED.value
        assert googlebot.rule_source == "explicit"
        assert "Indexed in Google" in googlebot.business_impact

        # Check OAI-SearchBot allowed
        oai_search = next(e for e in report.entries if e.bot_name == "OAI-SearchBot")
        assert oai_search.status == BotAccessStatus.ALLOWED.value
        assert oai_search.rule_source == "explicit"
        assert "ChatGPT Search" in oai_search.business_impact

        # Check GPTBot disallowed
        gptbot = next(e for e in report.entries if e.bot_name == "GPTBot")
        assert gptbot.status == BotAccessStatus.DISALLOWED.value
        assert gptbot.rule_source == "explicit"
        assert "Protected" in gptbot.business_impact

        # Check ClaudeBot disallowed
        claudebot = next(e for e in report.entries if e.bot_name == "ClaudeBot")
        assert claudebot.status == BotAccessStatus.DISALLOWED.value

        # Check Bingbot inherited wildcard Allow: /
        bingbot = next(e for e in report.entries if e.bot_name == "Bingbot")
        assert bingbot.status == BotAccessStatus.ALLOWED.value
        assert bingbot.rule_source == "wildcard"

        # Check summary metrics
        assert report.search_allowed_count >= 5
        assert report.ai_search_allowed_count >= 2
        assert report.ai_training_blocked_count >= 4

    def test_blanket_disallow_emergency_recommendation(self, engine):
        report = engine.evaluate_robots_content(SAMPLE_ROBOTS_BLANKET_BLOCK, target_path="/")
        googlebot = next(e for e in report.entries if e.bot_name == "Googlebot")
        assert googlebot.status == BotAccessStatus.DISALLOWED.value
        assert any("EMERGENCY" in r or "CRITICAL" in r for r in report.recommendations)

    def test_ai_search_blocked_warning(self, engine):
        report = engine.evaluate_robots_content(SAMPLE_ROBOTS_AI_SEARCH_BLOCKED, target_path="/")
        oai_search = next(e for e in report.entries if e.bot_name == "OAI-SearchBot")
        assert oai_search.status == BotAccessStatus.DISALLOWED.value

        perplexity = next(e for e in report.entries if e.bot_name == "PerplexityBot")
        assert perplexity.status == BotAccessStatus.DISALLOWED.value

        assert any("AI Search bots" in r and "disallowed" in r for r in report.recommendations)

    def test_empty_disallow_resets_allow_all(self, engine):
        content = """
        User-agent: Googlebot
        Disallow:
        """
        report = engine.evaluate_robots_content(content, target_path="/anything")
        googlebot = next(e for e in report.entries if e.bot_name == "Googlebot")
        assert googlebot.status == BotAccessStatus.ALLOWED.value

    def test_missing_robots_txt_default_allow(self, engine):
        report = engine.evaluate_robots_content("", robots_found=False)
        assert report.robots_found is False
        for entry in report.entries:
            assert entry.status == BotAccessStatus.ALLOWED.value
            assert entry.rule_source == "default_allow"
        assert any("No robots.txt detected" in r for r in report.recommendations)

    @pytest.mark.anyio
    async def test_async_evaluate_url_with_transport(self, engine):
        async def handler(request: httpx.Request):
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=SAMPLE_ROBOTS_HARDENED)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        report = await engine.evaluate_url("https://testsite.org", transport=transport)
        assert report.robots_found is True
        assert report.search_allowed_count >= 5

    def test_sync_evaluate_url_mock(self, engine):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_ROBOTS_HARDENED

        with patch("httpx.Client.get", return_value=mock_resp):
            report = engine.evaluate_url_sync("https://testsite.org")
            assert report.robots_found is True
            assert report.total_bots_evaluated >= 15


class TestSeoEngineBotMatrixIntegration:
    @patch("requests.get")
    def test_seo_engine_populates_bot_matrix(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_ROBOTS_HARDENED
        mock_get.return_value = mock_resp

        engine = SeoEngine()
        evidence = engine.audit_robots_txt("https://example.com")

        assert evidence.found is True
        assert evidence.bot_matrix is not None
        assert evidence.bot_matrix.total_bots_evaluated >= 15
        assert "Googlebot" in evidence.bot_access
        assert evidence.bot_access["Googlebot"].status == "ALLOWED"
        assert evidence.bot_access["GPTBot"].status == "DISALLOWED"


class TestMarkdownReporterBotMatrix:
    def test_markdown_renders_bot_matrix_table(self):
        engine = BotMatrixEngine()
        bot_report = engine.evaluate_robots_content(SAMPLE_ROBOTS_HARDENED, target_path="/")

        robots_ev = RobotsEvidence(
            found=True,
            robots_url="https://example.com/robots.txt",
            bot_matrix=bot_report,
        )

        report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-02T15:00:00",
            overall_health_score=85,
            unified_on_page=OnPageEvidence(url="https://example.com", status_code=200, title="Example"),
            unified_robots=robots_ev,
            unified_schema=SchemaEvidence(),
            unified_geo=GeoAeoEvidence(),
        )

        reporter = MarkdownReporter()
        md = reporter.render(report)

        assert "AI & SEARCH CRAWLER ACCESS MATRIX" in md
        assert "Googlebot" in md
        assert "OAI-SearchBot" in md
        assert "GPTBot" in md
        assert "ChatGPT Search" in md
        assert "Business Impact" in md
