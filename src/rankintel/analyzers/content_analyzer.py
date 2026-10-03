"""
Site Content Analyzer — Cross-page multi-page crawl content intelligence:
Detects exact main-content duplicates, near-duplicate page pairs (via SimHash & shingle Jaccard),
repeated boilerplate text blocks, and site-wide structure issues.
"""
from __future__ import annotations
import re
from typing import Dict, List, Set
from collections import defaultdict
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    SiteCrawlResult,
    SiteContentIntelligence,
    ExactDuplicateCluster,
    NearDuplicatePair,
    RepeatedBoilerplateBlock,
    ContentEvidence,
    WordCountTier,
    TitleH1AlignmentStatus,
)
from rankintel.engines.content_engine import ContentEngine, BOILERPLATE_TAGS


class SiteContentAnalyzer:
    """
    Analyzes site-wide content evidence from CrawlRecord raw_html
    without initiating any network requests.
    """

    @classmethod
    def analyze_site(cls, site_crawl: SiteCrawlResult) -> SiteContentIntelligence:
        """
        Processes all crawled HTML documents in site_crawl to detect exact duplicates,
        near-duplicates, repeated boilerplate, and structural anomalies.
        """
        page_evidence: Dict[str, ContentEvidence] = {}
        exact_hash_to_urls: Dict[str, List[str]] = defaultdict(list)
        clean_text_by_url: Dict[str, str] = {}
        block_to_urls: Dict[str, Set[str]] = defaultdict(set)

        thin_urls: List[str] = []
        heading_skip_urls: List[str] = []
        title_h1_mismatch_urls: List[str] = []

        # 1. Evaluate individual pages
        records_to_process = [
            rec for rec in site_crawl.crawl_records
            if (rec.status_code == 200 or rec.status_code is None) and rec.raw_html
        ]

        for rec in records_to_process:
            url = rec.url
            html = rec.raw_html

            evidence = ContentEngine.evaluate(
                raw_html=html,
                url=url,
                title=getattr(rec, "title", None),
                h1_list=[rec.h1] if getattr(rec, "h1", None) else None,
            )
            page_evidence[url] = evidence

            # Track exact duplicate main content hash
            if evidence.exact_content_hash and evidence.main_content_word_count > 0:
                exact_hash_to_urls[evidence.exact_content_hash].append(url)

            # Extract clean main text for near-duplicate comparison
            soup = BeautifulSoup(html, "html.parser")
            main_text, _, _ = ContentEngine.extract_main_content(soup)
            clean_text_by_url[url] = main_text

            # Extract paragraphs / text blocks (> 6 words) for boilerplate detection
            body = soup.find("body") or soup
            for elem in body.find_all(["p", "li", "div", "section"]):
                # Avoid nesting duplicate extracts
                if elem.find(["p", "div", "section"]):
                    continue
                block_text = elem.get_text(separator=" ", strip=True)
                words = block_text.split()
                if len(words) >= 6:
                    norm_block = re.sub(r"[^\w\s]", "", block_text.lower())
                    norm_block = re.sub(r"\s+", " ", norm_block).strip()
                    if len(norm_block.split()) >= 6:
                        block_to_urls[norm_block].add(url)

            # Factual indicators tracking
            if evidence.thin_content.word_count_tier in (WordCountTier.EMPTY, WordCountTier.VERY_LOW, WordCountTier.LOW):
                thin_urls.append(url)

            if len(evidence.heading_structure.heading_skips) > 0:
                heading_skip_urls.append(url)

            if evidence.title_h1_relationship.alignment_status in (
                TitleH1AlignmentStatus.MISALIGNED,
                TitleH1AlignmentStatus.WEAK_ALIGNMENT,
            ):
                title_h1_mismatch_urls.append(url)

        # 2. Exact Duplicate Main-Content Clusters
        exact_clusters: List[ExactDuplicateCluster] = []
        cluster_idx = 1
        for content_hash, urls in exact_hash_to_urls.items():
            if len(urls) > 1:
                sample_ev = page_evidence.get(urls[0])
                wc = sample_ev.main_content_word_count if sample_ev else 0
                exact_clusters.append(ExactDuplicateCluster(
                    cluster_id=f"exact_cluster_{cluster_idx}",
                    content_hash=content_hash,
                    word_count=wc,
                    urls=sorted(urls)
                ))
                cluster_idx += 1

        # 3. Near-Duplicate Page Pairs (SimHash & 3-gram Jaccard)
        near_duplicate_pairs: List[NearDuplicatePair] = []
        crawled_urls = list(clean_text_by_url.keys())
        checked_pairs: Set[tuple[str, str]] = set()

        for i in range(len(crawled_urls)):
            for j in range(i + 1, len(crawled_urls)):
                url_a = crawled_urls[i]
                url_b = crawled_urls[j]

                # If already an exact duplicate, skip near-duplicate duplicate listing
                ev_a = page_evidence.get(url_a)
                ev_b = page_evidence.get(url_b)
                if ev_a and ev_b and ev_a.exact_content_hash and ev_a.exact_content_hash == ev_b.exact_content_hash:
                    continue

                simhash_a = ev_a.simhash if ev_a else ""
                simhash_b = ev_b.simhash if ev_b else ""
                ham_dist = ContentEngine.calculate_simhash_hamming(simhash_a, simhash_b)

                # Pre-filter candidate pairs using SimHash Hamming distance or similar length
                wc_diff = abs((ev_a.main_content_word_count if ev_a else 0) - (ev_b.main_content_word_count if ev_b else 0))
                if ham_dist <= 12 or wc_diff <= 30:
                    text_a = clean_text_by_url.get(url_a, "")
                    text_b = clean_text_by_url.get(url_b, "")
                    jaccard = ContentEngine.calculate_shingle_jaccard(text_a, text_b, k=3)

                    # Threshold: >= 80% shingle overlap confirms near-duplicate relationship
                    if jaccard >= 0.80:
                        pair_key = (min(url_a, url_b), max(url_a, url_b))
                        if pair_key not in checked_pairs:
                            checked_pairs.add(pair_key)
                            near_duplicate_pairs.append(NearDuplicatePair(
                                url_a=pair_key[0],
                                url_b=pair_key[1],
                                similarity_percentage=round(jaccard * 100, 1),
                                hamming_distance=ham_dist,
                                method="simhash_shingle_jaccard"
                            ))

        # 4. Repeated Boilerplate Blocks Detection
        repeated_blocks: List[RepeatedBoilerplateBlock] = []
        total_pages = len(records_to_process)
        min_page_threshold = 3 if total_pages >= 4 else max(2, total_pages)

        for block_text, urls in block_to_urls.items():
            if len(urls) >= min_page_threshold:
                w_count = len(block_text.split())
                # Only surface substantial repeated blocks (>= 8 words)
                if w_count >= 8:
                    snippet = block_text[:100] + ("..." if len(block_text) > 100 else "")
                    repeated_blocks.append(RepeatedBoilerplateBlock(
                        text_snippet=snippet,
                        word_count=w_count,
                        page_count=len(urls),
                        pages=sorted(list(urls))
                    ))

        # Sort repeated blocks by frequency descending
        repeated_blocks.sort(key=lambda b: b.page_count, reverse=True)

        summary = SiteContentIntelligence(
            total_pages_evaluated=len(records_to_process),
            exact_duplicate_clusters_count=len(exact_clusters),
            exact_duplicate_clusters=exact_clusters,
            near_duplicate_pairs_count=len(near_duplicate_pairs),
            near_duplicate_pairs=near_duplicate_pairs,
            repeated_boilerplate_blocks_count=len(repeated_blocks),
            repeated_boilerplate_blocks=repeated_blocks[:10],  # Keep top 10 repeated blocks
            thin_content_urls=sorted(list(set(thin_urls))),
            heading_skip_urls=sorted(list(set(heading_skip_urls))),
            title_h1_mismatch_urls=sorted(list(set(title_h1_mismatch_urls))),
            page_content_evidence=page_evidence,
        )

        site_crawl.content_intelligence = summary
        return summary
