"""
Internal Link Intelligence Engine for RankIntel (Phase 8.3).
Deterministic, evidence-driven extraction, classification, anchor text intelligence,
and link attribute inspection without redundant network fetches or LLMs.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from rankintel.models.schema import (
    LinkClassification,
    DiscoveredLinkItem,
    GenericAnchorOccurrence,
    InternalLinkEvidence,
    EvidenceNature,
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from rankintel.analyzers.record_lookup import RecordLookupIndex

# Common generic / non-descriptive anchor text phrases (normalized lowercase, punctuation-stripped)
GENERIC_ANCHOR_PATTERNS: Set[str] = {
    "click here",
    "click",
    "here",
    "read more",
    "learn more",
    "view more",
    "see more",
    "more",
    "more info",
    "more details",
    "details",
    "link",
    "page",
    "this page",
    "website",
    "source",
    "continue",
    "continue reading",
    "download",
    "get started",
    "find out more",
    "check it out",
    "go here",
    "view",
    "read",
    "open",
    "know more",
}

# Regex to strip non-alphanumeric characters for anchor pattern normalization
PUNCTUATION_REGEX = re.compile(r"[^\w\s]")


class InternalLinkEngine:
    """
    Deterministic Internal Link Intelligence Engine.
    Operates strictly on provided DOM / raw HTML without initiating network calls.
    """

    @classmethod
    def normalize_anchor_text(cls, text: str) -> str:
        """Normalize anchor text for matching generic patterns."""
        if not text:
            return ""
        # Strip brackets if tagged as image or aria
        clean = text
        if clean.startswith("[IMG:") and clean.endswith("]"):
            clean = clean[5:-1].strip()
        elif clean.startswith("[ARIA:") and clean.endswith("]"):
            clean = clean[6:-1].strip()

        # Lowercase, strip punctuation and extra whitespace
        norm = PUNCTUATION_REGEX.sub(" ", clean.lower())
        return " ".join(norm.split())

    @classmethod
    def is_generic_anchor(cls, anchor_text: str) -> bool:
        """Check if an anchor text matches known generic, non-descriptive patterns."""
        if not anchor_text or not anchor_text.strip():
            return False
        normalized = cls.normalize_anchor_text(anchor_text)
        return normalized in GENERIC_ANCHOR_PATTERNS

    @classmethod
    def extract_links_from_html(
        cls,
        raw_html: Optional[str],
        base_url: str,
        allow_subdomains: bool = False,
        lookup_index: Optional[RecordLookupIndex] = None,
    ) -> List[DiscoveredLinkItem]:
        """
        Extract all hyperlinks with full anchor semantics and link attributes
        from raw HTML without network requests.
        """
        if not raw_html or not raw_html.strip():
            return []

        from rankintel.analyzers.link_graph_engine import InternalLinkGraphEngine

        discovered: List[DiscoveredLinkItem] = []
        soup = BeautifulSoup(raw_html, "html.parser")

        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            if not raw_href:
                continue

            # Classify link target (INTERNAL, EXTERNAL, SPECIAL)
            classification = InternalLinkGraphEngine.classify_link(
                raw_href,
                base_url=base_url,
                allow_subdomains=allow_subdomains,
            )

            # Resolve full target URL
            if classification == LinkClassification.SPECIAL:
                full_target = raw_href
                target_identity = raw_href
            else:
                full_target = urljoin(base_url, raw_href)
                target_identity = InternalLinkGraphEngine.normalize_node_url(
                    full_target,
                    base_url=base_url,
                    lookup_index=lookup_index,
                )
                if not target_identity:
                    target_identity = full_target

            # Anchor text extraction: text, image alt, or ARIA label
            is_image_link = False
            image_alt: Optional[str] = None
            text_content = a.get_text(separator=" ", strip=True)

            if text_content:
                anchor_text = text_content
            else:
                # Check for nested images with alt text
                imgs = a.find_all("img")
                alts = [img.get("alt", "").strip() for img in imgs if img.get("alt", "").strip()]
                if alts:
                    is_image_link = True
                    image_alt = " ".join(alts)
                    anchor_text = f"[IMG: {image_alt}]"
                else:
                    # Check for accessible name attributes (aria-label, title)
                    aria_name = (a.get("aria-label") or a.get("title") or "").strip()
                    if aria_name:
                        anchor_text = f"[ARIA: {aria_name}]"
                    else:
                        anchor_text = ""

            is_empty_anchor = bool(len(anchor_text) == 0)

            # Link relationship attributes (rel="nofollow", etc.)
            rel_attr = a.get("rel", [])
            if isinstance(rel_attr, str):
                rel_list = [r.lower() for r in rel_attr.split()]
            elif isinstance(rel_attr, list):
                rel_list = [str(r).lower() for r in rel_attr]
            else:
                rel_list = []

            is_nofollow = "nofollow" in rel_list
            is_sponsored = "sponsored" in rel_list
            is_ugc = "ugc" in rel_list
            target_attr = a.get("target")

            discovered.append(DiscoveredLinkItem(
                source_url=base_url,
                target_url=full_target,
                target_identity_url=target_identity,
                anchor_text=anchor_text,
                is_empty_anchor=is_empty_anchor,
                is_image_link=is_image_link,
                image_alt=image_alt,
                rel_attributes=rel_list,
                is_nofollow=is_nofollow,
                is_sponsored=is_sponsored,
                is_ugc=is_ugc,
                target_attribute=target_attr,
                link_classification=classification,
            ))

        return discovered

    @classmethod
    def evaluate(
        cls,
        raw_html: Optional[str],
        url: str,
        allow_subdomains: bool = False,
        crawl_depth: Optional[int] = None,
        inbound_internal_count: Optional[int] = None,
    ) -> InternalLinkEvidence:
        """
        Evaluate internal link intelligence for a single page.
        """
        if not raw_html or not raw_html.strip():
            return InternalLinkEvidence(
                url=url,
                status=EvidenceNature.UNAVAILABLE,
                facts=["No HTML content was provided or response body was empty."],
                observations=["Internal link extraction unavailable for empty page body."],
            )

        links = cls.extract_links_from_html(
            raw_html=raw_html,
            base_url=url,
            allow_subdomains=allow_subdomains,
        )

        internal_links = [l for l in links if l.link_classification == LinkClassification.INTERNAL]
        external_links = [l for l in links if l.link_classification == LinkClassification.EXTERNAL]
        special_links = [l for l in links if l.link_classification == LinkClassification.SPECIAL]

        unique_internal_targets = {l.target_identity_url for l in internal_links}
        unique_external_targets = {l.target_url for l in external_links}

        nofollow_count = sum(1 for l in links if l.is_nofollow)
        empty_anchors = [l for l in internal_links if l.is_empty_anchor]
        empty_anchor_count = len(empty_anchors)

        # Track generic anchor occurrences on internal links
        generic_counts: Dict[Tuple[str, str], int] = {}
        for l in internal_links:
            if cls.is_generic_anchor(l.anchor_text):
                key = (l.anchor_text, l.target_identity_url)
                generic_counts[key] = generic_counts.get(key, 0) + 1

        generic_occurrences: List[GenericAnchorOccurrence] = [
            GenericAnchorOccurrence(anchor_text=k[0], target_url=k[1], count=c)
            for k, c in sorted(generic_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        generic_anchor_count = sum(c for c in generic_counts.values())

        # Construct factual telemetry notes
        facts: List[str] = [
            f"Observed {len(links)} total links: {len(internal_links)} internal ({len(unique_internal_targets)} unique destinations), {len(external_links)} external, {len(special_links)} special/fragment.",
        ]
        if nofollow_count > 0:
            facts.append(f"Observed {nofollow_count} links declaring rel='nofollow'.")
        if empty_anchor_count > 0:
            facts.append(f"Observed {empty_anchor_count} internal links with empty anchor text and no image alt or ARIA label.")
        if generic_anchor_count > 0:
            facts.append(f"Observed {generic_anchor_count} internal links using generic anchor patterns (e.g. {', '.join([g.anchor_text for g in generic_occurrences[:3]])}).")

        observations: List[str] = []
        if empty_anchor_count > 0:
            observations.append(
                f"{empty_anchor_count} internal links lack descriptive text; providing anchor text or accessible labels assists assistive technology and crawler navigation."
            )
        if generic_anchor_count > 0:
            observations.append(
                f"Generic anchor text observed across {generic_anchor_count} links; consider replacing non-descriptive phrases with topic-specific anchor text where appropriate."
            )
        if len(internal_links) == 0:
            observations.append("Page has 0 outgoing internal links to other pages within the site.")

        return InternalLinkEvidence(
            url=url,
            status=EvidenceNature.OBSERVED,
            total_links_found=len(links),
            internal_links_count=len(internal_links),
            external_links_count=len(external_links),
            special_links_count=len(special_links),
            unique_internal_outlinks_count=len(unique_internal_targets),
            unique_external_outlinks_count=len(unique_external_targets),
            nofollow_links_count=nofollow_count,
            empty_anchor_count=empty_anchor_count,
            generic_anchor_count=generic_anchor_count,
            generic_anchors=generic_occurrences,
            sample_internal_links=internal_links[:10],
            sample_external_links=external_links[:5],
            crawl_depth=crawl_depth,
            inbound_internal_count=inbound_internal_count,
            facts=facts,
            observations=observations,
        )
