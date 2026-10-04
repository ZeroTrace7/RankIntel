"""
Unit test suite for RankIntel Phase 10.3: Claim Grounding & Entity Intelligence Engine.

Verifies deterministic claim extraction, on-site grounding support evaluation,
multi-surface entity consistency, structured-vs-visible agreement, and strict
adherence to:
1. Strict SUPPORTED_ON_SITE requirement (explicit supporting context, not mere mention).
2. Conservative CONTRADICTED_ON_SITE (same entity + same field + compatible context + conflicting values).
3. No false contradictions for missing evidence.
4. Non-verification of external accreditation truth.
"""
import pytest
from bs4 import BeautifulSoup
from rankintel.engines.claim_grounding_engine import ClaimGroundingEngine, bound_snippet
from rankintel.models.schema import (
    ClaimSupportStatus,
    EntityConsistencyStatus,
    StructuredVisibleAgreementStatus,
    StructuredVisibleAgreement,
    ClaimEvidence,
    EntityGroundingEvidence,
    ClaimGroundingEvidence,
    AnswerableUnitType,
    AnswerableInformationUnit,
    AnswerabilityEvidence,
    EntityEvidence,
    DetectedEntity,
    EntityType,
    EntitySource,
    OnPageEvidence,
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
)


HTML_DETAILED_LAB = """
<!DOCTYPE html>
<html>
<head>
    <title>Sunrise Testing Lab - Accredited Electrical Testing</title>
    <meta name="description" content="Sunrise Testing Lab offers BIS certification and electrical calibration services across India." />
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Sunrise Testing Lab",
      "telephone": "+91-11-23456789",
      "email": "contact@sunrisetesting.com",
      "address": {
        "@type": "PostalAddress",
        "streetAddress": "Plot 42, Okhla Industrial Area",
        "addressLocality": "New Delhi",
        "addressCountry": "IN"
      },
      "url": "https://sunrisetesting.example.com"
    }
    </script>
</head>
<body>
    <header>
        <h1>Sunrise Testing Lab</h1>
    </header>
    <main>
        <section id="intro">
            <p>Established in 2005, Sunrise Testing Lab is a premier industrial testing facility.</p>
        </section>
        <section id="bis-services">
            <h2>BIS Certification Testing Scope</h2>
            <p>We provide comprehensive BIS certification testing under the Compulsory Registration Scheme (CRS). Our testing scope covers electrical safety parameters, insulation resistance, and dielectric breakdown testing according to IS 13252 and IS 616 standards.</p>
        </section>
        <section id="specs">
            <h2>Measurement Parameters</h2>
            <table>
                <tr><th>Parameter</th><th>Range</th><th>Uncertainty</th></tr>
                <tr><td>Voltage</td><td>0 - 1000 V</td><td>±0.05%</td></tr>
            </table>
        </section>
    </main>
    <footer>
        <address>
            Plot 42, Okhla Industrial Area, New Delhi. Phone: +91-11-23456789. Email: contact@sunrisetesting.com
        </address>
    </footer>
</body>
</html>
"""

HTML_ISOLATED_CLAIM = """
<!DOCTYPE html>
<html>
<head>
    <title>Isolated Claims Page</title>
    <meta name="description" content="Over 30 years of excellence in industrial manufacturing and ISO 9001 quality testing." />
</head>
<body>
    <h1>General Industrial Products</h1>
    <p>Welcome to our product showcase website. Browse our catalog below.</p>
</body>
</html>
"""

HTML_CONTRADICTORY_PHONE_AND_YEAR = """
<!DOCTYPE html>
<html>
<head>
    <title>Contradictory Lab Website</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Alpha Tech Laboratories",
      "telephone": "+91-11-11111111",
      "email": "alpha@example.com"
    }
    </script>
</head>
<body>
    <h1>Alpha Tech Laboratories</h1>
    <p>Founded in 1995 as an analytical testing laboratory.</p>
    <p>Our company was originally established in 2012 to serve automotive clients.</p>
    <footer>
        <p>Main Headquarters Contact: Phone: +91-11-99999999 | Email: alpha@example.com</p>
    </footer>
</body>
</html>
"""


