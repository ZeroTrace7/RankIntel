"""
Unit tests for RankIntel Phase 10.1: RetrievalReadinessEngine.
Verifies RFC 9309 robots access per purpose, snippet controls (nosnippet, max-snippet, data-nosnippet),
content availability (raw vs rendered), conservative WAF/challenge detection,
canonical/indexability interactions, and strict FACT + ANALYSIS output.
"""
import pytest

from rankintel.engines.retrieval_readiness_engine import RetrievalReadinessEngine
from rankintel.references.ai_crawlers import (
    CORE_RETRIEVAL_BOTS,
    MASTER_BOT_REGISTRY,
    get_crawler_info,
)
from rankintel.models.schema import (
    RetrievalReadinessStatus,
    BotPurpose,
    SnippetControlStatus,
    SnippetControlEvidence,
    IndexabilityInteractionEvidence,
    ContentAvailabilityEvidence,
    WafChallengeEvidence,
    BotRetrievalAccessRecord,
    RetrievalReadinessEvidence,
    IndexabilityStatus,
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
)


SAMPLE_ROBOTS_HARDENED = """
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /cart/

User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Googlebot
Allow: /
"""

SAMPLE_ROBOTS_DISALLOW_ALL = """
User-agent: *
Disallow: /
"""

SAMPLE_ROBOTS_ALLOW_ALL = """
User-agent: *
Allow: /
"""


class TestCoreCrawlerRegistry:
    """Verifies crawler registry definitions and purpose distinctions."""

    def test_core_12_bots_present(self):
        assert len(CORE_RETRIEVAL_BOTS) == 12
        expected_bots = [
            "Googlebot",
            "Google-Extended",
            "OAI-SearchBot",
            "GPTBot",
            "ChatGPT-User",
            "Claude-SearchBot",
            "ClaudeBot",
            "Claude-User",
            "PerplexityBot",
            "Perplexity-User",
            "Bingbot",
            "Applebot",
        ]
        for bot in expected_bots:
            assert bot in CORE_RETRIEVAL_BOTS
            assert bot in MASTER_BOT_REGISTRY

    def test_crawler_purposes_and_properties(self):
        # OAI-SearchBot is search_index and honors robots.txt
        oai_sb = get_crawler_info("OAI-SearchBot")
        assert oai_sb is not None
        assert oai_sb["purpose"] == BotPurpose.SEARCH_INDEX.value
        assert oai_sb["honors_robots_txt"] is True

        # GPTBot is ai_training and honors robots.txt
        gptbot = get_crawler_info("GPTBot")
        assert gptbot is not None
        assert gptbot["purpose"] == BotPurpose.AI_TRAINING.value
        assert gptbot["honors_robots_txt"] is True

        # Google-Extended is control token for AI training / Gemini
        g_ext = get_crawler_info("Google-Extended")
        assert g_ext is not None
        assert g_ext["purpose"] == BotPurpose.AI_TRAINING.value
        assert g_ext["is_control_token_only"] is True

        # ChatGPT-User is user_fetch
        cg_user = get_crawler_info("ChatGPT-User")
        assert cg_user is not None
        assert cg_user["purpose"] == BotPurpose.USER_FETCH.value

        # Perplexity-User is user_fetch and generally ignores robots.txt per Perplexity docs
        perp_user = get_crawler_info("Perplexity-User")
        assert perp_user is not None
        assert perp_user["purpose"] == BotPurpose.USER_FETCH.value
        assert perp_user["honors_robots_txt"] is False


