"""
Unit tests for Content Intelligence Engine (Phase 8.1).
Validates main content extraction, thin-content indicators, exact SHA-256 hashing,
SimHash near-duplicate fingerprinting, Title-H1 alignment, and heading hierarchy signals.
"""
import pytest
from bs4 import BeautifulSoup

from rankintel.engines.content_engine import ContentEngine
from rankintel.models.schema import (
    ContentExtractionMethod,
    WordCountTier,
    TitleH1AlignmentStatus,
)


def test_empty_or_none_html():
    evidence_none = ContentEngine.evaluate(None, url="https://example.com")
    assert evidence_none.extraction_method == ContentExtractionMethod.UNAVAILABLE
    assert evidence_none.main_content_word_count == 0
    assert evidence_none.thin_content.is_empty_or_whitespace is True
    assert evidence_none.thin_content.word_count_tier == WordCountTier.UNAVAILABLE

    evidence_empty = ContentEngine.evaluate("   \n  ", url="https://example.com")
    assert evidence_empty.extraction_method == ContentExtractionMethod.UNAVAILABLE
    assert evidence_empty.main_content_word_count == 0


def test_semantic_main_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <nav><a href="/">Home</a><a href="/about">About</a><a href="/contact">Contact</a></nav>
        <main>
            <h1>Primary Heading</h1>
            <p>This is the primary editorial text inside the semantic main element of the HTML document.
            It provides detailed context, explanations, and key facts about the subject matter discussed.</p>
        </main>
        <footer><p>&copy; 2026 Example Corp. All rights reserved.</p></footer>
    </body>
    </html>
    """
    evidence = ContentEngine.evaluate(html, url="https://example.com")
    assert evidence.extraction_method == ContentExtractionMethod.SEMANTIC_MAIN
    assert "primary editorial text" in evidence.main_content_text_preview
    assert evidence.main_content_word_count > 20
    assert evidence.thin_content.word_count_tier in (WordCountTier.VERY_LOW, WordCountTier.LOW)


def test_semantic_article_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Article Hub</title></head>
    <body>
        <header><div class="menu">Site Header Navigation Menu</div></header>
        <div class="content-wrapper">
            <article>
                <h1>Breaking News Story</h1>
                <p>The research consortium announced groundbreaking experimental findings today regarding quantum computing architectures.
                These benchmarks indicate significant performance improvements over classical semiconductor designs.</p>
            </article>
        </div>
        <div class="sidebar">Related links and advertisements</div>
    </body>
    </html>
    """
    evidence = ContentEngine.evaluate(html, url="https://example.com/news")
    assert evidence.extraction_method == ContentExtractionMethod.SEMANTIC_ARTICLE
    assert "research consortium announced" in evidence.main_content_text_preview


def test_role_main_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>App Page</title></head>
    <body>
        <div class="top-nav">Navigation Items</div>
        <div role="main" id="app-container">
            <h1>Application Dashboard</h1>
            <p>Welcome to the multi-engine intelligence command center for autonomous search engine auditing.
            Access real-time telemetry, Core Web Vitals measurements, and technical conflict reconciliations.</p>
        </div>
    </body>
    </html>
    """
    evidence = ContentEngine.evaluate(html, url="https://example.com/app")
    assert evidence.extraction_method == ContentExtractionMethod.ROLE_MAIN
    assert "command center" in evidence.main_content_text_preview


def test_heuristic_pruned_body_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Legacy Site</title></head>
    <body>
        <div class="site-header">Header with company logo and banner</div>
        <div class="main-navigation">Home | Products | Contact | Careers | Blog</div>
        <div class="page-body">
            <h1>Industrial Testing Laboratory Services</h1>
            <p>Our ISO 17025 accredited laboratory conducts mechanical, chemical, and non-destructive testing for engineering materials.
            We provide fast turnaround times and certified metallurgical reporting for global supply chains.</p>
        </div>
        <div id="sidebar-widgets" class="sidebar">Widget links and promo banner</div>
        <div class="footer-copyright">Copyright 2026 Test Labs</div>
    </body>
    </html>
    """
    evidence = ContentEngine.evaluate(html, url="https://example.com/legacy")
    assert evidence.extraction_method == ContentExtractionMethod.HEURISTIC_PRUNED_BODY
    assert "ISO 17025 accredited" in evidence.main_content_text_preview
    assert "Header with company logo" not in evidence.main_content_text_preview
    assert "Widget links and promo" not in evidence.main_content_text_preview


