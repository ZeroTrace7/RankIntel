"""
Centralized Record Lookup Strategy for RankIntel M6.3 Analyzers.
Prevents query parameter collapse and preserves distinct resource identity.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Union
from rankintel.models.schema import CrawlRecord, SiteCrawlResult
from rankintel.crawler.normalizer import UrlNormalizer


class RecordLookupIndex:
    """
    Collision-safe index for CrawlRecord lookups.
    Enforces a strict hierarchy:
    1. Exact raw URL match
    2. Content-preserving URL identity (preserves ?id=1 vs ?id=2)
    3. Crawl-normalized URL (fallback for trailing slashes / tracking params)
    """

    def __init__(self, records: Union[List[CrawlRecord], Dict[str, CrawlRecord], SiteCrawlResult]):
        self.by_raw_url: Dict[str, CrawlRecord] = {}
        self.by_identity: Dict[str, CrawlRecord] = {}
        self.by_norm_url: Dict[str, CrawlRecord] = {}
        self._all_records: List[CrawlRecord] = []

        if isinstance(records, SiteCrawlResult):
            rec_list = records.crawl_records
        elif isinstance(records, dict):
            rec_list = list(records.values())
        else:
            rec_list = list(records)

        for rec in rec_list:
            self._all_records.append(rec)
            raw = rec.url.strip() if rec.url else ""
            if raw:
                self.by_raw_url[raw] = rec

            ident = rec.identity_url or (UrlNormalizer.get_url_identity(raw) if raw else "")
            if ident:
                self.by_identity[ident] = rec

            norm = rec.normalized_url or (UrlNormalizer.normalize_for_crawl(raw) if raw else "")
            if norm:
                # To prevent ?id=1 and ?id=2 from colliding in by_norm_url,
                # only store in by_norm_url if not already present or if identity matches
                if norm not in self.by_norm_url:
                    self.by_norm_url[norm] = rec

    def lookup(self, url: str) -> Optional[CrawlRecord]:
        """
        Look up a CrawlRecord by URL using prioritized identity resolution.
        """
        if not url:
            return None

        clean_url = url.strip()

        # 1. Exact raw URL
        if clean_url in self.by_raw_url:
            return self.by_raw_url[clean_url]

        # 2. Content-preserving URL identity (preserves content-defining query params)
        ident = UrlNormalizer.get_url_identity(clean_url)
        if ident in self.by_identity:
            return self.by_identity[ident]

        # 3. Fallback to crawl-normalized URL
        norm = UrlNormalizer.normalize_for_crawl(clean_url)
        candidate = self.by_norm_url.get(norm)
        if candidate:
            # If the candidate has the same content identity or neither has query params, safe
            cand_ident = candidate.identity_url or UrlNormalizer.get_url_identity(candidate.url)
            if cand_ident == ident or ("?" not in clean_url and "?" not in candidate.url):
                return candidate

        return None

    def get(self, url: str, default: Optional[CrawlRecord] = None) -> Optional[CrawlRecord]:
        res = self.lookup(url)
        return res if res is not None else default

    def __contains__(self, url: str) -> bool:
        return self.lookup(url) is not None

    def __getitem__(self, url: str) -> CrawlRecord:
        res = self.lookup(url)
        if res is None:
            raise KeyError(url)
        return res

    def all_records(self) -> List[CrawlRecord]:
        return list(self._all_records)
