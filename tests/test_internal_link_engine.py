"""
Unit tests for InternalLinkEngine (Phase 8.3).
Tests link extraction, normalization, classification, anchor text, empty anchors,
image alt handling, rel attributes, generic anchor patterns, and single-page evaluation.
Zero live HTTP requests — completely deterministic offline tests.
"""
import pytest
from rankintel.models.schema import (
    LinkClassification,
    EvidenceNature,
)
from rankintel.engines.internal_link_engine import InternalLinkEngine


def test_extract_links_classification():
    html = """
    <html>
        <body>
            <a href="/about">About Us</a>
            <a href="https://example.com/services">Our Services</a>
            <a href="https://google.com">Google</a>
            <a href="mailto:info@example.com">Email Us</a>
            <a href="tel:+1234567890">Call</a>
            <a href="javascript:void(0);">Do Nothing</a>
            <a href="#top">Back to top</a>
        </body>
    </html>
    """
    links = InternalLinkEngine.extract_links_from_html(html, "https://example.com")
    assert len(links) == 7

    internals = [l for l in links if l.link_classification == LinkClassification.INTERNAL]
    externals = [l for l in links if l.link_classification == LinkClassification.EXTERNAL]
    specials = [l for l in links if l.link_classification == LinkClassification.SPECIAL]

    assert len(internals) == 2
    assert len(externals) == 1
    assert len(specials) == 4

    assert internals[0].target_url == "https://example.com/about"
    assert internals[0].anchor_text == "About Us"
    assert internals[1].target_url == "https://example.com/services"
    assert externals[0].target_url == "https://google.com"


def test_anchor_text_extraction_plain_text():
    html = '<a href="/pricing">View Pricing Plans</a>'
    links = InternalLinkEngine.extract_links_from_html(html, "https://example.com")
    assert len(links) == 1
    assert links[0].anchor_text == "View Pricing Plans"
    assert not links[0].is_empty_anchor
    assert not links[0].is_image_link


def test_anchor_text_extraction_image_alt():
    html = '<a href="/"><img src="/logo.png" alt="Company Logo"></a>'
    links = InternalLinkEngine.extract_links_from_html(html, "https://example.com")
    assert len(links) == 1
    assert links[0].is_image_link
    assert links[0].image_alt == "Company Logo"
    assert links[0].anchor_text == "[IMG: Company Logo]"
    assert not links[0].is_empty_anchor


def test_anchor_text_extraction_aria_label():
    html = '<a href="/search" aria-label="Search site"><svg></svg></a>'
    links = InternalLinkEngine.extract_links_from_html(html, "https://example.com")
    assert len(links) == 1
    assert links[0].anchor_text == "[ARIA: Search site]"
    assert not links[0].is_empty_anchor


def test_empty_anchor_detection():
    html = """
    <div>
        <a href="/empty1"></a>
        <a href="/empty2">   </a>
        <a href="/empty3"><img src="/blank.gif"></a>
        <a href="/empty4"><span></span></a>
    </div>
    """
    links = InternalLinkEngine.extract_links_from_html(html, "https://example.com")
    assert len(links) == 4
    for link in links:
        assert link.is_empty_anchor
        assert link.anchor_text == ""


def test_rel_attributes_parsing():
    html = """
    <div>
        <a href="/internal-nofollow" rel="nofollow">No Follow</a>
        <a href="https://partner.com" rel="sponsored noopener">Sponsored</a>
        <a href="/forum" rel="ugc">Forum Post</a>
        <a href="/normal">Normal Link</a>
    </div>
    """
    links = InternalLinkEngine.extract_links_from_html(html, "https://example.com")
    assert len(links) == 4

    assert links[0].is_nofollow
    assert not links[0].is_sponsored
    assert not links[0].is_ugc

    assert links[1].is_sponsored
    assert "noopener" in links[1].rel_attributes

    assert links[2].is_ugc
    assert not links[3].is_nofollow


def test_generic_anchor_detection():
    assert InternalLinkEngine.is_generic_anchor("Click here")
    assert InternalLinkEngine.is_generic_anchor("CLICK HERE")
    assert InternalLinkEngine.is_generic_anchor("read more...")
    assert InternalLinkEngine.is_generic_anchor("Learn More!")
    assert InternalLinkEngine.is_generic_anchor("here")
    assert InternalLinkEngine.is_generic_anchor("more details")
    assert InternalLinkEngine.is_generic_anchor("download")
    assert InternalLinkEngine.is_generic_anchor("know more")

    # Topic-specific anchors should NOT be flagged as generic
    assert not InternalLinkEngine.is_generic_anchor("Enterprise Pricing Plans")
    assert not InternalLinkEngine.is_generic_anchor("Read our comprehensive technical guide")
    assert not InternalLinkEngine.is_generic_anchor("Contact our sales team")
    assert not InternalLinkEngine.is_generic_anchor("Quality Assurance Certification")


def test_evaluate_populated_page():
    html = """
    <!DOCTYPE html>
    <html>
        <head><title>Test Page</title></head>
        <body>
            <header>
                <a href="/"><img src="/logo.png" alt="Brand Logo"></a>
                <a href="/features">Features</a>
                <a href="/pricing">Pricing</a>
            </header>
            <main>
                <h1>Welcome</h1>
                <p>Read our announcement: <a href="/blog/launch">Read more</a></p>
                <p>Visit our sponsor: <a href="https://external.com" rel="sponsored">Sponsor</a></p>
                <p>Empty link: <a href="/subpage"></a></p>
            </main>
        </body>
    </html>
    """
    evidence = InternalLinkEngine.evaluate(html, "https://example.com")
    assert evidence.status == EvidenceNature.OBSERVED
    assert evidence.total_links_found == 6
    assert evidence.internal_links_count == 5
    assert evidence.external_links_count == 1
    assert evidence.empty_anchor_count == 1
    assert evidence.generic_anchor_count == 1
    assert len(evidence.generic_anchors) == 1
    assert evidence.generic_anchors[0].anchor_text == "Read more"
    assert len(evidence.facts) > 0
    assert len(evidence.observations) > 0


def test_evaluate_empty_html():
    evidence = InternalLinkEngine.evaluate(None, "https://example.com")
    assert evidence.status == EvidenceNature.UNAVAILABLE
    assert evidence.total_links_found == 0
    assert "No HTML content was provided" in evidence.facts[0]

    evidence_whitespace = InternalLinkEngine.evaluate("   \n\t  ", "https://example.com")
    assert evidence_whitespace.status == EvidenceNature.UNAVAILABLE
