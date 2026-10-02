"""
Sitemap Discovery Engine — Locates sitemaps from robots.txt directives and standard paths.
"""
from __future__ import annotations
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin

from rankintel.models.schema import RobotsEvidence


class SitemapDiscovery:
    """Discovers sitemap locations without making unprompted network calls."""

    STANDARD_SITEMAP_PATHS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
    ]

    @classmethod
    def discover_from_robots_txt(cls, robots_content: str) -> List[str]:
        """Extract all Sitemap: URLs declared in robots.txt text."""
        sitemaps: List[str] = []
        seen: Set[str] = set()

        if not robots_content:
            return []

        for line in robots_content.splitlines():
            line_str = line.strip()
            if line_str.lower().startswith("sitemap:"):
                parts = line_str.split(":", 1)
                if len(parts) == 2:
                    s_url = parts[1].strip()
                    if s_url and s_url.startswith(("http://", "https://")) and s_url not in seen:
                        seen.add(s_url)
                        sitemaps.append(s_url)
        return sitemaps

    @classmethod
    def discover_sitemap_urls(
        cls,
        base_url: str,
        robots_evidence: Optional[RobotsEvidence] = None,
        robots_txt_content: Optional[str] = None,
        fallback_to_standard_paths: bool = True,
    ) -> List[str]:
        """
        Produce candidate sitemap URLs for a domain using:
        1. robots.txt Sitemap: directives (if available)
        2. standard sitemap root fallbacks (if enabled and no directives found)
        """
        discovered: List[str] = []
        seen: Set[str] = set()

        # 1. From passed robots_txt_content
        if robots_txt_content:
            for s_url in cls.discover_from_robots_txt(robots_txt_content):
                if s_url not in seen:
                    seen.add(s_url)
                    discovered.append(s_url)

        # 2. From RobotsEvidence model
        if robots_evidence and robots_evidence.sitemaps:
            for s_url in robots_evidence.sitemaps:
                clean = s_url.strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    discovered.append(clean)

        # 3. Fallback to standard root locations if no directives discovered
        if not discovered and fallback_to_standard_paths and base_url:
            parsed = urlparse(base_url)
            root_origin = f"{parsed.scheme}://{parsed.netloc}"
            for path in cls.STANDARD_SITEMAP_PATHS:
                candidate = urljoin(root_origin, path)
                if candidate not in seen:
                    seen.add(candidate)
                    discovered.append(candidate)

        return discovered
