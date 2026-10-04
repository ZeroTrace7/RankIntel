"""
AI Access & Retrieval Readiness Engine for RankIntel (Phase 10.1).

Evaluates whether major search indexers, AI citation retrievers, user-action
fetchers, and training scrapers can access, retrieve, and snippet-extract
website content using observable technical evidence.

Produces FACT and ANALYSIS only. Zero arbitrary scores, letter grades,
ranking claims, or recommendations.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from rankintel.references.ai_crawlers import (
    MASTER_BOT_REGISTRY,
    CORE_RETRIEVAL_BOTS,
)
from rankintel.engines.bot_matrix_engine import BotMatrixEngine, UserAgentBlock
from rankintel.analyzers.indexability_engine import IndexabilityEngine
from rankintel.crawler.normalizer import UrlNormalizer
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
    SiteRetrievalReadinessIntelligence,
    IndexabilityStatus,
    CrawlRecord,
    SiteCrawlResult,
)


class RetrievalReadinessEngine:
    """
    Evaluates 5 decoupled dimensions of AI & search retrieval readiness:
    1. Bot Access (robots.txt permissions per crawler purpose)
    2. Index & Snippet Controls (noindex, nosnippet, data-nosnippet, max-snippet, X-Robots-Tag)
    3. Content Availability (raw vs rendered HTML word count comparison)
    4. Access Barriers (observable 403/429/503, WAF headers, challenge pages)
    5. Factual & Analytical Synthesis (zero arbitrary scores or recommendations)
    """

    CHALLENGE_KEYWORDS: List[str] = [
        "checking your browser before accessing",
        "cloudflare turnstile",
        "attention required! | cloudflare",
        "just a moment...",
        "ddos protection by cloudflare",
        "cf-chl-bypass",
        "hcaptcha",
        "recaptcha",
        "security check to access",
        "please verify you are a human",
        "perimeterx",
        "datadome",
    ]

    @classmethod
    def detect_waf_and_challenges(
        cls,
        status_code: int,
        response_headers: Optional[Dict[str, Any]] = None,
        raw_html: Optional[str] = None,
    ) -> WafChallengeEvidence:
        """
        Conservatively detect network/WAF blocking and challenge interstitials.
        Avoids speculating on WAF provider when evidence is insufficient.
        """
        indicators: List[str] = []
        headers = response_headers or {}
        headers_lower = {str(k).strip().lower(): str(v).strip().lower() for k, v in headers.items()}

        is_http_blocked = status_code in (403, 429, 503)
        if is_http_blocked:
            indicators.append(f"HTTP {status_code} blocking response status")

        # Header inspections
        waf_provider = "UNKNOWN"
        if "cf-ray" in headers_lower:
            indicators.append("Cloudflare cf-ray tracking header present")
            waf_provider = "Cloudflare"
        if "cf-mitigated" in headers_lower:
            indicators.append(f"Cloudflare cf-mitigated header: {headers_lower['cf-mitigated']}")
            waf_provider = "Cloudflare"
        if "x-amz-cf-id" in headers_lower:
            indicators.append("AWS CloudFront header present")
            waf_provider = "AWS CloudFront"
        if "x-datadome" in headers_lower or "datadome" in headers_lower:
            indicators.append("DataDome protection header present")
            waf_provider = "DataDome"
        if "x-px" in headers_lower:
            indicators.append("PerimeterX protection header present")
            waf_provider = "PerimeterX"

        server_hdr = headers_lower.get("server", "")
        if "cloudflare" in server_hdr:
            indicators.append("Server header identifies Cloudflare")
            if waf_provider == "UNKNOWN":
                waf_provider = "Cloudflare"
        elif "akamai" in server_hdr:
            indicators.append("Server header identifies Akamai")
            if waf_provider == "UNKNOWN":
                waf_provider = "Akamai"

        # HTML challenge body signatures
        has_challenge_body = False
        if raw_html:
            html_lower = raw_html.lower()
            words_count = len(html_lower.split())
            for kw in cls.CHALLENGE_KEYWORDS:
                if kw in html_lower:
                    if kw in ("recaptcha", "hcaptcha"):
                        # If page returned 200 OK with substantial content (> 200 words), this is an embedded form verification element, not an access block
                        if status_code == 200 and words_count > 200:
                            indicators.append(f"Observable embedded form protection in HTML: '{kw}'")
                            continue
                    indicators.append(f"Observable challenge signature in HTML: '{kw}'")
                    has_challenge_body = True

        waf_detected = bool(indicators)
        blocked = is_http_blocked or has_challenge_body

        barrier_type = None
        if has_challenge_body:
            barrier_type = "BOT_CHALLENGE"
        elif status_code == 429:
            barrier_type = "RATE_LIMIT"
        elif status_code in (403, 503):
            barrier_type = "WAF_HTTP_STATUS"

        status = RetrievalReadinessStatus.BLOCKED if blocked else RetrievalReadinessStatus.ALLOWED
        final_provider = waf_provider if (waf_provider != "UNKNOWN" or blocked) else None

        return WafChallengeEvidence(
            is_blocked=blocked,
            status_code=status_code,
            status=status,
            barrier_type=barrier_type,
            waf_or_challenge_detected=waf_detected,
            waf_provider=final_provider,
            challenge_detected=has_challenge_body,
            challenge_indicators=indicators,
        )

    @classmethod
    def parse_snippet_controls(
        cls,
        raw_html: Optional[str] = None,
        response_headers: Optional[Dict[str, Any]] = None,
    ) -> SnippetControlEvidence:
        """
        Extract snippet control directives from HTML meta tags, data-nosnippet attributes,
        and X-Robots-Tag response headers.
        """
        evidence = SnippetControlEvidence()
        nosnippet_sources: List[str] = []
        max_snippet_val: Optional[int] = None
        max_snippet_src: Optional[str] = None

        # 1. Parse meta tags from HTML
        if raw_html:
            try:
                soup = BeautifulSoup(raw_html, "html.parser")

                # Check <meta name="..." content="..."> for robots or specific bots
                for meta in soup.find_all("meta"):
                    name_attr = str(meta.get("name", "")).strip().lower()
                    if name_attr in ("robots", "googlebot", "bingbot", "oai-searchbot", "perplexitybot", "claudebot"):
                        content = str(meta.get("content", "")).lower()
                        for part in content.split(","):
                            clean = part.strip()
                            if clean == "nosnippet":
                                nosnippet_sources.append(f"meta:{name_attr}")
                            elif clean.startswith("max-snippet:"):
                                val_str = clean.split(":", 1)[1].strip()
                                try:
                                    val_int = int(val_str)
                                    if max_snippet_val is None or val_int < max_snippet_val:
                                        max_snippet_val = val_int
                                        max_snippet_src = f"meta:{name_attr}"
                                except ValueError:
                                    pass
                            elif clean.startswith("max-image-preview:"):
                                evidence.max_image_preview = clean.split(":", 1)[1].strip()
                            elif clean.startswith("max-video-preview:"):
                                try:
                                    evidence.max_video_preview = int(clean.split(":", 1)[1].strip())
                                except ValueError:
                                    pass

                # Check data-nosnippet attributes
                data_nosnippet_nodes = soup.find_all(attrs={"data-nosnippet": True})
                if data_nosnippet_nodes:
                    evidence.has_data_nosnippet = True
                    evidence.data_nosnippet_count = len(data_nosnippet_nodes)
                    sample_selectors: List[str] = []
                    for el in data_nosnippet_nodes[:5]:
                        tag_name = el.name
                        cls_names = el.get("class", [])
                        if isinstance(cls_names, list) and cls_names:
                            sel = f"{tag_name}.{'.'.join(cls_names[:2])}"
                        elif el.get("id"):
                            sel = f"{tag_name}#{el.get('id')}"
                        else:
                            sel = f"<{tag_name} data-nosnippet>"
                        sample_selectors.append(sel)
                    evidence.data_nosnippet_sample_selectors = sample_selectors

            except Exception:
                pass

        # 2. Parse X-Robots-Tag from HTTP headers
        headers = response_headers or {}
        raw_x_tags: List[str] = []
        if isinstance(headers, dict):
            for k, v in headers.items():
                if str(k).strip().lower() == "x-robots-tag":
                    if isinstance(v, list):
                        raw_x_tags.extend(str(item) for item in v if item)
                    elif isinstance(v, str) and v:
                        raw_x_tags.append(v)
        elif isinstance(headers, list):
            for k, v in headers:
                if str(k).strip().lower() == "x-robots-tag" and v:
                    raw_x_tags.append(str(v))

        for x_val in raw_x_tags:
            for part in x_val.split(","):
                clean = part.strip().lower()
                # Check for "googlebot: nosnippet" or generic "nosnippet"
                if "nosnippet" in clean:
                    nosnippet_sources.append("header:x-robots-tag")
                elif "max-snippet:" in clean:
                    idx = clean.find("max-snippet:")
                    val_str = clean[idx + len("max-snippet:"):].strip().split()[0]
                    try:
                        val_int = int(val_str)
                        if max_snippet_val is None or val_int < max_snippet_val:
                            max_snippet_val = val_int
                            max_snippet_src = "header:x-robots-tag"
                    except ValueError:
                        pass
                elif "max-image-preview:" in clean:
                    idx = clean.find("max-image-preview:")
                    evidence.max_image_preview = clean[idx + len("max-image-preview:"):].strip().split()[0]
                elif "max-video-preview:" in clean:
                    idx = clean.find("max-video-preview:")
                    try:
                        evidence.max_video_preview = int(clean[idx + len("max-video-preview:"):].strip().split()[0])
                    except ValueError:
                        pass

        evidence.has_nosnippet = bool(nosnippet_sources)
        evidence.nosnippet_sources = list(dict.fromkeys(nosnippet_sources))
        evidence.max_snippet = max_snippet_val
        evidence.max_snippet_source = max_snippet_src

        # Determine overall snippet control status
        if evidence.has_nosnippet or (evidence.max_snippet is not None and evidence.max_snippet == 0):
            evidence.status = SnippetControlStatus.NOSNIPPET
        elif evidence.max_snippet is not None:
            evidence.status = SnippetControlStatus.MAX_SNIPPET
        else:
            evidence.status = SnippetControlStatus.ALLOWED

        return evidence

    @classmethod
    def evaluate_content_availability(
        cls,
        raw_html: Optional[str] = None,
        rendered_html: Optional[str] = None,
    ) -> ContentAvailabilityEvidence:
        """
        Compares raw static HTML with rendered HTML to evaluate factual text content availability.
        Reports facts without speculating whether AI engines can or cannot execute JS.
        """
        raw_words = 0
        rendered_words = 0
        raw_available = bool(raw_html and raw_html.strip())
        rendered_available = bool(rendered_html and rendered_html.strip())

        def _count_words(html_text: str) -> int:
            try:
                soup = BeautifulSoup(html_text, "html.parser")
                for s in soup(["script", "style", "noscript", "svg"]):
                    s.decompose()
                text = soup.get_text(separator=" ", strip=True)
                tokens = [w for w in text.split() if len(w) > 1]
                return len(tokens)
            except Exception:
                return 0

        if raw_available:
            raw_words = _count_words(raw_html or "")
        if rendered_available:
            rendered_words = _count_words(rendered_html or "")

        delta = rendered_words - raw_words if (raw_available and rendered_available) else 0

        # Factual assessment of difference
        significant_diff = False
        impact_summary = ""

        if raw_available and rendered_available:
            # If rendered text has noticeably more text (>50 words or >25% higher)
            if delta > 50 and (raw_words == 0 or delta / max(raw_words, 1) > 0.25):
                significant_diff = True
                impact_summary = (
                    f"Rendered HTML yields {delta} additional words ({rendered_words} vs {raw_words} raw). "
                    "Some retrieval systems may have reduced access to this content if they do not execute client-side JavaScript."
                )
            elif delta < -50:
                impact_summary = f"Rendered DOM contains fewer text words ({rendered_words} vs {raw_words} raw)."
            else:
                impact_summary = f"Raw and rendered HTML text counts are aligned ({raw_words} raw vs {rendered_words} rendered)."
        elif raw_available:
            impact_summary = f"Static HTML observed ({raw_words} words); browser DOM was not rendered in this pass."
        else:
            impact_summary = "HTML content unavailable."

        return ContentAvailabilityEvidence(
            raw_html_available=raw_available,
            rendered_html_available=rendered_available,
            raw_word_count=raw_words,
            rendered_word_count=rendered_words,
            word_count_delta=delta,
            significant_content_difference=significant_diff,
            js_rendering_impact=impact_summary,
        )

    @classmethod
    def evaluate_indexability_interaction(
        cls,
        url: str,
        http_status: int,
        raw_html: Optional[str] = None,
        response_headers: Optional[Dict[str, Any]] = None,
    ) -> IndexabilityInteractionEvidence:
        """
        Evaluate canonicalization and noindex interactions.
        """
        meta_directives = IndexabilityEngine.parse_meta_robots(raw_html)
        x_directives = IndexabilityEngine.parse_x_robots_tag(response_headers)
        canonical_target = IndexabilityEngine.parse_canonical_tag(raw_html, url)

        has_noindex = any(d in IndexabilityEngine.NOINDEX_DIRECTIVES for d in meta_directives + x_directives)
        has_nofollow = any("nofollow" in d for d in meta_directives + x_directives)

        noindex_sources: List[str] = []
        if any(d in IndexabilityEngine.NOINDEX_DIRECTIVES for d in meta_directives):
            noindex_sources.append("meta:robots")
        if any(d in IndexabilityEngine.NOINDEX_DIRECTIVES for d in x_directives):
            noindex_sources.append("header:x-robots-tag")

        canonical_signal = "MISSING"
        canonical_conflict = False
        summary_parts: List[str] = []

        if canonical_target:
            norm_url = UrlNormalizer.normalize_for_crawl(url)
            norm_target = UrlNormalizer.normalize_for_crawl(canonical_target)
            if norm_url == norm_target:
                canonical_signal = "SELF_REFERENCING"
                summary_parts.append("Self-referencing canonical tag declared.")
            elif UrlNormalizer.is_same_domain(url, canonical_target):
                canonical_signal = "CANONICALIZED_ELSEWHERE"
                summary_parts.append(f"Page canonicalizes to internal URL: {canonical_target}.")
            else:
                canonical_signal = "CROSS_DOMAIN"
                summary_parts.append(f"Page canonicalizes to external domain: {canonical_target}.")
        else:
            summary_parts.append("No canonical URL declared.")

        if has_noindex:
            summary_parts.append("Page declares noindex directive.")
            if canonical_signal == "SELF_REFERENCING":
                canonical_conflict = True
                summary_parts.append("Interaction: noindex declared alongside self-referencing canonical.")
            elif canonical_signal == "CANONICALIZED_ELSEWHERE":
                summary_parts.append("Interaction: page declares both noindex and a distinct canonical target.")

        idx_status, _ = IndexabilityEngine.evaluate_indexability(
            http_status=http_status,
            meta_directives=meta_directives,
            x_robots_directives=x_directives,
            has_content=bool(raw_html and raw_html.strip()),
        )

        return IndexabilityInteractionEvidence(
            indexability_status=idx_status,
            has_noindex=has_noindex,
            noindex_sources=noindex_sources,
            has_nofollow=has_nofollow,
            canonical_url=canonical_target,
            canonical_signal=canonical_signal,
            canonical_conflict=canonical_conflict,
            interaction_summary=" ".join(summary_parts),
        )

    @classmethod
    def evaluate_page(
        cls,
        url: str,
        status_code: int = 200,
        raw_html: Optional[str] = None,
        rendered_html: Optional[str] = None,
        response_headers: Optional[Dict[str, Any]] = None,
        robots_content: Optional[str] = None,
        robots_found: bool = True,
        bot_matrix: Optional[Any] = None,
        target_path: Optional[str] = None,
        core_bots_only: bool = True,
    ) -> RetrievalReadinessEvidence:
        """
        Evaluate full AI and search retrieval readiness for a single page.
        Zero redundant HTTP requests. Reuses existing crawl/DOM evidence.
        """
        parsed = urlparse(url)
        path = target_path or (parsed.path or "/")
        if parsed.query:
            path = f"{path}?{parsed.query}"

        # 1. Access Barriers (WAF & HTTP)
        waf = cls.detect_waf_and_challenges(
            status_code=status_code,
            response_headers=response_headers,
            raw_html=raw_html,
        )

        # 2. Snippet Controls
        snippets = cls.parse_snippet_controls(
            raw_html=raw_html,
            response_headers=response_headers,
        )

        # 3. Content Availability
        content_avail = cls.evaluate_content_availability(
            raw_html=raw_html,
            rendered_html=rendered_html,
        )

        # 4. Indexability & Canonical Interactions
        index_inter = cls.evaluate_indexability_interaction(
            url=url,
            http_status=status_code,
            raw_html=raw_html,
            response_headers=response_headers,
        )

        # 5. Robots.txt evaluation
        matrix_engine = BotMatrixEngine()
        blocks = matrix_engine.parse_robots_txt(robots_content or "") if (robots_found and robots_content) else []
        bot_matrix_entries = {e.bot_name: e for e in bot_matrix.entries} if (bot_matrix and hasattr(bot_matrix, "entries")) else {}

        selected_bots = CORE_RETRIEVAL_BOTS if core_bots_only else list(MASTER_BOT_REGISTRY.keys())
        bot_records: Dict[str, BotRetrievalAccessRecord] = {}

        search_allowed = 0
        training_allowed = 0
        user_fetch_allowed = 0
        blocked_waf_count = 0

        for b_name in selected_bots:
            meta = MASTER_BOT_REGISTRY.get(b_name, {})
            cat_label = meta.get("category_label", "Search Engine")
            company = meta.get("company", meta.get("engine", "Web"))
            purpose_raw = meta.get("purpose", "search_index")
            purpose = BotPurpose(purpose_raw) if purpose_raw in [e.value for e in BotPurpose] else BotPurpose.SEARCH_INDEX
            honors_robots = meta.get("honors_robots_txt", True)
            is_control_token = meta.get("is_control_token_only", False)

            notes: List[str] = []

            # Evaluate robots.txt status
            if b_name in bot_matrix_entries:
                bm_entry = bot_matrix_entries[b_name]
                robots_status = RetrievalReadinessStatus.ALLOWED if bm_entry.status == "ALLOWED" else RetrievalReadinessStatus.DISALLOWED
                rule_src = bm_entry.rule_source
                matched_dir = bm_entry.matched_directive
                line_no = bm_entry.line_number
                raw_pat = bm_entry.raw_pattern
                if matched_dir:
                    notes.append(f"robots.txt directive matched: {matched_dir} (line {line_no})")
                elif rule_src == "default_allow":
                    notes.append("Permitted by default allow.")
            elif not robots_found:
                robots_status = RetrievalReadinessStatus.ALLOWED
                rule_src = "default_allow"
                matched_dir = None
                line_no = None
                raw_pat = None
                notes.append("No robots.txt detected; default allow applied per RFC 9309.")
            elif not honors_robots:
                # E.g. Perplexity-User (real-time user action)
                robots_status = RetrievalReadinessStatus.NOT_APPLICABLE
                rule_src = "user_action_bypass"
                matched_dir = None
                line_no = None
                raw_pat = None
                notes.append("User-initiated on-demand fetcher; operates independently of robots.txt.")
            else:
                st_str, rule_src, matched_dir, line_no, raw_pat = matrix_engine.evaluate_bot(
                    b_name, blocks, path
                )
                robots_status = RetrievalReadinessStatus.ALLOWED if st_str == "ALLOWED" else RetrievalReadinessStatus.DISALLOWED
                if matched_dir:
                    notes.append(f"robots.txt directive matched: {matched_dir} (line {line_no})")

            # Determine bot-specific snippet control
            if purpose == BotPurpose.AI_TRAINING or is_control_token:
                b_snippet_status = SnippetControlStatus.NOT_APPLICABLE
            elif snippets.has_nosnippet:
                b_snippet_status = SnippetControlStatus.NOSNIPPET
            elif snippets.max_snippet is not None:
                b_snippet_status = SnippetControlStatus.MAX_SNIPPET
            else:
                b_snippet_status = SnippetControlStatus.ALLOWED

            # Determine network/WAF status
            if waf.is_blocked:
                waf_status = RetrievalReadinessStatus.BLOCKED
                blocked_waf_count += 1
                notes.append(f"Network/WAF access blocked (HTTP {waf.status_code})")
            else:
                waf_status = RetrievalReadinessStatus.ALLOWED

            # Compute effective status for this bot
            if waf_status == RetrievalReadinessStatus.BLOCKED:
                eff_status = RetrievalReadinessStatus.BLOCKED
            elif robots_status == RetrievalReadinessStatus.DISALLOWED:
                eff_status = RetrievalReadinessStatus.DISALLOWED
            elif index_inter.has_noindex and purpose in (BotPurpose.SEARCH_INDEX,):
                # Search engine cannot index the page due to noindex
                eff_status = RetrievalReadinessStatus.DISALLOWED
                notes.append("Page declares noindex, preventing search indexation and citation surfacing.")
            elif robots_status == RetrievalReadinessStatus.ALLOWED or robots_status == RetrievalReadinessStatus.NOT_APPLICABLE:
                eff_status = RetrievalReadinessStatus.ALLOWED
            else:
                eff_status = RetrievalReadinessStatus.UNKNOWN

            # Count permitted bots
            if eff_status == RetrievalReadinessStatus.ALLOWED:
                if purpose == BotPurpose.SEARCH_INDEX:
                    search_allowed += 1
                elif purpose == BotPurpose.AI_TRAINING:
                    training_allowed += 1
                elif purpose == BotPurpose.USER_FETCH:
                    user_fetch_allowed += 1

            record = BotRetrievalAccessRecord(
                bot_name=b_name,
                company=company,
                purpose=purpose,
                category_label=cat_label,
                robots_access=robots_status,
                indexability=index_inter.indexability_status,
                snippet_control=b_snippet_status,
                waf_network_status=waf_status,
                effective_status=eff_status,
                rule_source=rule_src,
                matched_directive=matched_dir,
                line_number=line_no,
                raw_pattern=raw_pat,
                notes=notes,
            )
            bot_records[b_name] = record

        # Generate factual observations
        facts: List[str] = []
        analyses: List[str] = []

        # Access Facts
        facts.append(f"HTTP Status: {status_code}")
        if waf.waf_or_challenge_detected:
            facts.append(f"WAF / Challenge Indicators: {', '.join(waf.challenge_indicators)}")
        else:
            facts.append("No active WAF or automated challenge barriers observed.")

        # Snippet Facts
        if snippets.has_nosnippet:
            facts.append(f"nosnippet directive present in: {', '.join(snippets.nosnippet_sources)}")
        if snippets.max_snippet is not None:
            facts.append(f"max-snippet threshold set to {snippets.max_snippet} characters ({snippets.max_snippet_source})")
        if snippets.has_data_nosnippet:
            facts.append(f"data-nosnippet attribute observed on {snippets.data_nosnippet_count} HTML element(s)")

        # Content Availability Facts
        if content_avail.raw_html_available:
            facts.append(f"Static HTML contains {content_avail.raw_word_count} words.")
        if content_avail.rendered_html_available:
            facts.append(f"Rendered browser DOM contains {content_avail.rendered_word_count} words (delta: {content_avail.word_count_delta:+d} words).")

        # Analyses
        if waf.is_blocked:
            analyses.append("HTTP or challenge blocking prevents automated retrieval across all crawlers.")
        if index_inter.has_noindex:
            analyses.append("noindex directive precludes inclusion in standard search indexes and search-driven citations.")
        if snippets.has_nosnippet:
            analyses.append("nosnippet directive instructs search and citation engines not to display extractable text snippets.")
        if content_avail.significant_content_difference:
            analyses.append(content_avail.js_rendering_impact)
        if index_inter.canonical_signal == "CANONICALIZED_ELSEWHERE":
            analyses.append(f"Search retrieval systems consolidating canonical targets will attribute content to {index_inter.canonical_url}.")

        return RetrievalReadinessEvidence(
            url=url,
            engine_source="retrieval_readiness_engine",
            http_status=status_code,
            content_availability=content_avail,
            waf_challenge=waf,
            snippet_controls=snippets,
            indexability_interaction=index_inter,
            bot_access_records=bot_records,
            total_bots_evaluated=len(bot_records),
            search_index_allowed_count=search_allowed,
            ai_training_allowed_count=training_allowed,
            user_fetch_allowed_count=user_fetch_allowed,
            blocked_by_waf_count=blocked_waf_count,
            facts=facts,
            analyses=analyses,
        )

    @classmethod
    def evaluate_site(
        cls,
        site_crawl: SiteCrawlResult,
        robots_content: Optional[str] = None,
        robots_found: bool = True,
    ) -> SiteRetrievalReadinessIntelligence:
        """
        Evaluate site-wide multi-page AI and search retrieval readiness across CrawlRecords.
        Preserves partial-crawl semantics and performs zero extra network calls.
        """
        records = site_crawl.crawl_records
        total_pages = len(records)
        is_partial = site_crawl.completeness_status != "CRAWL_COMPLETE" or site_crawl.remaining_frontier > 0

        disclaimer = ""
        if is_partial:
            disclaimer = (
                f"Evaluation covers {total_pages} crawled pages; "
                f"{site_crawl.remaining_frontier} remaining frontier URLs were unvisited within crawl budget."
            )

        pages_with_waf: List[str] = []
        pages_requiring_js: List[str] = []
        pages_nosnippet: List[str] = []
        pages_data_nosnippet: List[str] = []
        pages_noindex: List[str] = []
        pages_canonical_conflicts: List[str] = []
        bot_disallowed_counts: Dict[str, int] = {}
        page_readiness: Dict[str, RetrievalReadinessEvidence] = {}

        for rec in records:
            if getattr(rec, "retrieval_readiness", None) is not None:
                ev = rec.retrieval_readiness
            else:
                ev = cls.evaluate_page(
                    url=rec.url,
                    status_code=rec.status_code,
                    raw_html=rec.raw_html,
                    rendered_html=None,  # Browser DOM if individual record tracked it
                    response_headers=rec.response_headers,
                    robots_content=robots_content,
                    robots_found=robots_found,
                    core_bots_only=True,
                )
            page_readiness[rec.url] = ev

            if ev.waf_challenge.is_blocked:
                pages_with_waf.append(rec.url)
            if ev.content_availability.significant_content_difference:
                pages_requiring_js.append(rec.url)
            if ev.snippet_controls.has_nosnippet:
                pages_nosnippet.append(rec.url)
            if ev.snippet_controls.has_data_nosnippet:
                pages_data_nosnippet.append(rec.url)
            if ev.indexability_interaction.has_noindex:
                pages_noindex.append(rec.url)
            if ev.indexability_interaction.canonical_conflict:
                pages_canonical_conflicts.append(rec.url)

            for b_name, b_rec in ev.bot_access_records.items():
                if b_rec.effective_status == RetrievalReadinessStatus.DISALLOWED:
                    bot_disallowed_counts[b_name] = bot_disallowed_counts.get(b_name, 0) + 1

        facts: List[str] = [
            f"Evaluated {total_pages} crawled pages for AI and search retrieval readiness.",
            f"Pages with observable WAF / access blocking: {len(pages_with_waf)}",
            f"Pages with nosnippet directives: {len(pages_nosnippet)}",
            f"Pages with data-nosnippet attributes: {len(pages_data_nosnippet)}",
            f"Pages with noindex directives: {len(pages_noindex)}",
            f"Pages with canonical / indexability conflicts: {len(pages_canonical_conflicts)}",
        ]

        analyses: List[str] = []
        if pages_with_waf:
            analyses.append(f"{len(pages_with_waf)} page(s) exhibited HTTP or WAF blocking during crawl.")
        if pages_noindex:
            analyses.append(f"{len(pages_noindex)} page(s) declare noindex, excluding them from search and AI citation indexes.")
        if pages_nosnippet:
            analyses.append(f"{len(pages_nosnippet)} page(s) suppress snippet extraction via nosnippet.")

        intel = SiteRetrievalReadinessIntelligence(
            status="success",
            total_pages_evaluated=total_pages,
            is_partial_crawl=is_partial,
            completeness_disclaimer=disclaimer,
            pages_with_waf_challenge=pages_with_waf,
            pages_requiring_js=pages_requiring_js,
            pages_with_nosnippet=pages_nosnippet,
            pages_with_data_nosnippet=pages_data_nosnippet,
            pages_with_noindex=pages_noindex,
            pages_with_canonical_conflicts=pages_canonical_conflicts,
            bot_disallowed_counts=bot_disallowed_counts,
            page_readiness_evidence=page_readiness,
            facts=facts,
            analyses=analyses,
        )

        site_crawl.retrieval_readiness_intelligence = intel
        return intel