class TestRobotsAccessEvaluation:
    """Verifies per-bot RFC 9309 evaluation against various robots.txt configurations."""

    def test_hardened_robots_eval(self):
        engine = RetrievalReadinessEngine()
        ev = engine.evaluate_page(
            url="https://example.com/article",
            status_code=200,
            robots_content=SAMPLE_ROBOTS_HARDENED,
            robots_found=True,
            core_bots_only=True,
        )
        by_name = ev.bot_access_records

        # Search indexers allowed
        assert by_name["Googlebot"].robots_access == RetrievalReadinessStatus.ALLOWED
        assert by_name["OAI-SearchBot"].robots_access == RetrievalReadinessStatus.ALLOWED
        assert by_name["PerplexityBot"].robots_access == RetrievalReadinessStatus.ALLOWED
        assert by_name["Bingbot"].robots_access == RetrievalReadinessStatus.ALLOWED

        # Scrapers disallowed
        assert by_name["GPTBot"].robots_access == RetrievalReadinessStatus.DISALLOWED
        assert by_name["ClaudeBot"].robots_access == RetrievalReadinessStatus.DISALLOWED
        assert by_name["Google-Extended"].robots_access == RetrievalReadinessStatus.DISALLOWED

        # Perplexity-User is user_fetch and bypasses robots.txt
        assert by_name["Perplexity-User"].robots_access == RetrievalReadinessStatus.NOT_APPLICABLE

    def test_disallow_all_robots(self):
        engine = RetrievalReadinessEngine()
        ev = engine.evaluate_page(
            url="https://example.com/page",
            status_code=200,
            robots_content=SAMPLE_ROBOTS_DISALLOW_ALL,
            robots_found=True,
            core_bots_only=True,
        )
        by_name = ev.bot_access_records
        for name, rec in by_name.items():
            meta = MASTER_BOT_REGISTRY.get(name, {})
            if meta.get("honors_robots_txt", True):
                assert rec.robots_access == RetrievalReadinessStatus.DISALLOWED
            else:
                assert rec.robots_access == RetrievalReadinessStatus.NOT_APPLICABLE

    def test_missing_robots_defaults_to_allowed(self):
        engine = RetrievalReadinessEngine()
        ev = engine.evaluate_page(
            url="https://example.com/page",
            status_code=200,
            robots_content="",
            robots_found=False,
            core_bots_only=True,
        )
        for name, rec in ev.bot_access_records.items():
            meta = MASTER_BOT_REGISTRY.get(name, {})
            if meta.get("honors_robots_txt", True):
                assert rec.robots_access == RetrievalReadinessStatus.ALLOWED

    def test_waf_blocked_overrides_effective_status(self):
        engine = RetrievalReadinessEngine()
        ev = engine.evaluate_page(
            url="https://example.com/page",
            status_code=403,
            robots_content=SAMPLE_ROBOTS_ALLOW_ALL,
            robots_found=True,
            core_bots_only=True,
        )
        for rec in ev.bot_access_records.values():
            # robots_access is still ALLOWED or NOT_APPLICABLE, but effective_status is BLOCKED
            assert rec.effective_status == RetrievalReadinessStatus.BLOCKED


class TestSnippetControlsEvaluation:
    """Verifies nosnippet, max-snippet, data-nosnippet, and X-Robots-Tag handling."""

    def test_default_snippet_allowed(self):
        engine = RetrievalReadinessEngine()
        html = "<html><head><title>Test</title></head><body><p>Hello world</p></body></html>"
        evidence = engine.parse_snippet_controls(raw_html=html, response_headers={})
        assert evidence.status == SnippetControlStatus.ALLOWED
        assert evidence.has_nosnippet is False
        assert evidence.max_snippet is None
        assert evidence.data_nosnippet_count == 0

    def test_meta_nosnippet(self):
        engine = RetrievalReadinessEngine()
        html = '<html><head><meta name="robots" content="nosnippet"></head><body><p>Hello</p></body></html>'
        evidence = engine.parse_snippet_controls(raw_html=html, response_headers={})
        assert evidence.status == SnippetControlStatus.NOSNIPPET
        assert evidence.has_nosnippet is True

    def test_x_robots_tag_nosnippet(self):
        engine = RetrievalReadinessEngine()
        html = "<html><head><title>Test</title></head><body><p>Hello</p></body></html>"
        headers = {"x-robots-tag": "nosnippet, noarchive"}
        evidence = engine.parse_snippet_controls(raw_html=html, response_headers=headers)
        assert evidence.status == SnippetControlStatus.NOSNIPPET
        assert evidence.has_nosnippet is True
        assert "header:x-robots-tag" in evidence.nosnippet_sources

    def test_max_snippet_numeric(self):
        engine = RetrievalReadinessEngine()
        html = '<html><head><meta name="robots" content="max-snippet:150, max-image-preview:large"></head><body><p>Hello</p></body></html>'
        evidence = engine.parse_snippet_controls(raw_html=html, response_headers={})
        assert evidence.status == SnippetControlStatus.MAX_SNIPPET
        assert evidence.max_snippet == 150
        assert evidence.max_image_preview == "large"

    def test_max_snippet_zero_disallows(self):
        engine = RetrievalReadinessEngine()
        html = '<html><head><meta name="robots" content="max-snippet:0"></head><body><p>Hello</p></body></html>'
        evidence = engine.parse_snippet_controls(raw_html=html, response_headers={})
        assert evidence.status == SnippetControlStatus.NOSNIPPET
        assert evidence.max_snippet == 0

    def test_data_nosnippet_elements(self):
        engine = RetrievalReadinessEngine()
        html = (
            "<html><body>"
            "<p>Public overview text.</p>"
            '<div data-nosnippet="true" class="client-box">Private client data section</div>'
            "<span data-nosnippet id='secret'>Internal code 12345</span>"
            "</body></html>"
        )
        evidence = engine.parse_snippet_controls(raw_html=html, response_headers={})
        assert evidence.has_data_nosnippet is True
        assert evidence.data_nosnippet_count == 2
        assert len(evidence.data_nosnippet_sample_selectors) == 2