def test_supported_claims_detection_with_explicit_context():
    """
    Correction 1: A claim becomes SUPPORTED_ON_SITE only when the site contains
    explicit evidence that directly supports the claim's subject and relevant value/context.
    """
    engine = ClaimGroundingEngine()
    on_page = OnPageEvidence(
        url="https://sunrisetesting.example.com",
        title="Sunrise Testing Lab - Accredited Electrical Testing",
        meta_description="Sunrise Testing Lab offers BIS certification and electrical calibration services across India.",
        h1_text=["Sunrise Testing Lab"],
    )

    ev = engine.evaluate_page(
        url="https://sunrisetesting.example.com",
        raw_html=HTML_DETAILED_LAB,
        on_page=on_page,
    )

    assert ev.total_claims_detected > 0
    # BIS claim should be SUPPORTED_ON_SITE because the page has explicit scope and standards IS 13252
    bis_claims = [c for c in ev.claims if "bis" in c.claim_text.lower()]
    assert len(bis_claims) > 0
    assert any(c.support_status == ClaimSupportStatus.SUPPORTED_ON_SITE for c in bis_claims)
    # Check that note disclaims external verification
    supported_bis = next(c for c in bis_claims if c.support_status == ClaimSupportStatus.SUPPORTED_ON_SITE)
    assert any("does not verify independent external accreditation" in n for n in supported_bis.notes)


def test_partially_supported_claim_when_scope_is_missing():
    """
    Correction 1: If a standard/service is mentioned without explicit testing scope,
    parameters, or procedural steps, it is PARTIALLY_SUPPORTED, not fully supported.
    """
    engine = ClaimGroundingEngine()
    html = """
    <html><body>
    <h1>Services Overview</h1>
    <p>We offer BIS certification assistance.</p>
    <p>Contact our sales team for pricing.</p>
    </body></html>
    """
    ev = engine.evaluate_page(
        url="https://example.com/overview",
        raw_html=html,
    )

    bis_claims = [c for c in ev.claims if "bis" in c.claim_text.lower()]
    assert len(bis_claims) > 0
    # Lacks technical parameters, scope, or standard numbers -> PARTIALLY_SUPPORTED
    assert bis_claims[0].support_status in (ClaimSupportStatus.PARTIALLY_SUPPORTED, ClaimSupportStatus.UNCORROBORATED_ON_SITE)
    assert bis_claims[0].support_status != ClaimSupportStatus.SUPPORTED_ON_SITE


def test_uncorroborated_claims_in_meta_or_slogan():
    """Isolated claims in meta description with zero supporting body copy are UNCORROBORATED_ON_SITE."""
    engine = ClaimGroundingEngine()
    ev = engine.evaluate_page(
        url="https://example.com/isolated",
        raw_html=HTML_ISOLATED_CLAIM,
    )

    assert ev.uncorroborated_count > 0
    uncorroborated = [c for c in ev.claims if c.support_status == ClaimSupportStatus.UNCORROBORATED_ON_SITE]
    assert len(uncorroborated) >= 1
    # Over 30 years claim or ISO claim asserted in meta without body corroboration
    assert any("years" in c.claim_text.lower() or "iso" in c.claim_text.lower() for c in uncorroborated)


def test_explicit_contradiction_detection():
    """
    Correction 2: Require same entity + same field + compatible context + conflicting explicit values
    before CONTRADICTED_ON_SITE.
    """
    engine = ClaimGroundingEngine()
    ev = engine.evaluate_page(
        url="https://example.com/contradictory",
        raw_html=HTML_CONTRADICTORY_PHONE_AND_YEAR,
    )

    # 1. Conflicting founding year (1995 vs 2012) on same entity
    contradicted_claims = [c for c in ev.claims if c.support_status == ClaimSupportStatus.CONTRADICTED_ON_SITE]
    assert len(contradicted_claims) > 0
    assert any("1995" in c.claim_text or "2012" in c.claim_text for c in contradicted_claims)
    assert len(contradicted_claims[0].contradicting_snippets) > 0

    # 2. Conflicting telephone (+91-11-11111111 vs +91-11-99999999) under primary headquarters context
    phone_agr = next((a for a in ev.structured_agreements if a.field_name == "telephone"), None)
    assert phone_agr is not None
    assert phone_agr.status == StructuredVisibleAgreementStatus.DISAGREEMENT


