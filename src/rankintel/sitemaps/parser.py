"""
Conservative, robust XML parser for Sitemap documents and Sitemap Indexes.
Handles standard XML, namespaced XML, and conservative recovery of malformed XML
while strictly rejecting HTML error documents.
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Set, Tuple
from bs4 import BeautifulSoup

from rankintel.models.schema import SitemapFormat, SitemapUrlRecord
from rankintel.crawler.normalizer import UrlNormalizer

HTML_INDICATORS = (
    "<!doctype html",
    "<html",
    "<head",
    "<body",
    "<html>",
    "<head>",
    "<body>",
)


class SitemapParser:
    """Production XML sitemap parser with conservative error recovery."""

    @classmethod
    def _strip_ns(cls, tag: str) -> str:
        """Strip XML namespace prefix from tag."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def _is_html_document(cls, text: str) -> bool:
        """Conservative check if text is an HTML webpage rather than XML sitemap."""
        lower_sample = text[:2048].lower()
        return any(ind in lower_sample for ind in HTML_INDICATORS)

    @classmethod
    def parse_sitemap(
        cls,
        content: bytes,
        source_url: str,
        max_size_bytes: int = 10 * 1024 * 1024,
    ) -> Tuple[SitemapFormat, List[SitemapUrlRecord], List[str], Optional[str]]:
        """
        Parse XML sitemap bytes into structured records.
        Returns:
            (format, list_of_url_records, list_of_child_sitemap_urls, error_message)
        """
        if not content or len(content.strip()) == 0:
            return SitemapFormat.MALFORMED, [], [], "Empty sitemap content"

        if len(content) > max_size_bytes:
            return (
                SitemapFormat.MALFORMED,
                [],
                [],
                f"Sitemap payload size ({len(content)} bytes) exceeds maximum limit ({max_size_bytes} bytes)",
            )

        # Decode content with UTF-8 fallback to latin-1
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception as e:
                return SitemapFormat.MALFORMED, [], [], f"Encoding decode error: {e}"

        # 1. Conservative check: reject HTML error pages immediately
        if cls._is_html_document(text):
            return SitemapFormat.HTML_ERROR_PAGE, [], [], "Payload is an HTML document, not an XML sitemap"

        # 2. Primary parsing: standard ElementTree
        try:
            root = ET.fromstring(text.encode("utf-8"))
            root_tag = cls._strip_ns(root.tag).lower()

            if root_tag == "sitemapindex":
                child_sitemaps = cls._extract_sitemap_index_et(root)
                return SitemapFormat.SITEMAPINDEX, [], child_sitemaps, None
            elif root_tag == "urlset":
                urls = cls._extract_urlset_et(root, source_url)
                return SitemapFormat.URLSET, urls, [], None
            else:
                return (
                    SitemapFormat.MALFORMED,
                    [],
                    [],
                    f"Unrecognized XML root element '<{root_tag}>'; expected <urlset> or <sitemapindex>",
                )
        except ET.ParseError as parse_err:
            # 3. Conservative fallback parsing
            return cls._conservative_fallback_parse(text, source_url, str(parse_err))

    @classmethod
    def _extract_sitemap_index_et(cls, root: ET.Element) -> List[str]:
        """Extract child sitemap URLs from <sitemapindex> using ElementTree."""
        children: List[str] = []
        seen: Set[str] = set()

        for sitemap_elem in root:
            if cls._strip_ns(sitemap_elem.tag).lower() == "sitemap":
                for child in sitemap_elem:
                    if cls._strip_ns(child.tag).lower() == "loc":
                        loc = (child.text or "").strip()
                        if loc and loc.startswith(("http://", "https://")) and loc not in seen:
                            seen.add(loc)
                            children.append(loc)
        return children

    @classmethod
    def _extract_urlset_et(cls, root: ET.Element, source_url: str) -> List[SitemapUrlRecord]:
        """Extract URL records from <urlset> using ElementTree."""
        records: List[SitemapUrlRecord] = []
        seen_identities: Set[str] = set()

        for url_elem in root:
            if cls._strip_ns(url_elem.tag).lower() == "url":
                loc = ""
                lastmod = None
                changefreq = None
                priority = None

                for child in url_elem:
                    ctag = cls._strip_ns(child.tag).lower()
                    val = (child.text or "").strip()
                    if ctag == "loc":
                        loc = val
                    elif ctag == "lastmod" and val:
                        lastmod = val
                    elif ctag == "changefreq" and val:
                        changefreq = val.lower()
                    elif ctag == "priority" and val:
                        try:
                            priority = float(val)
                        except ValueError:
                            pass

                if loc and loc.startswith(("http://", "https://")):
                    identity = UrlNormalizer.get_url_identity(loc)
                    if identity not in seen_identities:
                        seen_identities.add(identity)
                        records.append(
                            SitemapUrlRecord(
                                loc=loc,
                                identity_url=identity,
                                source_sitemap=source_url,
                                lastmod=lastmod,
                                changefreq=changefreq,
                                priority=priority,
                            )
                        )
        return records

    @classmethod
    def _conservative_fallback_parse(
        cls, text: str, source_url: str, orig_error: str
    ) -> Tuple[SitemapFormat, List[SitemapUrlRecord], List[str], Optional[str]]:
        """
        Conservative recovery when ElementTree fails (e.g. unescaped & in query strings).
        Only recovers if document unambiguously contains <urlset> or <sitemapindex>.
        """
        lower = text.lower()
        has_urlset = "<urlset" in lower
        has_sitemapindex = "<sitemapindex" in lower

        if not (has_urlset or has_sitemapindex):
            return (
                SitemapFormat.MALFORMED,
                [],
                [],
                f"Malformed XML and missing sitemap root elements: {orig_error}",
            )

        try:
            soup = BeautifulSoup(text, "html.parser")
        except Exception as e:
            return SitemapFormat.MALFORMED, [], [], f"Failed to parse XML: {orig_error}; fallback failed: {e}"

        if has_sitemapindex:
            children: List[str] = []
            seen: Set[str] = set()
            for sm in soup.find_all("sitemap"):
                loc_tag = sm.find("loc")
                if loc_tag:
                    loc = loc_tag.get_text().strip()
                    if loc and loc.startswith(("http://", "https://")) and loc not in seen:
                        seen.add(loc)
                        children.append(loc)
            if children:
                return SitemapFormat.SITEMAPINDEX, [], children, f"Recovered via conservative fallback: {orig_error}"
            return SitemapFormat.MALFORMED, [], [], f"Malformed sitemapindex without valid loc elements: {orig_error}"

        if has_urlset:
            records: List[SitemapUrlRecord] = []
            seen_identities: Set[str] = set()
            for u in soup.find_all("url"):
                loc_tag = u.find("loc")
                if loc_tag:
                    loc = loc_tag.get_text().strip()
                    if loc and loc.startswith(("http://", "https://")):
                        identity = UrlNormalizer.get_url_identity(loc)
                        if identity not in seen_identities:
                            seen_identities.add(identity)
                            lastmod_tag = u.find("lastmod")
                            changefreq_tag = u.find("changefreq")
                            priority_tag = u.find("priority")

                            lastmod = lastmod_tag.get_text().strip() if lastmod_tag else None
                            changefreq = changefreq_tag.get_text().strip().lower() if changefreq_tag else None
                            priority = None
                            if priority_tag:
                                try:
                                    priority = float(priority_tag.get_text().strip())
                                except ValueError:
                                    pass

                            records.append(
                                SitemapUrlRecord(
                                    loc=loc,
                                    identity_url=identity,
                                    source_sitemap=source_url,
                                    lastmod=lastmod,
                                    changefreq=changefreq,
                                    priority=priority,
                                )
                            )
            if records:
                return SitemapFormat.URLSET, records, [], f"Recovered via conservative fallback: {orig_error}"
            return SitemapFormat.MALFORMED, [], [], f"Malformed urlset without valid loc elements: {orig_error}"

        return SitemapFormat.MALFORMED, [], [], f"Malformed XML: {orig_error}"
