"""
Bot Access Matrix Engine — RFC 9309 Robots.txt Parser & Crawler Access Triangulator.

Evaluates robots.txt access across 4 distinct crawler categories:
1. Traditional Search Engines (Googlebot, Bingbot, Slurp, etc.)
2. AI Search & Citation Agents (OAI-SearchBot, PerplexityBot, Claude-SearchBot)
3. AI Model Training Crawlers (GPTBot, ClaudeBot, Google-Extended, CCBot, etc.)
4. Platform / OS Assistants (Applebot)
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from rankintel.references.ai_crawlers import MASTER_BOT_REGISTRY
from rankintel.models.schema import (
    BotMatrixEntry,
    BotMatrixReport,
    BotAccessStatus,
    BotCategory,
)


class DirectiveRule:
    """Represents a single Allow or Disallow rule in robots.txt."""
    def __init__(self, directive: str, pattern: str, line_number: int):
        self.directive = directive.lower().strip()  # 'allow' or 'disallow'
        self.pattern = pattern.strip()
        self.line_number = line_number
        self.pattern_len = len(self.pattern)
        self.regex = self._compile_pattern(self.pattern)

    @staticmethod
    def _compile_pattern(pat: str) -> Optional[re.Pattern]:
        if not pat:
            return None
        # Escape regex special characters except * and $
        escaped = ""
        i = 0
        while i < len(pat):
            ch = pat[i]
            if ch == "*":
                escaped += ".*"
            elif ch == "$":
                if i == len(pat) - 1:
                    escaped += "$"
                else:
                    escaped += r"\$"
            else:
                escaped += re.escape(ch)
            i += 1
        
        # In robots.txt, path matches from the beginning
        if not escaped.startswith("^"):
            escaped = "^" + escaped
        try:
            return re.compile(escaped)
        except re.error:
            return None

    def matches(self, path: str) -> bool:
        if not self.pattern:
            return False
        if self.regex:
            return bool(self.regex.match(path))
        return path.startswith(self.pattern)


class UserAgentBlock:
    """Represents a block of directives for one or more user agents."""
    def __init__(self, user_agents: List[str]):
        self.user_agents = [ua.lower().strip() for ua in user_agents]
        self.rules: List[DirectiveRule] = []

    def applies_to(self, bot_name: str) -> bool:
        bot_lower = bot_name.lower().strip()
        for ua in self.user_agents:
            if ua == "*" or ua == bot_lower or ua in bot_lower:
                return True
        return False

    def specificity_score(self, bot_name: str) -> int:
        bot_lower = bot_name.lower().strip()
        best = -1
        for ua in self.user_agents:
            if ua == bot_lower:
                return 1000 + len(ua)
            elif ua in bot_lower and ua != "*":
                best = max(best, 100 + len(ua))
            elif ua == "*":
                best = max(best, 1)
        return best


class BotMatrixEngine:
    """
    RFC 9309 compliant Bot Access Matrix evaluator.
    Categorizes search, citation, and training bots, determining
    exact indexing status and business impact.
    """

    def __init__(self, registry: Optional[Dict[str, Dict[str, Any]]] = None):
        self.registry = registry or MASTER_BOT_REGISTRY

    def parse_robots_txt(self, content: str) -> List[UserAgentBlock]:
        """
        Parse raw robots.txt content into UserAgentBlocks per RFC 9309.
        Handles multi-agent blocks and comments cleanly.
        """
        lines = content.splitlines()
        blocks: List[UserAgentBlock] = []
        current_uas: List[str] = []
        current_rules: List[DirectiveRule] = []

        def flush_current():
            nonlocal current_uas, current_rules
            if current_uas:
                block = UserAgentBlock(current_uas)
                block.rules = list(current_rules)
                blocks.append(block)
                current_uas = []
                current_rules = []

        for line_num, raw_line in enumerate(lines, start=1):
            # Strip comments
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            if ":" not in line:
                continue

            field, val = line.split(":", 1)
            field = field.strip().lower()
            val = val.strip()

            if field == "user-agent":
                if current_rules:
                    # Previous block has rules and finished; flush it
                    flush_current()
                current_uas.append(val)
            elif field in ("allow", "disallow"):
                if current_uas:
                    current_rules.append(DirectiveRule(field, val, line_num))

        flush_current()
        return blocks

    def evaluate_bot(
        self,
        bot_name: str,
        blocks: List[UserAgentBlock],
        target_path: str = "/"
    ) -> Tuple[str, str, Optional[str], Optional[int], Optional[str]]:
        """
        Evaluate single bot against parsed blocks according to RFC 9309.
        Returns: (status, rule_source, matched_directive, line_number, raw_pattern)
        """
        # 1. Find the best matching UserAgentBlock
        best_block: Optional[UserAgentBlock] = None
        best_score = -1

        for block in blocks:
            score = block.specificity_score(bot_name)
            if score > best_score:
                best_score = score
                best_block = block

        # If no block matches (no specific and no * wildcard), default allow
        if not best_block or best_score <= 0:
            return BotAccessStatus.ALLOWED.value, "default_allow", None, None, None

        rule_source = "explicit" if best_score > 10 else "wildcard"

        # 2. Evaluate directives in the winning block
        matching_rules: List[DirectiveRule] = []
        for r in best_block.rules:
            # Empty Disallow: means allow all (RFC 9309 Section 2.2.1)
            if r.directive == "disallow" and not r.pattern:
                matching_rules.append(DirectiveRule("allow", "/", r.line_number))
            elif r.matches(target_path):
                matching_rules.append(r)

        if not matching_rules:
            # If nothing in the block matched this specific path, allowed by default
            return BotAccessStatus.ALLOWED.value, rule_source, None, None, None

        # Sort matching rules:
        # RFC 9309 § 2.2.2: The most specific rule (longest path) wins.
        # If lengths are equal, Allow takes precedence over Disallow.
        def rule_sort_key(rule: DirectiveRule):
            # Sort by pattern length descending, then Allow (1) > Disallow (0)
            is_allow = 1 if rule.directive == "allow" else 0
            return (rule.pattern_len, is_allow)

        matching_rules.sort(key=rule_sort_key, reverse=True)
        winner = matching_rules[0]

        status = BotAccessStatus.ALLOWED.value if winner.directive == "allow" else BotAccessStatus.DISALLOWED.value
        matched_str = f"{winner.directive.capitalize()}: {winner.pattern}" if winner.pattern else "Disallow: (empty)"

        return status, rule_source, matched_str, winner.line_number, winner.pattern

    def evaluate_robots_content(
        self,
        robots_content: str,
        target_path: str = "/",
        robots_url: str = "",
        robots_found: bool = True
    ) -> BotMatrixReport:
        """
        Evaluate full robots.txt content against all bots in MASTER_BOT_REGISTRY.
        """
        blocks = self.parse_robots_txt(robots_content) if robots_found else []

        entries: List[BotMatrixEntry] = []
        search_allowed = 0
        ai_search_allowed = 0
        ai_training_blocked = 0

        for bot_name, meta in self.registry.items():
            cat = meta.get("category", "search_engine")
            cat_label = meta.get("category_label", "Search Engine")
            engine_name = meta.get("engine", meta.get("company", "Web"))

            if not robots_found:
                status = BotAccessStatus.ALLOWED.value
                source = "default_allow"
                matched_dir = None
                line_no = None
                raw_pat = None
            else:
                status, source, matched_dir, line_no, raw_pat = self.evaluate_bot(bot_name, blocks, target_path)

            # Determine business impact
            if status == BotAccessStatus.ALLOWED.value:
                impact = meta.get("allowed_impact", f"Allowed to crawl for {engine_name}")
                if cat == "search_engine":
                    search_allowed += 1
                elif cat == "ai_search":
                    ai_search_allowed += 1
            else:
                impact = meta.get("disallowed_impact", f"Blocked from crawling for {engine_name}")
                if cat == "ai_training":
                    ai_training_blocked += 1

            entries.append(
                BotMatrixEntry(
                    bot_name=bot_name,
                    category=cat_label,
                    company_or_engine=engine_name,
                    status=status,
                    rule_source=source,
                    business_impact=impact,
                    matched_directive=matched_dir,
                    line_number=line_no,
                    raw_pattern=raw_pat,
                )
            )

        # Generate intelligent recommendations
        recommendations = self._generate_recommendations(entries, robots_found, robots_content)

        return BotMatrixReport(
            url=target_path,
            robots_url=robots_url,
            robots_found=robots_found,
            total_bots_evaluated=len(entries),
            search_allowed_count=search_allowed,
            ai_search_allowed_count=ai_search_allowed,
            ai_training_blocked_count=ai_training_blocked,
            entries=entries,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        entries: List[BotMatrixEntry],
        robots_found: bool,
        robots_content: str
    ) -> List[str]:
        """Generate tactical business recommendations based on bot evaluation."""
        recs: List[str] = []

        if not robots_found:
            recs.append("⚠️ No robots.txt detected (404/Missing). All search engines and AI scrapers have unrestricted access. Deploy a hardened robots.txt.")
            return recs

        # 1. Critical Search Engine Disallow Check
        blocked_search = [e for e in entries if e.category == "Search Engine" and e.status == BotAccessStatus.DISALLOWED.value]
        if blocked_search:
            names = ", ".join([e.bot_name for e in blocked_search])
            recs.append(f"🚨 CRITICAL: Core search engine bots ({names}) are disallowed! This causes de-indexing and catastrophic organic traffic loss.")

        # 2. AI Search & Citation Bot Check (OAI-SearchBot, PerplexityBot)
        blocked_ai_search = [e for e in entries if e.category == "AI Search Agent" and e.status == BotAccessStatus.DISALLOWED.value]
        if blocked_ai_search:
            names = ", ".join([e.bot_name for e in blocked_ai_search])
            recs.append(f"⚠️ WARNING: AI Search bots ({names}) are disallowed. Your content will be excluded from ChatGPT Search and Perplexity citations.")

        # 3. AI Training Scrapers check (GPTBot, ClaudeBot, etc.)
        allowed_scrapers = [e for e in entries if e.category == "AI Model Training" and e.status == BotAccessStatus.ALLOWED.value]
        if allowed_scrapers and not blocked_ai_search:
            names = ", ".join([e.bot_name for e in allowed_scrapers[:4]])
            recs.append(f"💡 RECOMMENDATION: Foundation training scrapers ({names}) are currently allowed. To protect proprietary content from AI training without harming search or GEO visibility, block GPTBot, ClaudeBot, and Google-Extended specifically.")

        # 4. Blanket Disallow Check
        if "disallow: /" in robots_content.lower() and "user-agent: *" in robots_content.lower():
            all_disallowed = all(e.status == BotAccessStatus.DISALLOWED.value for e in entries)
            if all_disallowed:
                recs.append("🚨 EMERGENCY: robots.txt contains a blanket 'Disallow: /' affecting all crawlers. Immediate remediation required to avoid total search delisting.")

        return recs

    async def evaluate_url(
        self,
        base_url: str,
        target_path: str = "/",
        client: Optional[httpx.AsyncClient] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None
    ) -> BotMatrixReport:
        """
        Asynchronously fetches robots.txt from base_url and evaluates the bot access matrix.
        """
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(origin, "/robots.txt")

        try:
            if client is not None:
                resp = await client.get(robots_url, timeout=10.0, follow_redirects=True)
            else:
                async with httpx.AsyncClient(transport=transport, timeout=10.0, follow_redirects=True) as local_client:
                    resp = await local_client.get(robots_url)

            if resp.status_code == 200:
                return self.evaluate_robots_content(resp.text, target_path=target_path, robots_url=robots_url, robots_found=True)
            else:
                return self.evaluate_robots_content("", target_path=target_path, robots_url=robots_url, robots_found=False)
        except Exception:
            return self.evaluate_robots_content("", target_path=target_path, robots_url=robots_url, robots_found=False)

    def evaluate_url_sync(
        self,
        base_url: str,
        target_path: str = "/"
    ) -> BotMatrixReport:
        """
        Synchronously fetches robots.txt from base_url and evaluates the bot access matrix.
        """
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(origin, "/robots.txt")

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(robots_url)
                if resp.status_code == 200:
                    return self.evaluate_robots_content(resp.text, target_path=target_path, robots_url=robots_url, robots_found=True)
                else:
                    return self.evaluate_robots_content("", target_path=target_path, robots_url=robots_url, robots_found=False)
        except Exception:
            return self.evaluate_robots_content("", target_path=target_path, robots_url=robots_url, robots_found=False)
