"""
URL Hygiene & Relationship Analysis Engine for RankIntel (Milestone M6.3).
Orchestrates:
Crawl Evidence -> RedirectResolver -> CanonicalResolver -> UrlHygieneDetector -> SiteCrawlResult
"""
from __future__ import annotations
from typing import Dict, List, Optional

from rankintel.models.schema import (
    SiteCrawlResult,
    RedirectChainRecord,
    RedirectChainStatus,
    CanonicalChainRecord,
    CanonicalChainStatus,
    HygieneAnomaly,
)
from rankintel.analyzers.record_lookup import RecordLookupIndex
from rankintel.analyzers.redirect_resolver import RedirectResolver
from rankintel.analyzers.canonical_resolver import CanonicalResolver
from rankintel.analyzers.hygiene_detector import UrlHygieneDetector


class UrlHygieneEngine:
    """
    Coordinates M6.3 relationship resolution and URL hygiene detection across a crawl.
    """

    @classmethod
    def evaluate_site(
        cls,
        site_crawl: SiteCrawlResult,
        max_redirect_hops: int = 10,
        max_canonical_hops: int = 10,
    ) -> SiteCrawlResult:
        """
        Execute full M6.3 analysis pipeline on a SiteCrawlResult.
        Zero external network requests.
        """
        # 1. Resolve redirect chains
        redirect_chains = RedirectResolver.resolve_site(site_crawl, max_hops=max_redirect_hops)

        # 2. Resolve canonical chains (with redirect awareness)
        canonical_chains = CanonicalResolver.resolve_site(
            site_crawl,
            redirect_chains=redirect_chains,
            max_hops=max_canonical_hops,
        )

        # 3. Detect URL hygiene anomalies
        hygiene_anomalies = UrlHygieneDetector.detect_site_hygiene(
            site_crawl,
            redirect_chains=redirect_chains,
            canonical_chains=canonical_chains,
        )

        # 4. Synthesize structural site-wide issues
        loop_redirects = [c for c in redirect_chains.values() if c.has_loop]
        multi_hop_redirects = [c for c in redirect_chains.values() if c.status == RedirectChainStatus.MULTI_HOP]
        broken_redirects = [c for c in redirect_chains.values() if c.status == RedirectChainStatus.BROKEN_TARGET]

        canonical_loops = [c for c in canonical_chains.values() if c.has_loop]
        canonical_chains_detected = [c for c in canonical_chains.values() if c.status == CanonicalChainStatus.CHAIN]
        canonical_to_redirect = [c for c in canonical_chains.values() if c.points_to_redirect]
        canonical_to_dead = [c for c in canonical_chains.values() if c.points_to_dead_url]

        if loop_redirects:
            site_crawl.site_wide_issues.append(f"{len(loop_redirects)} circular redirect loop(s) detected")
        if multi_hop_redirects:
            site_crawl.site_wide_issues.append(f"{len(multi_hop_redirects)} multi-hop redirect chain(s) detected")
        if broken_redirects:
            site_crawl.site_wide_issues.append(f"{len(broken_redirects)} redirect target(s) returned 4xx/5xx errors")

        if canonical_loops:
            site_crawl.site_wide_issues.append(f"{len(canonical_loops)} circular canonical loop(s) detected")
        if canonical_chains_detected:
            site_crawl.site_wide_issues.append(f"{len(canonical_chains_detected)} multi-hop canonical chain(s) detected")
        if canonical_to_redirect:
            site_crawl.site_wide_issues.append(f"{len(canonical_to_redirect)} canonical tag(s) point to a redirected URL")
        if canonical_to_dead:
            site_crawl.site_wide_issues.append(f"{len(canonical_to_dead)} canonical tag(s) point to a broken/dead URL")

        if hygiene_anomalies:
            site_crawl.site_wide_issues.append(f"{len(hygiene_anomalies)} URL hygiene representation anomalie(s) detected")

        # De-duplicate site_wide_issues
        site_crawl.site_wide_issues = list(dict.fromkeys(site_crawl.site_wide_issues))

        return site_crawl
