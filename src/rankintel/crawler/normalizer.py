"""
URL Normalizer for RankIntel Deep Crawling.

Distinguishes between:
1. Crawl Normalization: Stripping known marketing/tracking parameters (utm_*, gclid, etc.)
   and sorting query parameters to prevent infinite duplicate crawl loops.
2. URL Identity: Preserving content-defining parameters (e.g. ?id=123, ?product=456)
   so unique resources are never erroneously conflated.
"""
from __future__ import annotations
import re
from typing import Optional, Set
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qsl, urlencode

TRACKING_QUERY_PARAMS: Set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "msclkid",
    "mc_eid",
    "_ga",
    "_gl",
}

NON_HTML_EXTENSIONS: Set[str] = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".webm",
    ".css", ".js", ".mjs",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".exe", ".dmg", ".apk", ".bin",
}


class UrlNormalizer:
    """RFC-compliant URL normalizer and boundary evaluator."""

    @classmethod
    def normalize_for_crawl(cls, url: str, parent_url: Optional[str] = None) -> str:
        """
        Normalize URL for crawler deduplication.
        - Resolves relative URLs against parent_url
        - Strips fragments
        - Lowercases scheme and host
        - Strips default ports (:80, :443)
        - Strips known marketing tracking parameters (utm_*, gclid, fbclid, etc.)
        - Alphabetically sorts remaining query parameters
        - Normalizes non-root trailing slashes
        """
        if parent_url:
            url = urljoin(parent_url, url)

        parsed = urlsplit(url.strip())
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return url.strip()

        # Hostname & port
        netloc = parsed.netloc.lower()
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        # Path normalization
        path = parsed.path
        if not path:
            path = "/"
        else:
            # Replace multiple slashes with a single slash
            path = re.sub(r"/+", "/", path)
            # Normalize trailing slash for non-root paths (strip trailing slash)
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/")

        # Query parameter normalization (strip tracking parameters, sort remaining)
        filtered_q = []
        if parsed.query:
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            for k, v in query_pairs:
                if k.lower() not in TRACKING_QUERY_PARAMS:
                    filtered_q.append((k, v))
            filtered_q.sort(key=lambda item: (item[0], item[1]))

        new_query = urlencode(filtered_q) if filtered_q else ""

        # Fragment is explicitly discarded for crawl normalization
        return urlunsplit((scheme, netloc, path, new_query, ""))

    @classmethod
    def get_url_identity(cls, url: str, parent_url: Optional[str] = None) -> str:
        """
        Produce a canonical identity URL for a resource.
        Preserves all content-identifying parameters intact.
        """
        if parent_url:
            url = urljoin(parent_url, url)

        parsed = urlsplit(url.strip())
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return url.strip()

        netloc = parsed.netloc.lower()
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        # Preserve query params but sort them for consistent identity
        q_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        q_pairs.sort(key=lambda item: (item[0], item[1]))
        new_query = urlencode(q_pairs) if q_pairs else ""

        return urlunsplit((scheme, netloc, path, new_query, ""))

    @classmethod
    def is_same_domain(cls, url: str, base_url: str, allow_subdomains: bool = False) -> bool:
        """Verify whether candidate URL falls within crawl domain boundary."""
        p_cand = urlsplit(url)
        p_base = urlsplit(base_url)

        cand_host = p_cand.netloc.lower().split(":")[0]
        base_host = p_base.netloc.lower().split(":")[0]

        if not cand_host:
            return True  # Relative URL
        if cand_host == base_host:
            return True

        if allow_subdomains:
            # Allow foo.example.com when base is example.com, or vice versa
            base_parts = base_host.split(".")
            base_root = ".".join(base_parts[-2:]) if len(base_parts) >= 2 else base_host
            return cand_host.endswith("." + base_root) or cand_host == base_root

        return False

    @classmethod
    def is_crawlable_mime(cls, url: str) -> bool:
        """
        Check whether URL points to an HTML/document resource rather than
        a binary asset (image, video, archive, document).
        """
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in ("http", "https", ""):
            return False

        path_lower = parsed.path.lower()
        for ext in NON_HTML_EXTENSIONS:
            if path_lower.endswith(ext):
                return False

        return True
