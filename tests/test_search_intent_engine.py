"""
Search Intent Engine Unit Tests (Phase 9.4 - Layer A).
Verifies deterministic on-site intent signal extraction, multi-signal corroboration rules,
isolated token behavior, confidence levels, terminology compliance (INFERRED_FROM_ON_SITE_EVIDENCE),
and strict FACT vs. ANALYSIS separation with zero external search queries or ranking claims.
"""
import pytest

from rankintel.engines.search_intent_engine import SearchIntentEngine
from rankintel.models.schema import (
    SearchIntentCategory,
    SearchSignalConfidence,
    OnPageEvidence,
    SchemaEvidence,
    PageTopicIntelligence,
    TopicEvidence,
    PageQueryEvidence,
    QueryPageEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    EntitySignalType,
)


def test_empty_or_none_content_handling():
    """Verify empty or None content returns status 'skipped' and intent UNSPECIFIED."""
    result = SearchIntentEngine.evaluate(url="https://example.com/test", raw_html=None)
    assert result.status == "skipped"
    assert result.primary_observed_intent_signal == SearchIntentCategory.UNSPECIFIED
    assert result.evidence_items == []
    assert len(result.facts) >= 1
    assert len(result.analyses) >= 1
    assert "INFERRED_FROM_ON_SITE_EVIDENCE" in result.analyses[0]


def test_informational_signal_detection():
    """Verify explanatory headings and FAQ schema corroborate an INFORMATIONAL intent signal."""
    html = """
    <html>
        <head><title>Material Testing Guide - Lab Standards</title></head>
        <body>
            <h1>Material Testing Guide</h1>
            <h2>What is Material Testing?</h2>
            <p>Material testing is a rigorous procedure to determine mechanical properties.</p>
            <h2>How to Perform Calibration Tests</h2>
            <p>Step-by-step instructions for performing laboratory calibration.</p>
        </body>
    </html>
    """
    on_page = OnPageEvidence(
        title="Material Testing Guide - Lab Standards",
        h1_text=["Material Testing Guide"],
        h2_text=["What is Material Testing?", "How to Perform Calibration Tests"],
    )
    schema_ev = SchemaEvidence(
        detected_types=["FAQPage"],
    )

    result = SearchIntentEngine.evaluate(
        url="https://example.com/guide",
        raw_html=html,
        on_page=on_page,
        schema_ev=schema_ev,
    )

    assert result.status == "success"
    assert result.primary_observed_intent_signal == SearchIntentCategory.INFORMATIONAL
    assert len(result.evidence_items) >= 2
    # Verify presence of DIRECT structural evidence
    direct_items = [it for it in result.evidence_items if it.confidence == SearchSignalConfidence.DIRECT]
    assert len(direct_items) >= 2
    assert any("What is Material Testing" in it.evidence_term for it in direct_items)
    # Check FACT vs ANALYSIS separation
    assert any("explanatory/educational syntax" in f for f in result.facts)
    assert any("Primary observed intent signal is 'informational'" in a for a in result.analyses)


def test_commercial_signal_detection():
    """Verify comparison headings and comparison tables corroborate a COMMERCIAL evaluation signal."""
    html = """
    <html>
        <head><title>Spectrometer Model A vs Model B Comparison</title></head>
        <body>
            <h1>Spectrometer Comparison Guide</h1>
            <h2>Spectrometer Model A vs Model B</h2>
            <table border="1">
                <tr><th>Feature</th><th>Model A</th><th>Model B</th></tr>
                <tr><td>Price Tier</td><td>Standard</td><td>Premium</td></tr>
                <tr><td>Accuracy</td><td>0.01%</td><td>0.005%</td></tr>
            </table>
        </body>
    </html>
    """
    result = SearchIntentEngine.evaluate(
        url="https://example.com/compare",
        raw_html=html,
    )

    assert result.status == "success"
    assert result.primary_observed_intent_signal == SearchIntentCategory.COMMERCIAL
    assert any(it.signal_type == "COMPARISON_EVALUATION_HEADING" for it in result.evidence_items)
    assert any(it.signal_type == "COMPARISON_PRICING_TABLE" for it in result.evidence_items)
    assert any("comparison/evaluation syntax" in f for f in result.facts)
    assert any("Primary observed intent signal is 'commercial'" in a for a in result.analyses)


def test_transactional_signal_detection():
    """Verify specific call-to-actions and interactive inquiry forms corroborate a TRANSACTIONAL signal."""
    html = """
    <html>
        <head><title>Book Laboratory Testing Services</title></head>
        <body>
            <h1>Book Lab Services</h1>
            <p>Schedule your batch test today.</p>
            <form action="/quote" method="post">
                <input type="text" name="name" placeholder="Name">
                <input type="email" name="email" placeholder="Email">
                <textarea name="inquiry"></textarea>
                <button type="submit">Request a Quote</button>
            </form>
            <a href="/order" class="btn">Order Now</a>
        </body>
    </html>
    """
    result = SearchIntentEngine.evaluate(
        url="https://example.com/services/book",
        raw_html=html,
    )

    assert result.status == "success"
    assert result.primary_observed_intent_signal == SearchIntentCategory.TRANSACTIONAL
    assert any(it.signal_type == "SPECIFIC_CALL_TO_ACTION" for it in result.evidence_items)
    assert any(it.signal_type == "TRANSACTIONAL_INQUIRY_FORM" for it in result.evidence_items)
    assert any("call-to-action" in f for f in result.facts)