def test_no_false_contradiction_when_fields_are_missing():
    """Missing fields must be classified as MISSING_*, NEVER as DISAGREEMENT or contradiction."""
    engine = ClaimGroundingEngine()
    html_no_schema = """
    <html><body>
    <h1>Acme Testing Co</h1>
    <footer><p>Contact: +91-11-22223333</p></footer>
    </body></html>
    """
    ev = engine.evaluate_page(
        url="https://example.com/no-schema",
        raw_html=html_no_schema,
    )

    phone_agr = next((a for a in ev.structured_agreements if a.field_name == "telephone"), None)
    assert phone_agr is not None
    assert phone_agr.status == StructuredVisibleAgreementStatus.MISSING_STRUCTURED
    assert phone_agr.status != StructuredVisibleAgreementStatus.DISAGREEMENT
    assert ev.disagreement_count == 0


def test_structured_visible_agreement_matching():
    """Matching fields in JSON-LD and visible text are classified as AGREEMENT."""
    engine = ClaimGroundingEngine()
    on_page = OnPageEvidence(
        url="https://sunrisetesting.example.com",
        title="Sunrise Testing Lab",
        h1_text=["Sunrise Testing Lab"],
    )
    ev = engine.evaluate_page(
        url="https://sunrisetesting.example.com",
        raw_html=HTML_DETAILED_LAB,
        on_page=on_page,
    )

    # Phone matches (+91-11-23456789)
    phone_agr = next(a for a in ev.structured_agreements if a.field_name == "telephone")
    assert phone_agr.status == StructuredVisibleAgreementStatus.AGREEMENT

    # Email matches (contact@sunrisetesting.com)
    email_agr = next(a for a in ev.structured_agreements if a.field_name == "email")
    assert email_agr.status == StructuredVisibleAgreementStatus.AGREEMENT

    # Organization Name matches (Sunrise Testing Lab)
    name_agr = next(a for a in ev.structured_agreements if a.field_name == "organization_name")
    assert name_agr.status in (StructuredVisibleAgreementStatus.AGREEMENT, StructuredVisibleAgreementStatus.PARTIAL_AGREEMENT)


def test_entity_consistency_across_6_surfaces():
    """Entity presence and consistency tracked across visible body, headings, meta, JSON-LD, contact, units."""
    engine = ClaimGroundingEngine()
    detected_entity = DetectedEntity(
        name="Sunrise Testing Lab",
        entity_type=EntityType.ORGANIZATION,
        source=EntitySource.JSON_LD,
        url="https://sunrisetesting.example.com",
    )
    entity_ev = EntityEvidence(
        url="https://sunrisetesting.example.com",
        total_entities_detected=1,
        detected_entities=[detected_entity],
    )
    on_page = OnPageEvidence(
        url="https://sunrisetesting.example.com",
        title="Sunrise Testing Lab - Accredited Electrical Testing",
        h1_text=["Sunrise Testing Lab"],
    )

    ev = engine.evaluate_page(
        url="https://sunrisetesting.example.com",
        raw_html=HTML_DETAILED_LAB,
        on_page=on_page,
        entity_ev=entity_ev,
    )

    assert len(ev.entity_grounding) > 0
    eg = ev.entity_grounding[0]
    assert eg.entity_name == "Sunrise Testing Lab"
    assert eg.observed_in_headings is True
    assert eg.observed_in_title_meta is True
    assert eg.observed_in_json_ld is True
    assert eg.observed_in_contact_info is True
    assert eg.consistency_status == EntityConsistencyStatus.CONSISTENT