class TestContentAvailabilityEvaluation:
    """Verifies raw vs rendered word count and JS-dependency detection."""

    def test_no_rendered_html_fallback(self):
        engine = RetrievalReadinessEngine()
        raw_html = "<html><body><p>" + "word " * 200 + "</p></body></html>"
        evidence = engine.evaluate_content_availability(raw_html=raw_html, rendered_html=None)
        assert evidence.raw_word_count == 200
        assert evidence.rendered_word_count == 0
        assert evidence.word_count_delta == 0
        assert evidence.significant_content_difference is False
        assert "Static HTML observed" in evidence.js_rendering_impact

    def test_static_html_near_identical_words(self):
        engine = RetrievalReadinessEngine()
        raw = "<html><body><p>" + "keyword " * 300 + "</p></body></html>"
        rendered = "<html><body><p>" + "keyword " * 310 + "</p></body></html>"
        evidence = engine.evaluate_content_availability(raw_html=raw, rendered_html=rendered)
        assert evidence.raw_word_count == 300
        assert evidence.rendered_word_count == 310
        assert evidence.word_count_delta == 10
        assert evidence.significant_content_difference is False

    def test_heavy_js_client_rendered_page(self):
        engine = RetrievalReadinessEngine()
        # Raw HTML is just a root div with 10 words
        raw = "<html><body><div id='root'>" + "loading app " * 5 + "</div></body></html>"
        # Rendered HTML hydrates 600 words
        rendered = "<html><body><div id='root'>" + "content detailed information " * 200 + "</div></body></html>"
        evidence = engine.evaluate_content_availability(raw_html=raw, rendered_html=rendered)
        assert evidence.raw_word_count == 10
        assert evidence.rendered_word_count == 600
        assert evidence.word_count_delta == 590
        assert evidence.significant_content_difference is True
        assert "Rendered HTML yields" in evidence.js_rendering_impact
        assert "Some retrieval systems may have reduced access" in evidence.js_rendering_impact


class TestWafChallengeEvaluation:
    """Verifies conservative WAF, rate limit, and challenge detection."""

    def test_http_403_blocked(self):
        engine = RetrievalReadinessEngine()
        evidence = engine.detect_waf_and_challenges(
            status_code=403,
            response_headers={"cf-ray": "12345678"},
            raw_html="<html><head><title>403 Forbidden</title></head></html>",
        )
        assert evidence.status == RetrievalReadinessStatus.BLOCKED
        assert evidence.is_blocked is True
        assert evidence.barrier_type == "WAF_HTTP_STATUS"
        assert evidence.waf_provider == "Cloudflare"

    def test_http_429_rate_limited(self):
        engine = RetrievalReadinessEngine()
        evidence = engine.detect_waf_and_challenges(
            status_code=429,
            response_headers={"retry-after": "60"},
            raw_html="<html><body>Too Many Requests</body></html>",
        )
        assert evidence.status == RetrievalReadinessStatus.BLOCKED
        assert evidence.is_blocked is True
        assert evidence.barrier_type == "RATE_LIMIT"

    def test_cf_challenge_page_at_200(self):
        engine = RetrievalReadinessEngine()
        html = "<html><head><title>Just a moment...</title></head><body>Verify you are human cf-turnstile</body></html>"
        evidence = engine.detect_waf_and_challenges(
            status_code=200,
            response_headers={"cf-mitigated": "challenge"},
            raw_html=html,
        )
        assert evidence.status == RetrievalReadinessStatus.BLOCKED
        assert evidence.is_blocked is True
        assert evidence.barrier_type == "BOT_CHALLENGE"
        assert evidence.challenge_detected is True

    def test_unknown_provider_preserved(self):
        engine = RetrievalReadinessEngine()
        evidence = engine.detect_waf_and_challenges(
            status_code=403,
            response_headers={},
            raw_html="<html><body>Access Denied</body></html>",
        )
        assert evidence.status == RetrievalReadinessStatus.BLOCKED
        assert evidence.is_blocked is True
        assert evidence.waf_provider == "UNKNOWN"

    def test_standard_clean_page(self):
        engine = RetrievalReadinessEngine()
        evidence = engine.detect_waf_and_challenges(
            status_code=200,
            response_headers={"content-type": "text/html; charset=utf-8"},
            raw_html="<html><body>Normal content</body></html>",
        )
        assert evidence.status == RetrievalReadinessStatus.ALLOWED
        assert evidence.is_blocked is False
        assert evidence.waf_provider is None


