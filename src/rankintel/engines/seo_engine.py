"""
SEO Engine Adapter — Powered by advertools and standards-compliant crawlers.
Handles RFC-compliant robots.txt, sitemaps, and static DOM analysis.
"""
from __future__ import annotations
import time
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Tuple

from rankintel.references.ai_crawlers import AI_SEARCH_BOTS, AI_TRAINING_BOTS
from rankintel.references.schema_registry import DEPRECATED_OR_RESTRICTED_SCHEMAS
from rankintel.models.schema import (
    BotStatus,
    RobotsEvidence,
    OnPageEvidence,
    SchemaEvidence,
    EngineResult,
    PageSummary,
    SiteCrawlResult
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
                    if s_url and s_url not in evidence.sitemaps:
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
                    
                    # Extract sample URLs from sitemap if available
                    if evidence.sitemaps:
                        evidence.discovered_urls = self.extract_sitemap_urls(evidence.sitemaps[0], max_urls=25)
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

            if evidence.sitemaps:
                evidence.discovered_urls = self.extract_sitemap_urls(evidence.sitemaps[0], max_urls=25)

        except Exception:
            evidence.found = False

        return evidence

    def extract_sitemap_urls(self, sitemap_url: str, max_urls: int = 25) -> List[str]:
        """Extract URLs from XML sitemap using advertools or basic XML parsing."""
        discovered: List[str] = []
        if HAS_ADVERTOOLS:
            try:
                df = adv.sitemap_to_df(sitemap_url, recursive=False)
                if "loc" in df.columns:
                    locs = df["loc"].dropna().tolist()
                    for u in locs[:max_urls]:
                        if isinstance(u, str) and u.startswith("http"):
                            discovered.append(u)
                    return discovered
            except Exception:
                pass

        # Fallback XML parsing
        try:
            r = requests.get(sitemap_url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, "xml")
                for loc in soup.find_all("loc"):
                    u = loc.get_text().strip()
                    if u and u.startswith("http") and u not in discovered:
                        discovered.append(u)
                        if len(discovered) >= max_urls:
                            break
        except Exception:
            pass

        return discovered

    def audit_static_page(self, url: str) -> Tuple[OnPageEvidence, SchemaEvidence]:
        """Audit static HTML page using HTTP request and BeautifulSoup."""
        on_page = OnPageEvidence(url=url, engine_source="advertools_static_http")
        schema_ev = SchemaEvidence(engine_source="advertools_static_http")

        start = time.time()
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            on_page.response_time_sec = round(time.time() - start, 2)
            on_page.status_code = resp.status_code
            on_page.is_redirect = len(resp.history) > 0
            on_page.response_headers = {k: v for k, v in resp.headers.items()}

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

            # Links extraction (Internal vs External)
            parsed_current = urlparse(url)
            current_domain = parsed_current.netloc.lower()
            internal_links = set()
            external_links = set()

            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                full_url = urljoin(url, href)
                parsed_href = urlparse(full_url)
                if parsed_href.netloc.lower() == current_domain or not parsed_href.netloc:
                    internal_links.add(full_url)
                else:
                    external_links.add(full_url)

            on_page.internal_links = list(internal_links)
            on_page.external_links = list(external_links)

            # Schema detection from static DOM — MUST run BEFORE stripping <script> tags
            schema_tags = soup.find_all('script', type='application/ld+json')
            schema_ev.blocks_count = len(schema_tags)

            detected = []
            deprecated = []
            sameas_urls = []
            has_org = False
            has_author = False

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

                        # Check Organization / Person
                        type_str = str(t)
                        if any(o in type_str for o in ["Organization", "Corporation", "LocalBusiness"]):
                            has_org = True
                        if any(p in type_str for p in ["Person", "Author"]):
                            has_author = True

                        # Extract sameAs
                        sameas = item.get("sameAs")
                        if sameas:
                            if isinstance(sameas, list):
                                for s_u in sameas:
                                    if isinstance(s_u, str) and s_u.startswith("http"):
                                        sameas_urls.append(s_u)
                            elif isinstance(sameas, str) and sameas.startswith("http"):
                                sameas_urls.append(sameas)

                except Exception as e:
                    schema_ev.validation_issues.append(f"Malformed JSON-LD block: {e}")

            for s in set(detected):
                if s in DEPRECATED_OR_RESTRICTED_SCHEMAS:
                    deprecated.append(s)

            schema_ev.detected_types = list(set(detected))
            schema_ev.deprecated_types_detected = list(set(deprecated))
            schema_ev.sameas_urls = list(set(sameas_urls))
            schema_ev.has_organization = has_org
            schema_ev.has_author = has_author

            # Word count — strip scripts/styles AFTER schema extraction
            for s in soup(["script", "style", "nav", "footer"]):
                s.extract()
            text = soup.get_text(separator=' ')
            on_page.word_count = len(text.split())

        except Exception as e:
            on_page.status_code = 0
            on_page.response_time_sec = round(time.time() - start, 2)

        return on_page, schema_ev

    def discover_site_urls(self, start_url: str, max_urls: int = 25) -> List[str]:
        """Discover URLs on a website via sitemap and internal crawl links."""
        parsed = urlparse(start_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots = self.audit_robots_txt(base_url)
        if robots.discovered_urls:
            return robots.discovered_urls[:max_urls]

        # If no sitemap urls, perform single-page link discovery
        on_page, _ = self.audit_static_page(start_url)
        discovered = [start_url] + on_page.internal_links
        return list(dict.fromkeys(discovered))[:max_urls]

    def crawl_site(self, start_url: str, max_pages: int = 50, depth: int = 2) -> SiteCrawlResult:
        """Multi-page advertools crawl with site-wide issue detection."""
        import tempfile
        import os
        import pandas as pd

        result = SiteCrawlResult(crawl_depth=depth)

        if not HAS_ADVERTOOLS:
            discovered = self.discover_site_urls(start_url, max_urls=min(max_pages, 10))
            for u in discovered:
                p, _ = self.audit_static_page(u)
                issues = []
                if p.status_code >= 400:
                    issues.append(f"HTTP_{p.status_code}")
                if p.h1_count == 0:
                    issues.append("MISSING_H1")
                if p.word_count < 300:
                    issues.append("THIN_CONTENT")
                if not p.meta_description:
                    issues.append("NO_META_DESC")
                result.pages.append(PageSummary(
                    url=u, status_code=p.status_code,
                    title=p.title, title_length=p.title_length,
                    meta_desc_length=p.meta_desc_length,
                    h1_count=p.h1_count,
                    has_canonical=bool(p.canonical_url),
                    word_count=p.word_count,
                    issues=issues
                ))
            result.pages_crawled = len(result.pages)
            result.pages_with_issues = len([page for page in result.pages if page.issues])
            return result

        with tempfile.NamedTemporaryFile(suffix=".jl", delete=False) as f:
            tmp_path = f.name

        try:
            adv.crawl(
                url_list=[start_url],
                output_file=tmp_path,
                follow_links=True,
                custom_settings={
                    "DEPTH_LIMIT": depth,
                    "CLOSESPIDER_PAGECOUNT": max_pages,
                    "LOG_LEVEL": "ERROR",
                    "USER_AGENT": "RankIntel/2.0 MultiPage Crawler",
                }
            )

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                df = pd.read_json(tmp_path, lines=True)
                result.pages_crawled = len(df)
                title_counts: dict = {}

                for _, row in df.iterrows():
                    url = str(row.get("url", ""))
                    status = int(row.get("status", 200)) if not pd.isna(row.get("status")) else 200
                    title = str(row.get("title", "") or "") if not pd.isna(row.get("title")) else ""
                    meta_desc = str(row.get("meta_description", "") or "") if not pd.isna(row.get("meta_description")) else ""
                    h1 = str(row.get("h1", "") or "") if not pd.isna(row.get("h1")) else ""
                    body = str(row.get("body_text", "") or "") if not pd.isna(row.get("body_text")) else ""
                    canonical = str(row.get("canonical", "") or "") if not pd.isna(row.get("canonical")) else ""
                    word_count = len(body.split())

                    issues = []
                    if status >= 400:
                        result.broken_links.append(url)
                        issues.append(f"HTTP_{status}")
                    if not h1 and status == 200:
                        result.missing_h1_pages.append(url)
                        issues.append("MISSING_H1")
                    if word_count < 300 and status == 200:
                        result.thin_content_pages.append(url)
                        issues.append("THIN_CONTENT")
                    if not meta_desc and status == 200:
                        result.pages_without_meta_desc.append(url)
                        issues.append("NO_META_DESC")
                    if title:
                        title_counts[title] = title_counts.get(title, 0) + 1

                    page = PageSummary(
                        url=url, status_code=status,
                        title=title, title_length=len(title),
                        meta_desc_length=len(meta_desc),
                        h1_count=1 if h1 else 0,
                        has_canonical=bool(canonical),
                        word_count=word_count,
                        issues=issues
                    )
                    result.pages.append(page)

                result.duplicate_titles = [t for t, c in title_counts.items() if c > 1 and t]

                if result.missing_h1_pages:
                    result.site_wide_issues.append(f"{len(result.missing_h1_pages)} pages missing an H1 tag")
                if result.thin_content_pages:
                    result.site_wide_issues.append(f"{len(result.thin_content_pages)} pages with thin content (<300 words)")
                if result.duplicate_titles:
                    result.site_wide_issues.append(f"{len(result.duplicate_titles)} duplicate title tags detected across pages")
                if result.broken_links:
                    result.site_wide_issues.append(f"{len(result.broken_links)} broken response URLs (HTTP 4xx/5xx)")

                result.pages_with_issues = len([page for page in result.pages if page.issues])
        except Exception as e:
            result.site_wide_issues.append(f"Crawl error encountered: {e}")
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        return result

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
