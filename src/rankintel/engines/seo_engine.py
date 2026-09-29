"""
SEO Engine Adapter — Powered by advertools and standards-compliant crawlers.
Handles RFC-compliant robots.txt, sitemaps, and static DOM analysis.
"""
from __future__ import annotations
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional

from rankintel.references.ai_crawlers import AI_SEARCH_BOTS, AI_TRAINING_BOTS
from rankintel.references.schema_registry import DEPRECATED_OR_RESTRICTED_SCHEMAS
from rankintel.models.schema import (
    BotStatus,
    RobotsEvidence,
    OnPageEvidence,
    SchemaEvidence,
    EngineResult
)

try:
    import advertools as adv
    HAS_ADVERTOOLS = True
except ImportError:
    HAS_ADVERTOOLS = False

class SeoEngine:
    """Specialized engine for traditional technical SEO, RFC robots, and sitemap crawling."""

    def __init__(self, headers: Optional[dict] = None):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def audit_robots_txt(self, base_url: str) -> RobotsEvidence:
        """Audit robots.txt with RFC-compliant rules."""
        robots_url = urljoin(base_url, "/robots.txt")
        evidence = RobotsEvidence(robots_url=robots_url, engine_source="advertools_rfc" if HAS_ADVERTOOLS else "urllib_robotparser")

        all_bots = {**AI_SEARCH_BOTS, **AI_TRAINING_BOTS}
        bot_names = list(all_bots.keys())

        try:
            resp = requests.get(robots_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                evidence.found = False
                return evidence

            evidence.found = True
            content = resp.text

            # Extract sitemaps declared in robots.txt
            for line in content.splitlines():
                if line.strip().lower().startswith("sitemap:"):
                    s_url = line.split(":", 1)[1].strip()
                    if s_url:
                        evidence.sitemaps.append(s_url)

            # Test using advertools if available
            if HAS_ADVERTOOLS:
                try:
                    df = adv.robotstxt_test(
                        robotstxt_url=robots_url,
                        user_agents=bot_names,
                        urls=["/"]
                    )
                    for _, row in df.iterrows():
                        bot = str(row["user_agent"])
                        can_fetch = bool(row["can_fetch"])
                        category = "search" if bot in AI_SEARCH_BOTS else "training"
                        info = all_bots.get(bot, {})
                        role = info.get("role") if category == "search" else info.get("purpose", "")

                        evidence.bot_access[bot] = BotStatus(
                            bot=bot,
                            status="ALLOWED" if can_fetch else "BLOCKED",
                            category=category,
                            engine=info.get("engine", info.get("company", "")),
                            role_or_purpose=role,
                            via_wildcard=False
                        )
                    return evidence
                except Exception:
                    pass  # Fallback to urllib.robotparser

            # Fallback to standard library RobotFileParser
            from urllib.robotparser import RobotFileParser
            rp = RobotFileParser()
            rp.parse(content.splitlines())

            for bot, info in all_bots.items():
                can_fetch = rp.can_fetch(bot, "/")
                category = "search" if bot in AI_SEARCH_BOTS else "training"
                role = info.get("role") if category == "search" else info.get("purpose", "")

                evidence.bot_access[bot] = BotStatus(
                    bot=bot,
                    status="ALLOWED" if can_fetch else "BLOCKED",
                    category=category,
                    engine=info.get("engine", info.get("company", "")),
                    role_or_purpose=role,
                    via_wildcard=False
                )

        except Exception:
            evidence.found = False

        return evidence

    def audit_static_page(self, url: str) -> tuple[OnPageEvidence, SchemaEvidence]:
        """Audit static HTML page using HTTP request and BeautifulSoup."""
        on_page = OnPageEvidence(url=url, engine_source="advertools_static_http")
        schema_ev = SchemaEvidence(engine_source="advertools_static_http")

        start = time.time()
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            on_page.response_time_sec = round(time.time() - start, 2)
            on_page.status_code = resp.status_code
            on_page.is_redirect = len(resp.history) > 0

            if resp.status_code != 200:
                return on_page, schema_ev

            resp.encoding = 'utf-8' if not resp.encoding or resp.encoding.lower() == 'iso-8859-1' else resp.encoding
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Title
            t_tag = soup.find('title')
            title = t_tag.text.strip() if t_tag else ""
            on_page.title = title
            on_page.title_length = len(title)

            # Meta Description
            m_tag = soup.find('meta', attrs={'name': 'description'})
            m_desc = m_tag['content'].strip() if m_tag and m_tag.get('content') else ""
            on_page.meta_description = m_desc
            on_page.meta_desc_length = len(m_desc)

            # Canonical
            c_tag = soup.find('link', attrs={'rel': 'canonical'})
            if c_tag and c_tag.get('href'):
                on_page.canonical_url = c_tag['href'].strip()

            # Headings
            on_page.h1_text = [h1.get_text().strip() for h1 in soup.find_all('h1') if h1.get_text().strip()]
            on_page.h1_count = len(on_page.h1_text)

            on_page.h2_text = [h2.get_text().strip() for h2 in soup.find_all('h2') if h2.get_text().strip()]
            on_page.h2_count = len(on_page.h2_text)

            on_page.h3_text = [h3.get_text().strip() for h3 in soup.find_all('h3') if h3.get_text().strip()]
            on_page.h3_count = len(on_page.h3_text)

            # Images
            imgs = soup.find_all('img')
            on_page.total_images = len(imgs)
            on_page.images_with_alt = len([img for img in imgs if img.get('alt') and img.get('alt').strip()])

            # Word count
            for s in soup(["script", "style", "nav", "footer"]):
                s.extract()
            text = soup.get_text(separator=' ')
            on_page.word_count = len(text.split())

            # Schema detection from static DOM
            schema_tags = soup.find_all('script', type='application/ld+json')
            schema_ev.blocks_count = len(schema_tags)
            import json

            detected = []
            deprecated = []
            for tag in schema_tags:
                try:
                    c = tag.string if tag.string else tag.text
                    if not c:
                        continue
                    data = json.loads(c, strict=False)
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        if "@graph" in data and isinstance(data["@graph"], list):
                            items = data["@graph"]
                        else:
                            items = [data]
                    for item in items:
                        t = item.get("@type")
                        if t:
                            if isinstance(t, list):
                                for sub_t in t:
                                    detected.append(str(sub_t))
                            else:
                                detected.append(str(t))
                except Exception as e:
                    schema_ev.validation_issues.append(f"Malformed JSON-LD block: {e}")

            for s in set(detected):
                if s in DEPRECATED_OR_RESTRICTED_SCHEMAS:
                    deprecated.append(s)

            schema_ev.detected_types = list(set(detected))
            schema_ev.deprecated_types_detected = list(set(deprecated))

        except Exception as e:
            on_page.status_code = 0
            on_page.response_time_sec = round(time.time() - start, 2)

        return on_page, schema_ev

    def execute(self, url: str) -> EngineResult:
        """Run complete SEO engine pass."""
        t0 = time.time()
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        on_page, schema_data = self.audit_static_page(url)
        robots = self.audit_robots_txt(base_url)

        return EngineResult(
            engine_name="advertools_seo",
            status="success" if on_page.status_code == 200 else "error",
            execution_time_sec=round(time.time() - t0, 2),
            on_page=on_page,
            robots=robots,
            schema_data=schema_data
        )
