"""
Site Entity Analyzer — Cross-page multi-page crawl entity intelligence:
Performs primary organization candidate identification (with explicit selection rationale),
tracks site-wide entity aggregation, and surfaces observable attribute inconsistencies across pages.
"""
from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from urllib.parse import urlparse

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteEntityIntelligence,
    PrimaryOrganizationCandidate,
    EntityInconsistency,
    DetectedEntity,
    EntityRelationship,
    EntityEvidence,
    EntityType,
    EntitySource,
    EntitySignalType,
    EvidenceNature,
)
from rankintel.engines.entity_engine import (
    EntityEngine,
    normalize_entity_name,
    normalize_phone_number,
)


class SiteEntityAnalyzer:
    """
    Analyzes site-wide entity declarations and signals from CrawlRecord raw_html
    without initiating any network requests.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteEntityIntelligence:
        """
        Processes all crawled HTML documents in site_crawl to identify primary organization candidates,
        aggregate observed entities and relationships, and identify cross-page consistency findings.
        """
        page_evidence: Dict[str, EntityEvidence] = {}
        all_entities: List[DetectedEntity] = []
        all_relationships: List[EntityRelationship] = []

        # Tracking structures for cross-page consistency
        # brand_core -> { "raw_names": {name: [urls]}, "addresses": {addr: [urls]}, "phones": {phone: [urls]}, "sameas": {url_link: [urls]} }
        entity_profiles: Dict[str, Dict[str, Dict[str, List[str]]]] = defaultdict(lambda: {
            "names": defaultdict(list),
            "addresses": defaultdict(list),
            "phones": defaultdict(list),
            "urls": defaultdict(list),
            "sameas": defaultdict(list),
        })

        # Candidate scoring for primary organization candidate identification
        candidate_frequencies: Dict[str, int] = defaultdict(int)
        candidate_sources: Dict[str, Set[str]] = defaultdict(set)
        candidate_reasons: Dict[str, List[str]] = defaultdict(list)
        root_declarations: Set[str] = set()

        records_to_process = [
            rec for rec in site_crawl.crawl_records
            if (rec.status_code == 200 or rec.status_code is None) and rec.raw_html
        ]

        # Determine root/homepage URL
        root_url = ""
        if records_to_process:
            # Shortest URL or depth 0
            sorted_by_depth = sorted(records_to_process, key=lambda r: (r.depth, len(r.url)))
            root_url = sorted_by_depth[0].url

        for rec in records_to_process:
            url = rec.url
            html = rec.raw_html

            evidence = EntityEngine.evaluate(raw_html=html, url=url)
            page_evidence[url] = evidence
            all_entities.extend(evidence.detected_entities)
            all_relationships.extend(evidence.relationships)

            is_root_page = (url == root_url)

            # Analyze organization and local business signals for site-wide candidate selection
            for ent in evidence.detected_entities:
                if ent.entity_type in (EntityType.ORGANIZATION, EntityType.LOCAL_BUSINESS):
                    norm = ent.normalized_name or normalize_entity_name(ent.name)
                    if not norm:
                        continue

                    candidate_frequencies[norm] += 1
                    candidate_sources[norm].add(ent.source.value)

                    if ent.source == EntitySource.JSON_LD:
                        candidate_reasons[norm].append(f"Structured {ent.structured_data_type or 'Organization'} JSON-LD on `{url}`")
                    elif ent.signal_type == EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL:
                        candidate_reasons[norm].append(f"og:site_name signal on `{url}`")
                    elif ent.signal_type == EntitySignalType.COPYRIGHT_SIGNAL:
                        candidate_reasons[norm].append(f"Copyright branding signal on `{url}`")

                    if is_root_page:
                        root_declarations.add(norm)
                        candidate_reasons[norm].append(f"Observed on root/homepage `{url}`")

                    profile = entity_profiles[norm]
                    profile["names"][ent.name].append(url)
                    if ent.address:
                        profile["addresses"][ent.address].append(url)
                    if ent.telephone:
                        clean_p = normalize_phone_number(ent.telephone)
                        profile["phones"][clean_p].append(url)
                    if ent.url:
                        profile["urls"][ent.url].append(url)
                    for s_link in ent.same_as:
                        profile["sameas"][s_link].append(url)

        # ---------------------------------------------------------------------
        # 1. Primary Organization Candidate Identification (Explicit Rationale)
        # ---------------------------------------------------------------------
        primary_candidate: Optional[PrimaryOrganizationCandidate] = None

        if candidate_frequencies:
            # Score candidates neutrally:
            # +10 for root declaration, +5 for JSON-LD, +2 per occurrence
            def score_candidate(c_norm: str) -> int:
                score = candidate_frequencies[c_norm] * 2
                if c_norm in root_declarations:
                    score += 10
                if "JSON_LD" in candidate_sources[c_norm]:
                    score += 5
                return score

            best_norm = max(candidate_frequencies.keys(), key=score_candidate)
            # Find the most representative display name for this candidate
            raw_name_counts: Dict[str, int] = defaultdict(int)
            for raw_n, urls in entity_profiles[best_norm]["names"].items():
                raw_name_counts[raw_n] += len(urls)
            display_name = max(raw_name_counts.keys(), key=lambda k: raw_name_counts[k]) if raw_name_counts else best_norm

            reasons: List[str] = []
            if best_norm in root_declarations:
                reasons.append("Observed on root/homepage declaration")
            if "JSON_LD" in candidate_sources[best_norm]:
                reasons.append("Explicit Organization / LocalBusiness JSON-LD markup")
            if "META_TAG" in candidate_sources[best_norm]:
                reasons.append("Declared via og:site_name meta signal")
            if "VISIBLE_HTML" in candidate_sources[best_norm]:
                reasons.append("Observed in footer copyright/branding notices")
            reasons.append(f"Present across {candidate_frequencies[best_norm]} of {len(records_to_process)} crawled pages")

            primary_candidate = PrimaryOrganizationCandidate(
                candidate_name=display_name,
                selection_reasons=reasons,
                evidence_sources=sorted(list(candidate_sources[best_norm])),
                confidence_nature=EvidenceNature.OBSERVED,
            )

        # ---------------------------------------------------------------------
        # 2. Cross-Page Entity Inconsistencies Detection
        # ---------------------------------------------------------------------
        inconsistencies: List[EntityInconsistency] = []

        # Check profiles that appear across multiple pages for attribute variations
        for norm, prof in entity_profiles.items():
            # Get canonical display name
            disp_name = norm
            if prof["names"]:
                disp_name = max(prof["names"].keys(), key=lambda k: len(prof["names"][k]))

            # A. Conflicting Names (significant divergence under same core profile)
            if len(prof["names"]) > 1:
                # Group by exact string
                distinct_names = list(prof["names"].keys())
                # Check if variations are more than minor case differences
                unique_lower = {n.strip().lower() for n in distinct_names}
                if len(unique_lower) > 1:
                    conflicts_dict = {n: prof["names"][n] for n in distinct_names}
                    inconsistencies.append(EntityInconsistency(
                        entity_type=EntityType.ORGANIZATION,
                        entity_name=disp_name,
                        attribute="name",
                        conflicting_values=conflicts_dict,
                        details=(
                            f"Multiple distinct organization name strings observed across crawled pages: "
                            f"{', '.join(f'\"{n}\" ({len(u)} pages)' for n, u in conflicts_dict.items())}."
                        ),
                    ))

            # B. Conflicting Addresses
            if len(prof["addresses"]) > 1:
                # Normalize address whitespace for comparison
                distinct_addrs = list(prof["addresses"].keys())
                unique_addrs = {re.sub(r"\s+", " ", a.strip().lower()) for a in distinct_addrs}
                if len(unique_addrs) > 1:
                    conflicts_dict = {a: prof["addresses"][a] for a in distinct_addrs}
                    inconsistencies.append(EntityInconsistency(
                        entity_type=EntityType.LOCAL_BUSINESS,
                        entity_name=disp_name,
                        attribute="address",
                        conflicting_values=conflicts_dict,
                        details=(
                            f"Multiple distinct physical addresses published for the same apparent organization: "
                            f"{'; '.join(f'\"{a}\" ({len(u)} pages)' for a, u in conflicts_dict.items())}."
                        ),
                    ))

            # C. Conflicting Phone Numbers
            if len(prof["phones"]) > 1:
                distinct_phones = list(prof["phones"].keys())
                # Compare normalized digit sets
                if len(set(distinct_phones)) > 1:
                    conflicts_dict = {p: prof["phones"][p] for p in distinct_phones}
                    inconsistencies.append(EntityInconsistency(
                        entity_type=EntityType.LOCAL_BUSINESS,
                        entity_name=disp_name,
                        attribute="telephone",
                        conflicting_values=conflicts_dict,
                        details=(
                            f"Multiple primary telephone numbers published across pages: "
                            f"{', '.join(f'{p} ({len(u)} pages)' for p, u in conflicts_dict.items())}."
                        ),
                    ))

            # D. Conflicting URLs / Domains declared in Structured Data
            if len(prof["urls"]) > 1:
                distinct_urls = list(prof["urls"].keys())
                # Compare hostnames / protocols
                hosts = {urlparse(u).netloc.lower() for u in distinct_urls if u}
                if len(hosts) > 1:
                    conflicts_dict = {u: prof["urls"][u] for u in distinct_urls}
                    inconsistencies.append(EntityInconsistency(
                        entity_type=EntityType.ORGANIZATION,
                        entity_name=disp_name,
                        attribute="url",
                        conflicting_values=conflicts_dict,
                        details=(
                            f"Structured data entity url references different domains: "
                            f"{', '.join(f'{u} ({len(pages)} pages)' for u, pages in conflicts_dict.items())}."
                        ),
                    ))

        # Unique entity count by normalized name
        unique_entities = {e.normalized_name or normalize_entity_name(e.name) for e in all_entities if e.name}

        result_intel = SiteEntityIntelligence(
            total_pages_evaluated=len(records_to_process),
            total_entities_detected=len(all_entities),
            unique_entities_count=len(unique_entities),
            primary_organization_candidate=primary_candidate,
            inconsistencies_count=len(inconsistencies),
            inconsistencies=inconsistencies,
            all_entities=all_entities,
            all_relationships=all_relationships,
            page_entity_evidence=page_evidence,
        )

        site_crawl.entity_intelligence = result_intel
        return result_intel