def test_thin_content_indicators_and_placeholders():
    # Empty content
    html_empty = "<html><body><main></main></body></html>"
    ev_empty = ContentEngine.evaluate(html_empty, url="https://example.com/empty")
    assert ev_empty.thin_content.is_empty_or_whitespace is True
    assert ev_empty.thin_content.word_count_tier == WordCountTier.EMPTY

    # Placeholder copy
    html_placeholder = """
    <html><body><main>
        <h1>Welcome</h1>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. This site is currently under construction. Please check back coming soon.</p>
    </main></body></html>
    """
    ev_placeholder = ContentEngine.evaluate(html_placeholder, url="https://example.com/wip")
    assert ev_placeholder.thin_content.placeholder_text_detected is True
    assert any("under construction" in s.lower() for s in ev_placeholder.thin_content.placeholder_snippets)
    assert any("lorem ipsum" in s.lower() for s in ev_placeholder.thin_content.placeholder_snippets)

    # Substantive content (measurement bucket, not a good/bad score)
    substantive_text = " ".join(["editorial word"] * 350)
    html_substantive = f"<html><body><main><h1>Guide</h1><p>{substantive_text}</p><p>{substantive_text}</p></main></body></html>"
    ev_sub = ContentEngine.evaluate(html_substantive, url="https://example.com/guide")
    assert ev_sub.thin_content.word_count_tier == WordCountTier.SUBSTANTIVE
    assert ev_sub.thin_content.has_substantive_content is True


def test_exact_content_hash_and_html_hash():
    text_1 = "This is a clean editorial paragraph with numbers 123 and symbols."
    text_2 = "   THIS is a clean editorial paragraph WITH numbers 123 and symbols.   "
    text_diff = "This is a completely different text paragraph."

    hash_1 = ContentEngine.compute_exact_hash(text_1)
    hash_2 = ContentEngine.compute_exact_hash(text_2)
    hash_diff = ContentEngine.compute_exact_hash(text_diff)

    assert hash_1 == hash_2
    assert hash_1 != hash_diff
    assert len(hash_1) == 64

    # HTML hash
    html_a = "<html><body><h1>Title</h1><p>Body</p></body></html>"
    html_b = "<html><body><h1>Title</h1><p>Body</p></body></html>"
    html_c = "<html><body><h1>Title</h1><p>Body with footer</p></body></html>"
    assert ContentEngine.compute_html_hash(html_a) == ContentEngine.compute_html_hash(html_b)
    assert ContentEngine.compute_html_hash(html_a) != ContentEngine.compute_html_hash(html_c)


def test_simhash_generation_and_hamming():
    doc_a = "The quick brown fox jumps over the lazy dog in the sunny meadow with green grass."
    doc_near = "The quick brown fox jumps over the sleepy dog in the sunny meadow with green grass."
    doc_far = "Quantum computing architectures provide exponential acceleration for cryptographic simulations."

    sim_a = ContentEngine.compute_simhash(doc_a)
    sim_near = ContentEngine.compute_simhash(doc_near)
    sim_far = ContentEngine.compute_simhash(doc_far)

    assert len(sim_a) == 16
    assert len(sim_near) == 16
    assert len(sim_far) == 16

    dist_near = ContentEngine.calculate_simhash_hamming(sim_a, sim_near)
    dist_far = ContentEngine.calculate_simhash_hamming(sim_a, sim_far)

    # Near duplicate should have very small bit divergence, far document has large bit divergence
    assert dist_near <= 6
    assert dist_far > dist_near