def test_m10_2_unit_reuse_without_duplicate_parsing():
    """Factual statements from M10.2 AnswerabilityEvidence are reused directly as claims."""
    engine = ClaimGroundingEngine()
    unit = AnswerableInformationUnit(
        unit_id="unit-faq-42",
        unit_type=AnswerableUnitType.FAQ,
        snippet="What is the testing duration? The test procedure requires 3 business days.",
        content_location="body > section > div",
        structural_type="faq_block",
        bounded_evidence="FAQ block on turnaround time",
    )
    ans_ev = AnswerabilityEvidence(
        url="https://example.com/faq",
        total_units_detected=1,
        units=[unit],
    )

    ev = engine.evaluate_page(
        url="https://example.com/faq",
        raw_html="<html><body><h1>FAQ Page</h1></body></html>",
        answerability_ev=ans_ev,
    )

    reused_claims = [c for c in ev.claims if c.related_unit_id == "unit-faq-42"]
    assert len(reused_claims) == 1
    assert reused_claims[0].extraction_method == "m10_2_unit_reuse"
    assert reused_claims[0].source_type == "answerable_unit"
    assert "3 business days" in reused_claims[0].claim_text


def test_bounded_snippets_and_provenance_preservation():
    """All snippets must be bounded to avoid memory bloat and preserve provenance."""
    engine = ClaimGroundingEngine()
    long_statement = "Industrial standard conformity assessment " + ("very long text " * 50)
    html = f"<html><body><p>{long_statement}</p></body></html>"

    ev = engine.evaluate_page(
        url="https://example.com/long",
        raw_html=html,
    )

    for claim in ev.claims:
        assert len(claim.claim_text) <= 255
        assert len(claim.bounded_snippet) <= 355
        assert claim.provenance == "claim_grounding_engine"


def test_site_wide_aggregation_and_cross_page_corroboration():
    """Site-wide aggregation promotes uncorroborated claim on Page A if supported on Page B."""
    engine = ClaimGroundingEngine()

    # Page 1 has an uncorroborated service claim
    claim_p1 = ClaimEvidence(
        claim_id="c1",
        url="https://example.com/",
        claim_text="We offer precision electrical calibration services",
        claim_type="service_claim",
        support_status=ClaimSupportStatus.UNCORROBORATED_ON_SITE,
    )
    ev_p1 = ClaimGroundingEvidence(
        url="https://example.com/",
        total_claims_detected=1,
        uncorroborated_count=1,
        claims=[claim_p1],
    )

    # Page 2 has explicit supported technical calibration data
    claim_p2 = ClaimEvidence(
        claim_id="c2",
        url="https://example.com/services/calibration",
        claim_text="Precision electrical calibration services with technical measurement range 0-1000V",
        claim_type="specification",
        support_status=ClaimSupportStatus.SUPPORTED_ON_SITE,
    )
    ev_p2 = ClaimGroundingEvidence(
        url="https://example.com/services/calibration",
        total_claims_detected=1,
        supported_claims_count=1,
        claims=[claim_p2],
    )

    rec1 = CrawlRecord(url="https://example.com/", status=CrawlStatus.FETCHED, engine_results={"claim_grounding_engine": type("Res", (), {"claim_grounding": ev_p1})()})
    rec2 = CrawlRecord(url="https://example.com/services/calibration", status=CrawlStatus.FETCHED, engine_results={"claim_grounding_engine": type("Res", (), {"claim_grounding": ev_p2})()})

    site_crawl = SiteCrawlResult(
        pages_crawled=2,
        pages_discovered=2,
        crawl_records=[rec1, rec2],
    )

    site_intel = engine.evaluate_site(site_crawl)

    assert site_intel.total_site_claims_detected == 2
    # Claim on Page 1 should be promoted to SUPPORTED_ON_SITE via cross-page corroboration!
    assert claim_p1.support_status == ClaimSupportStatus.SUPPORTED_ON_SITE
    assert "https://example.com/services/calibration" in claim_p1.supporting_urls
