"""
Unit tests for RankIntel TrustEvaluator and 5-layer trust stack.
"""
from rankintel.analyzers.trust_evaluator import TrustEvaluator
from rankintel.models.schema import OnPageEvidence, SchemaEvidence, GeoAeoEvidence

def test_trust_evaluator_technical_layer():
    headers = {
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY"
    }
    on_page = OnPageEvidence(
        url="https://secure-example.com",
        response_headers=headers
    )
    schema = SchemaEvidence()
    trust = TrustEvaluator.evaluate("https://secure-example.com", on_page, schema)

    tech = trust.layers["technical"]
    assert tech.score == 5
    assert "HTTPS Protocol Active (+2)" in tech.signals_found
    assert "Strict-Transport-Security (HSTS)" in tech.signals_found
    assert "Content-Security-Policy (CSP)" in tech.signals_found

def test_trust_evaluator_identity_and_social():
    on_page = OnPageEvidence(
        url="https://example.com",
        title="Example Enterprise - Cloud Solutions",
        h1_text=["Example Enterprise Cloud"],
        internal_links=["https://example.com/about-us", "https://example.com/contact"],
        external_links=["https://twitter.com/example", "https://linkedin.com/company/example"]
    )
    schema = SchemaEvidence(
        has_organization=True,
        has_author=True,
        sameas_urls=[
            "https://twitter.com/example",
            "https://linkedin.com/company/example",
            "https://wikidata.org/wiki/Q12345"
        ]
    )
    trust = TrustEvaluator.evaluate("https://example.com", on_page, schema)

    ident = trust.layers["identity"]
    assert ident.score >= 4
    assert any("Organization" in s for s in ident.signals_found)

    social = trust.layers["social"]
    assert social.score >= 4
    assert any("sameAs" in s for s in social.signals_found)
    assert any("Knowledge Graph" in s for s in social.signals_found)

def test_trust_evaluator_overall_grade():
    # Weak site test
    on_page_weak = OnPageEvidence(url="http://insecure-site.org")
    schema_weak = SchemaEvidence()
    trust_weak = TrustEvaluator.evaluate("http://insecure-site.org", on_page_weak, schema_weak)
    assert trust_weak.grade in ("D", "F")
    assert trust_weak.overall_score < 40