def test_shingle_jaccard_similarity():
    text_a = "Search engine optimization and generative engine optimization are critical for AI visibility."
    text_b = "Search engine optimization and generative engine optimization are essential for AI visibility."
    text_c = "Cooking recipes for homemade pasta dough with eggs and flour."

    jaccard_ab = ContentEngine.calculate_shingle_jaccard(text_a, text_b, k=3)
    jaccard_ac = ContentEngine.calculate_shingle_jaccard(text_a, text_c, k=3)

    assert jaccard_ab >= 0.70
    assert jaccard_ac == 0.0


def test_title_h1_relationship_signals():
    # Strong alignment
    html_aligned = """
    <html>
    <head><title>Enterprise Metallurgy Testing - RankIntel</title></head>
    <body><main>
        <h1>Enterprise Metallurgy Testing</h1>
        <p>Enterprise metallurgy testing is critical for aerospace components. Our engineers verify metal tensile strength.</p>
    </main></body>
    </html>
    """
    ev_aligned = ContentEngine.evaluate(html_aligned, url="https://example.com/metallurgy")
    t_rel = ev_aligned.title_h1_relationship
    assert t_rel.alignment_status == TitleH1AlignmentStatus.STRONG_ALIGNMENT
    assert t_rel.h1_in_title is True
    assert t_rel.token_overlap_ratio >= 0.50
    assert t_rel.lead_content_keyword_ratio > 0.0

    # Misaligned
    html_misaligned = """
    <html>
    <head><title>Online Store Shoes Catalog</title></head>
    <body><main>
        <h1>Chemical Fertilizer Solutions</h1>
        <p>Nitrogen based agricultural products for commercial crop harvesting.</p>
    </main></body>
    </html>
    """
    ev_mis = ContentEngine.evaluate(html_misaligned, url="https://example.com/catalog")
    assert ev_mis.title_h1_relationship.alignment_status == TitleH1AlignmentStatus.MISALIGNED

    # Missing Title or H1
    html_missing_h1 = "<html><head><title>Title Only</title></head><body><p>Text</p></body></html>"
    ev_no_h1 = ContentEngine.evaluate(html_missing_h1, url="https://example.com/no-h1")
    assert ev_no_h1.title_h1_relationship.alignment_status == TitleH1AlignmentStatus.UNAVAILABLE


def test_heading_structure_signals():
    # Valid hierarchy
    html_valid = """
    <html><body>
        <h1>Main Topic</h1>
        <p>Introductory paragraph</p>
        <h2>Subtopic 1</h2>
        <p>Details about subtopic 1</p>
        <h3>Sub-subtopic A</h3>
        <p>Deep details</p>
        <h2>Subtopic 2</h2>
        <p>Details about subtopic 2</p>
    </body></html>
    """
    ev_valid = ContentEngine.evaluate(html_valid, url="https://example.com/valid")
    h = ev_valid.heading_structure
    assert h.h1_count == 1
    assert h.h2_count == 2
    assert h.h3_count == 1
    assert h.heading_hierarchy_valid is True
    assert len(h.heading_skips) == 0
    assert h.average_words_per_section > 0

    # Skips and empty headings
    html_skips = """
    <html><body>
        <h1>Root Topic</h1>
        <h3>Skipped directly to H3 without H2</h3>
        <p>Some text</p>
        <h2></h2>
        <h4>Skipped to H4 without H3</h4>
        <p>More text</p>
        <h1>Second H1 heading</h1>
    </body></html>
    """
    ev_skips = ContentEngine.evaluate(html_skips, url="https://example.com/skips")
    h_skips = ev_skips.heading_structure
    assert h_skips.heading_hierarchy_valid is False
    assert len(h_skips.heading_skips) >= 1
    assert h_skips.multiple_h1_detected is True
    assert h_skips.empty_headings_count >= 1
