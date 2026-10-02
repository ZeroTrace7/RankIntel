"""
URL Hygiene Analysis Engine for RankIntel (Milestone M6.3).
Detects duplicate URL representations and classifies relationship evidence.
"""
from __future__ import annotations
import hashlib
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    HygieneAnomalyType,
    HygieneEvidenceType,
    HygieneAnomaly,
    RedirectChainRecord,
    CanonicalChainRecord,
)
from rankintel.crawler.normalizer import UrlNormalizer, TRACKING_QUERY_PARAMS
from rankintel.analyzers.record_lookup import RecordLookupIndex


class UrlHygieneDetector:
    """
    Deterministic detector for URL hygiene anomalies.
    Distinguishes observed evidence (redirect, canonical, identical extracted text)
    from heuristic potential representations.
    """

    @classmethod
    def get_hygiene_key(cls, url: str) -> str:
        """
        Compute relaxed hygiene identity key.
        Preserves content-defining parameters, lowercases path/scheme/host,
        normalizes www and trailing slashes.
        """
        if not url:
            return ""

        parsed = urlsplit(url.strip())
        scheme = "https"  # Canonicalize protocol for grouping

        # Hostname: lowercase, strip default ports, strip leading 'www.'
        netloc = parsed.netloc.lower()
        if netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif netloc.endswith(":443"):
            netloc = netloc[:-4]

        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Path: lowercase, collapse multiple slashes, strip non-root trailing slash
        path = parsed.path or "/"
        path = re.sub(r"/+", "/", path)
        path = path.lower()
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        # Query: filter out tracking parameters, sort remaining content-defining parameters
        filtered_q = []
        if parsed.query:
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            for k, v in pairs:
                if k.lower() not in TRACKING_QUERY_PARAMS:
                    filtered_q.append((k, v))
            filtered_q.sort(key=lambda item: (item[0], item[1]))

        new_query = urlencode(filtered_q) if filtered_q else ""
        return urlunsplit((scheme, netloc, path, new_query, ""))

    @classmethod
    def classify_anomaly_type(cls, url_a: str, url_b: str) -> HygieneAnomalyType:
        """Determine the specific representation difference between two URLs."""
        pa = urlsplit(url_a.strip())
        pb = urlsplit(url_b.strip())

        # Protocol
        if pa.scheme.lower() != pb.scheme.lower():
            return HygieneAnomalyType.PROTOCOL_HTTP_HTTPS

        # WWW Subdomain
        ha = pa.netloc.lower().split(":")[0]
        hb = pb.netloc.lower().split(":")[0]
        if (ha.startswith("www.") and ha[4:] == hb) or (hb.startswith("www.") and hb[4:] == ha):
            return HygieneAnomalyType.WWW_SUBDOMAIN

        # Multiple consecutive slashes
        if ("//" in pa.path and "//" not in pb.path) or ("//" in pb.path and "//" not in pa.path):
            return HygieneAnomalyType.MULTIPLE_SLASHES

        # Trailing slash
        norm_path_a = pa.path.rstrip("/") if len(pa.path) > 1 else pa.path
        norm_path_b = pb.path.rstrip("/") if len(pb.path) > 1 else pb.path
        if norm_path_a == norm_path_b and pa.path != pb.path:
            return HygieneAnomalyType.TRAILING_SLASH

        # Path casing
        if pa.path.lower() == pb.path.lower() and pa.path != pb.path:
            return HygieneAnomalyType.PATH_CASING

        # Query parameters: tracking params vs clean
        qa_pairs = parse_qsl(pa.query, keep_blank_values=True)
        qb_pairs = parse_qsl(pb.query, keep_blank_values=True)
        has_qa_tracking = any(k.lower() in TRACKING_QUERY_PARAMS for k, _ in qa_pairs)
        has_qb_tracking = any(k.lower() in TRACKING_QUERY_PARAMS for k, _ in qb_pairs)
        if has_qa_tracking != has_qb_tracking:
            return HygieneAnomalyType.TRACKING_PARAMETERS

        # Query parameter ordering
        if sorted(qa_pairs) == sorted(qb_pairs) and pa.query != pb.query:
            return HygieneAnomalyType.QUERY_PARAM_ORDER

        # Default to trailing slash or casing if paths differ
        if pa.path != pb.path:
            if pa.path.lower() == pb.path.lower():
                return HygieneAnomalyType.PATH_CASING
            return HygieneAnomalyType.TRAILING_SLASH

        return HygieneAnomalyType.TRAILING_SLASH

    @classmethod
    def extract_clean_text(cls, raw_html: Optional[str]) -> str:
        """Extract visible cleaned text for content comparison."""
        if not raw_html:
            return ""
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.extract()
            text = soup.get_text(separator=" ")
            return re.sub(r"\s+", " ", text).strip()
        except Exception:
            return raw_html.strip()

    @classmethod
    def analyze_pair(
        cls,
        url_a: str,
        url_b: str,
        rec_a: Optional[CrawlRecord] = None,
        rec_b: Optional[CrawlRecord] = None,
        redirect_chains: Optional[Dict[str, RedirectChainRecord]] = None,
        canonical_chains: Optional[Dict[str, CanonicalChainRecord]] = None,
    ) -> Optional[HygieneAnomaly]:
        """
        Analyze a pair of URLs sharing the same hygiene key.
        Evaluates evidence strictly and determines primary vs duplicate.
        """
        if url_a.strip() == url_b.strip():
            return None

        # Ignore fragment-only differences (HTML in-page anchors are not hygiene anomalies)
        pa = urlsplit(url_a.strip())
        pb = urlsplit(url_b.strip())
        if pa._replace(fragment="") == pb._replace(fragment=""):
            return None

        anomaly_type = cls.classify_anomaly_type(url_a, url_b)
        evidence_notes: List[str] = []

        primary_url = url_a
        duplicate_url = url_b
        evidence_type = HygieneEvidenceType.POTENTIAL_DUPLICATE_REPRESENTATION

        # Helper to check redirect
        def is_redirect_to(source_rec: Optional[CrawlRecord], dest_url: str) -> bool:
            if not source_rec:
                return False
            if source_rec.crawl_status == CrawlStatus.REDIRECTED or (300 <= source_rec.status_code <= 399):
                dest_ident = UrlNormalizer.get_url_identity(dest_url)
                if source_rec.redirect_url:
                    return UrlNormalizer.get_url_identity(source_rec.redirect_url) == dest_ident
                if source_rec.response_headers:
                    loc = source_rec.response_headers.get("location")
                    if loc and UrlNormalizer.get_url_identity(str(loc)) == dest_ident:
                        return True
            return False

        # Helper to check canonical
        def is_canonical_to(source_rec: Optional[CrawlRecord], dest_url: str) -> bool:
            if not source_rec or not source_rec.raw_html:
                return False
            from rankintel.analyzers.indexability_engine import IndexabilityEngine
            declared = IndexabilityEngine.parse_canonical_tag(source_rec.raw_html, source_rec.url)
            if declared:
                return UrlNormalizer.get_url_identity(declared) == UrlNormalizer.get_url_identity(dest_url)
            return False

        # 1. Evidence Tier 1: Redirect Equivalence
        if is_redirect_to(rec_a, url_b):
            evidence_type = HygieneEvidenceType.REDIRECT_EQUIVALENT
            primary_url = url_b
            duplicate_url = url_a
            evidence_notes.append(f"Redirect confirmed: {url_a} redirects to {url_b}")
        elif is_redirect_to(rec_b, url_a):
            evidence_type = HygieneEvidenceType.REDIRECT_EQUIVALENT
            primary_url = url_a
            duplicate_url = url_b
            evidence_notes.append(f"Redirect confirmed: {url_b} redirects to {url_a}")

        # 2. Evidence Tier 2: Canonical Equivalence
        elif is_canonical_to(rec_a, url_b):
            evidence_type = HygieneEvidenceType.CANONICAL_EQUIVALENT
            primary_url = url_b
            duplicate_url = url_a
            evidence_notes.append(f"Canonical alignment: {url_a} declares {url_b} as canonical")
        elif is_canonical_to(rec_b, url_a):
            evidence_type = HygieneEvidenceType.CANONICAL_EQUIVALENT
            primary_url = url_a
            duplicate_url = url_b
            evidence_notes.append(f"Canonical alignment: {url_b} declares {url_a} as canonical")

        # 3. Evidence Tier 3: Identical Extracted Text
        elif rec_a and rec_b and rec_a.raw_html and rec_b.raw_html and rec_a.status_code == 200 and rec_b.status_code == 200:
            text_a = cls.extract_clean_text(rec_a.raw_html)
            text_b = cls.extract_clean_text(rec_b.raw_html)
            hash_a = hashlib.sha256(text_a.encode("utf-8")).hexdigest()
            hash_b = hashlib.sha256(text_b.encode("utf-8")).hexdigest()

            if hash_a == hash_b and text_a:
                evidence_type = HygieneEvidenceType.IDENTICAL_EXTRACTED_TEXT
                evidence_notes.append(
                    "Identical extracted textual content observed; full-document equivalence not established."
                )
                primary_url, duplicate_url = cls.pick_primary(url_a, url_b, anomaly_type)
            else:
                evidence_type = HygieneEvidenceType.DISTINCT_CONTENT_VARIANT
                evidence_notes.append(
                    "Normalized representations match, but extracted body text differs. Resources appear to serve different content."
                )
                primary_url = url_a
                duplicate_url = url_b

        # 4. Evidence Tier 4: Potential Representation Duplicate (Heuristic Only)
        else:
            evidence_type = HygieneEvidenceType.POTENTIAL_DUPLICATE_REPRESENTATION
            evidence_notes.append(
                "Potential URL representation duplicate detected. Content equality could not be verified from crawl evidence."
            )
            primary_url, duplicate_url = cls.pick_primary(url_a, url_b, anomaly_type)

        rec_text = cls.generate_recommendation(anomaly_type, evidence_type, primary_url, duplicate_url)

        return HygieneAnomaly(
            anomaly_type=anomaly_type,
            primary_url=primary_url,
            duplicate_url=duplicate_url,
            recommendation=rec_text,
            evidence_type=evidence_type,
            evidence_notes=evidence_notes,
        )

    @classmethod
    def pick_primary(cls, url_a: str, url_b: str, anomaly_type: HygieneAnomalyType) -> Tuple[str, str]:
        """Heuristically select standard primary representation."""
        pa = urlsplit(url_a.strip())
        pb = urlsplit(url_b.strip())

        if anomaly_type == HygieneAnomalyType.PROTOCOL_HTTP_HTTPS:
            if pa.scheme.lower() == "https":
                return url_a, url_b
            return url_b, url_a

        if anomaly_type == HygieneAnomalyType.PATH_CASING:
            if pa.path == pa.path.lower():
                return url_a, url_b
            return url_b, url_a

        if anomaly_type == HygieneAnomalyType.MULTIPLE_SLASHES:
            if "//" not in pa.path:
                return url_a, url_b
            return url_b, url_a

        if anomaly_type == HygieneAnomalyType.TRACKING_PARAMETERS:
            qa = parse_qsl(pa.query, keep_blank_values=True)
            has_qa_tracking = any(k.lower() in TRACKING_QUERY_PARAMS for k, _ in qa)
            if not has_qa_tracking:
                return url_a, url_b
            return url_b, url_a

        if anomaly_type == HygieneAnomalyType.QUERY_PARAM_ORDER:
            # Sorted query is primary
            qa = parse_qsl(pa.query, keep_blank_values=True)
            sorted_q = urlencode(sorted(qa))
            if pa.query == sorted_q:
                return url_a, url_b
            return url_b, url_a

        if anomaly_type == HygieneAnomalyType.WWW_SUBDOMAIN:
            # Prefer non-www by default
            if not pa.netloc.lower().startswith("www."):
                return url_a, url_b
            return url_b, url_a

        if anomaly_type == HygieneAnomalyType.TRAILING_SLASH:
            # Prefer non-trailing slash for non-root paths by standard convention
            if not pa.path.endswith("/") and len(pa.path) > 1:
                return url_a, url_b
            return url_b, url_a

        return url_a, url_b

    @classmethod
    def generate_recommendation(
        cls,
        anomaly_type: HygieneAnomalyType,
        evidence_type: HygieneEvidenceType,
        primary_url: str,
        duplicate_url: str,
    ) -> str:
        """Generate actionable remediation guidance based on evidence."""
        if evidence_type == HygieneEvidenceType.REDIRECT_EQUIVALENT:
            return f"Redirect from {duplicate_url} to {primary_url} is active. Ensure all internal links point directly to {primary_url}."

        if evidence_type == HygieneEvidenceType.CANONICAL_EQUIVALENT:
            return f"Canonical tag references {primary_url}. Implement a 301 permanent redirect from {duplicate_url} to consolidate index equity."

        if evidence_type == HygieneEvidenceType.IDENTICAL_EXTRACTED_TEXT:
            return f"Both representations serve identical text. Consolidate by configuring a 301 redirect from {duplicate_url} to {primary_url} and self-canonicalizing {primary_url}."

        if evidence_type == HygieneEvidenceType.DISTINCT_CONTENT_VARIANT:
            return f"URLs differ only by representation syntax ({anomaly_type.value}) but serve different content. Verify routing rules to ensure this is intentional and not routing ambiguity."

        return f"Potential representation divergence ({anomaly_type.value}). Maintain consistent URL structure pointing exclusively to {primary_url}."

    @classmethod
    def detect_site_hygiene(
        cls,
        site_crawl: SiteCrawlResult,
        redirect_chains: Optional[Dict[str, RedirectChainRecord]] = None,
        canonical_chains: Optional[Dict[str, CanonicalChainRecord]] = None,
    ) -> List[HygieneAnomaly]:
        """
        Detect URL hygiene anomalies across all records and discovered links in a SiteCrawlResult.
        """
        index = RecordLookupIndex(site_crawl.crawl_records)
        all_urls: Set[str] = set()

        for rec in site_crawl.crawl_records:
            if rec.url:
                clean_u = urlsplit(rec.url.strip())._replace(fragment="").geturl()
                all_urls.add(clean_u)
            for link in rec.discovered_links:
                if link and (link.startswith("http://") or link.startswith("https://")):
                    clean_l = urlsplit(link.strip())._replace(fragment="").geturl()
                    all_urls.add(clean_l)

        # Group URLs by hygiene key
        buckets: Dict[str, List[str]] = {}
        for u in all_urls:
            key = cls.get_hygiene_key(u)
            if key:
                buckets.setdefault(key, []).append(u)

        anomalies: List[HygieneAnomaly] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for key, urls in buckets.items():
            unique_urls = list(dict.fromkeys(urls))
            if len(unique_urls) < 2:
                continue

            for i in range(len(unique_urls)):
                for j in range(i + 1, len(unique_urls)):
                    u1 = unique_urls[i]
                    u2 = unique_urls[j]

                    pair_key = tuple(sorted([u1, u2]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    rec1 = index.lookup(u1)
                    rec2 = index.lookup(u2)

                    anomaly = cls.analyze_pair(
                        u1,
                        u2,
                        rec_a=rec1,
                        rec_b=rec2,
                        redirect_chains=redirect_chains,
                        canonical_chains=canonical_chains,
                    )
                    if anomaly:
                        anomalies.append(anomaly)

        site_crawl.hygiene_anomalies = anomalies
        return anomalies