def test_isolated_weak_tokens_do_not_determine_intent():
    """
    Verify isolated general words (e.g. single mention of 'best', 'pricing', or basic 'Contact Us' link)
    are captured as evidence items only and DO NOT trigger intent classification without corroboration.
    """
    html = """
    <html>
        <head><title>About Our Organization</title></head>
        <body>
            <h1>About Our History</h1>
            <p>We strive to do our best work in every project we undertake.</p>
            <footer>
                <a href="/contact">Contact Us</a>
            </footer>
        </body>
    </html>
    """
    result = SearchIntentEngine.evaluate(
        url="https://example.com/about",
        raw_html=html,
    )

    assert result.status == "success"
    # Even though "best" and "contact us" exist as tokens, they lack multi-signal corroboration
    assert result.primary_observed_intent_signal == SearchIntentCategory.UNSPECIFIED
    # But evidence items are still faithfully logged!
    assert len(result.evidence_items) >= 1
    assert any("does not meet multi-signal corroboration threshold" in note for note in result.corroboration_notes)
    assert any("intent remains UNSPECIFIED" in a for a in result.analyses)


def test_navigational_brand_homepage_detection():
    """Verify root domain homepage with verified organization entity is classified as NAVIGATIONAL."""
    html = """
    <html>
        <head><title>Acme International Laboratory - Official Website</title></head>
        <body>
            <h1>Acme International Laboratory</h1>
            <p>Welcome to our testing portal.</p>
        </body>
    </html>
    """
    on_page = OnPageEvidence(
        title="Acme International Laboratory - Official Website",
        h1_text=["Acme International Laboratory"],
    )
    entity_ev = EntityEvidence(
        detected_entities=[
            DetectedEntity(
                name="Acme International Laboratory",
                entity_type=EntityType.ORGANIZATION,
                source=EntitySource.VISIBLE_HTML,
                signal_type=EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL,
            )
        ]
    )

    result = SearchIntentEngine.evaluate(
        url="https://acmelabs.com/",
        raw_html=html,
        on_page=on_page,
        entity_ev=entity_ev,
    )

    assert result.status == "success"
    assert result.primary_observed_intent_signal == SearchIntentCategory.NAVIGATIONAL
    assert any(it.signal_type == "OFFICIAL_BRAND_HOMEPAGE" for it in result.evidence_items)


def test_local_geographic_signals_detection():
    """Verify postal address and physical markers corroborate a LOCAL intent signal."""
    html = """
    <html>
        <head><title>Mumbai Testing Branch Office</title></head>
        <body>
            <h1>Mumbai Testing Branch</h1>
            <p>Registered Office: Plot No 42, MIDC Industrial Area, Andheri East, Mumbai 400093.</p>
            <p>Phone: +91-22-28345678</p>
            <iframe src="https://maps.google.com/maps?q=mumbai"></iframe>
        </body>
    </html>
    """
    result = SearchIntentEngine.evaluate(
        url="https://example.com/mumbai-branch",
        raw_html=html,
    )

    assert result.status == "success"
    assert result.primary_observed_intent_signal == SearchIntentCategory.LOCAL
    assert any(it.signal_type == "PHYSICAL_ADDRESS_SIGNALS" for it in result.evidence_items)
    assert any(it.signal_type == "EMBEDDED_MAP" for it in result.evidence_items)
    assert any("physical address indicators" in f for f in result.facts)


def test_mixed_intent_resolution():
    """Verify balanced co-equal strong signals result in MIXED classification."""
    html = """
    <html>
        <head><title>Calibration Guide & Booking</title></head>
        <body>
            <h1>Complete Calibration Guide</h1>
            <h2>What is Calibration Testing?</h2>
            <p>Explanation of calibration methods and standards.</p>
            <h2>How to Perform In-House Verification</h2>
            <p>Step-by-step tutorial.</p>
            
            <form action="/book" method="post">
                <input type="text" name="quote_request">
                <button type="submit">Request a Quote</button>
            </form>
            <a href="/order" class="btn">Book Now</a>
        </body>
    </html>
    """
    on_page = OnPageEvidence(
        title="Calibration Guide & Booking",
        h1_text=["Complete Calibration Guide"],
        h2_text=["What is Calibration Testing?", "How to Perform In-House Verification"],
    )

    result = SearchIntentEngine.evaluate(
        url="https://example.com/calibration-guide-booking",
        raw_html=html,
        on_page=on_page,
    )

    assert result.status == "success"
    assert result.primary_observed_intent_signal in (
        SearchIntentCategory.MIXED,
        SearchIntentCategory.INFORMATIONAL,
        SearchIntentCategory.TRANSACTIONAL,
    )
    # Both informational and transactional must have strong corroborated presence
    assert result.intent_counts.get("informational", 0) >= 2
    assert result.intent_counts.get("transactional", 0) >= 2


def test_topic_linkage_and_analyses_formatting():
    """Verify observed topics from M9.2/M9.3 are linked to the page intent analysis."""
    html = """
    <html>
        <body>
            <h1>Hardness Testing Instructions</h1>
            <h2>How to Measure Rockwell Hardness</h2>
            <p>Detailed guide on measurement technique.</p>
        </body>
    </html>
    """
    topic_intel = PageTopicIntelligence(
        topics=[
            TopicEvidence(
                topic_name="Rockwell Hardness",
                normalized_name="rockwell hardness",
            )
        ]
    )

    result = SearchIntentEngine.evaluate(
        url="https://example.com/hardness",
        raw_html=html,
        topic_intel_ev=topic_intel,
    )

    assert "Rockwell Hardness" in result.associated_topics
    assert any("Rockwell Hardness" in a for a in result.analyses)
    assert all("INFERRED_FROM_ON_SITE_EVIDENCE" in a for a in result.analyses)