class TestCanonicalAndIndexabilityInteractions:
    """Verifies canonical mismatches and interactions with indexability."""

    def test_self_canonical_indexable(self):
        engine = RetrievalReadinessEngine()
        html = '<html><head><link rel="canonical" href="https://example.com/page"><meta name="robots" content="index, follow"></head></html>'
        evidence = engine.evaluate_indexability_interaction(
            url="https://example.com/page",
            http_status=200,
            raw_html=html,
            response_headers={},
        )
        assert evidence.canonical_signal == "SELF_REFERENCING"
        assert evidence.canonical_conflict is False
        assert "Self-referencing canonical tag declared." in evidence.interaction_summary

    def test_canonical_mismatch(self):
        engine = RetrievalReadinessEngine()
        html = '<html><head><link rel="canonical" href="https://example.com/page"></head></html>'
        evidence = engine.evaluate_indexability_interaction(
            url="https://example.com/page?ref=ad",
            http_status=200,
            raw_html=html,
            response_headers={},
        )
        assert evidence.canonical_signal == "CANONICALIZED_ELSEWHERE"
        assert "Page canonicalizes to internal URL" in evidence.interaction_summary

    def test_noindex_directive(self):
        engine = RetrievalReadinessEngine()
        html = '<html><head><meta name="robots" content="noindex, nofollow"></head></html>'
        evidence = engine.evaluate_indexability_interaction(
            url="https://example.com/page",
            http_status=200,
            raw_html=html,
            response_headers={},
        )
        assert evidence.has_noindex is True
        assert "Page declares noindex directive." in evidence.interaction_summary


class TestSiteEvaluation:
    """Verifies site-wide multi-page aggregation."""

    def test_site_evaluation_aggregation(self):
        engine = RetrievalReadinessEngine()
        records = [
            CrawlRecord(
                url="https://example.com/",
                normalized_url="https://example.com/",
                identity_url="https://example.com/",
                crawl_status=CrawlStatus.FETCHED,
                depth=0,
                status_code=200,
                retrieval_readiness=RetrievalReadinessEvidence(
                    url="https://example.com/",
                    search_index_allowed_count=4,
                    ai_training_allowed_count=0,
                    user_fetch_allowed_count=3,
                    content_availability=ContentAvailabilityEvidence(
                        raw_word_count=500,
                        significant_content_difference=False,
                    ),
                    snippet_controls=SnippetControlEvidence(
                        status=SnippetControlStatus.ALLOWED,
                    ),
                    waf_challenge=WafChallengeEvidence(
                        status=RetrievalReadinessStatus.ALLOWED,
                        is_blocked=False,
                    ),
                ),
            ),
            CrawlRecord(
                url="https://example.com/js-heavy",
                normalized_url="https://example.com/js-heavy",
                identity_url="https://example.com/js-heavy",
                crawl_status=CrawlStatus.FETCHED,
                depth=1,
                status_code=200,
                retrieval_readiness=RetrievalReadinessEvidence(
                    url="https://example.com/js-heavy",
                    search_index_allowed_count=4,
                    ai_training_allowed_count=0,
                    user_fetch_allowed_count=3,
                    content_availability=ContentAvailabilityEvidence(
                        raw_word_count=20,
                        rendered_word_count=600,
                        significant_content_difference=True,
                    ),
                    snippet_controls=SnippetControlEvidence(
                        status=SnippetControlStatus.ALLOWED,
                    ),
                    waf_challenge=WafChallengeEvidence(
                        status=RetrievalReadinessStatus.ALLOWED,
                        is_blocked=False,
                    ),
                ),
            ),
            CrawlRecord(
                url="https://example.com/blocked",
                normalized_url="https://example.com/blocked",
                identity_url="https://example.com/blocked",
                crawl_status=CrawlStatus.BLOCKED,
                depth=1,
                status_code=403,
                retrieval_readiness=RetrievalReadinessEvidence(
                    url="https://example.com/blocked",
                    search_index_allowed_count=0,
                    ai_training_allowed_count=0,
                    user_fetch_allowed_count=0,
                    waf_challenge=WafChallengeEvidence(
                        status=RetrievalReadinessStatus.BLOCKED,
                        is_blocked=True,
                        barrier_type="WAF_HTTP_STATUS",
                    ),
                ),
            ),
        ]
        site_crawl = SiteCrawlResult(
            root_url="https://example.com",
            total_urls_discovered=3,
            total_urls_crawled=3,
            crawl_records=records,
        )

        site_intel = engine.evaluate_site(site_crawl)
        assert site_intel.total_pages_evaluated == 3
        assert len(site_intel.pages_with_waf_challenge) == 1
        assert "https://example.com/blocked" in site_intel.pages_with_waf_challenge
        assert len(site_intel.pages_requiring_js) == 1
        assert "https://example.com/js-heavy" in site_intel.pages_requiring_js
        assert len(site_intel.page_readiness_evidence) == 3
        assert len(site_intel.facts) >= 1
