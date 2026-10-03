"""
Unit tests for RankIntel Entity Intelligence Engine (Phase 8.2).
"""
import pytest
from bs4 import BeautifulSoup

from rankintel.engines.entity_engine import (
    EntityEngine,
    normalize_entity_name,
    normalize_phone_number,
    format_postal_address,
)
from rankintel.models.schema import (
    EntityType,
    EntitySource,
    EntitySignalType,
    EntityAlignmentStatus,
    EntityRelationshipType,
    OnPageEvidence,
)


def test_normalize_entity_name():
    """Verify corporate suffix stripping and whitespace normalization."""
    assert normalize_entity_name("ABC Calibration Private Limited") == "abc calibration"
    assert normalize_entity_name("ABC Calibration Pvt. Ltd.") == "abc calibration"
    assert normalize_entity_name("Acme Corp.") == "acme"
    assert normalize_entity_name("Global Tech LLC") == "global tech"
    assert normalize_entity_name("Sunrise Testing & Engineering Inc.") == "sunrise testing engineering"
    assert normalize_entity_name("Simple Brand") == "simple brand"


def test_normalize_phone_number():
    """Verify phone digit normalization."""
    assert normalize_phone_number("+1 (555) 123-4567") == "+15551234567"
    assert normalize_phone_number("022-2580-1234") == "02225801234"
    assert normalize_phone_number("+91 98765 43210") == "+919876543210"


def test_format_postal_address():
    """Verify schema.org PostalAddress dictionary formatting."""
    addr_dict = {
        "streetAddress": "Plot 42, Sector 18",
        "addressLocality": "Gurugram",
        "addressRegion": "Haryana",
        "postalCode": "122015",
        "addressCountry": "IN"
    }
    formatted = format_postal_address(addr_dict)
    assert "Plot 42, Sector 18" in formatted
    assert "Gurugram" in formatted
    assert "122015" in formatted

    # Direct string passthrough
    assert format_postal_address("123 Main St, New York, NY") == "123 Main St, New York, NY"
    assert format_postal_address(None) is None


def test_jsonld_organization_extraction():
    """Verify Organization and LocalBusiness extraction from JSON-LD."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Sunrise Testing Lab Private Limited",
            "telephone": "+91-98765-43210",
            "email": "info@sunriselab.com",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Industrial Area Phase 2",
                "addressLocality": "Mumbai",
                "postalCode": "400001",
                "addressCountry": "IN"
            },
            "sameAs": [
                "https://www.facebook.com/sunriselab",
                "https://www.linkedin.com/company/sunriselab"
            ]
        }
        </script>
    </head>
    <body>
        <h1>Testing Services</h1>
    </body>
    </html>
    """
    evidence = EntityEngine.evaluate(html, url="https://sunriselab.com/")
    assert evidence.total_entities_detected >= 1
    
    org_entities = [e for e in evidence.detected_entities if e.source == EntitySource.JSON_LD]
    assert len(org_entities) == 1
    ent = org_entities[0]
    assert ent.name == "Sunrise Testing Lab Private Limited"
    assert ent.entity_type == EntityType.LOCAL_BUSINESS
    assert ent.telephone == "+91-98765-43210"
    assert ent.email == "info@sunriselab.com"
    assert "Mumbai" in (ent.address or "")
    assert len(ent.same_as) == 2

    # Check relationships
    loc_rels = [r for r in evidence.relationships if r.relation == EntityRelationshipType.ORGANIZATION_TO_LOCATION]
    assert len(loc_rels) == 1
    assert "Mumbai" in loc_rels[0].object_name

    social_rels = [r for r in evidence.relationships if r.relation == EntityRelationshipType.ORGANIZATION_TO_SOCIAL_PROFILE]
    assert len(social_rels) == 2

    site_rels = [r for r in evidence.relationships if r.relation == EntityRelationshipType.ORGANIZATION_TO_WEBSITE]
    assert len(site_rels) == 1
    assert site_rels[0].object_name == "sunriselab.com"


def test_jsonld_product_and_service_relationships():
    """Verify Product and Service extraction and embedded brand/provider relationships."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        [
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Precision Digital Caliper 150mm",
                "brand": {
                    "@type": "Brand",
                    "name": "Mitutoyo Corporation"
                },
                "sku": "MIT-500-196-30"
            },
            {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "ISO 17025 Calibration Service",
                "provider": {
                    "@type": "Organization",
                    "name": "Apex Calibration Labs"
                }
            }
        ]
        </script>
    </head>
    <body><h1>Lab Equipment</h1></body>
    </html>
    """
    evidence = EntityEngine.evaluate(html, url="https://example.com/products")
    
    prod_entities = [e for e in evidence.detected_entities if e.entity_type == EntityType.PRODUCT]
    assert len(prod_entities) == 1
    assert prod_entities[0].name == "Precision Digital Caliper 150mm"
    assert prod_entities[0].identifiers.get("sku") == "MIT-500-196-30"

    serv_entities = [e for e in evidence.detected_entities if e.entity_type == EntityType.SERVICE]
    assert len(serv_entities) == 1
    assert serv_entities[0].name == "ISO 17025 Calibration Service"

    prod_rels = [r for r in evidence.relationships if r.relation == EntityRelationshipType.PRODUCT_TO_ORGANIZATION]
    assert len(prod_rels) == 1
    assert prod_rels[0].subject_name == "Precision Digital Caliper 150mm"
    assert prod_rels[0].object_name == "Mitutoyo Corporation"

    serv_rels = [r for r in evidence.relationships if r.relation == EntityRelationshipType.SERVICE_TO_ORGANIZATION]
    assert len(serv_rels) == 1
    assert serv_rels[0].object_name == "Apex Calibration Labs"


def test_meta_tag_and_visible_signals():
    """Verify og:site_name, meta author, copyright text, and tel/mailto extraction."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home - TechSolutions</title>
        <meta property="og:site_name" content="TechSolutions Brand">
        <meta name="author" content="Dr. Jane Doe">
        <meta name="geo.placename" content="Chicago, Illinois">
    </head>
    <body>
        <main>
            <p>Welcome to our tech firm.</p>
            <p>Call us at <a href="tel:+13125550199">+1 312-555-0199</a> or email <a href="mailto:support@techsolutions.com">support</a>.</p>
        </main>
        <footer>
            <p>&copy; 2026 TechSolutions Group LLC. All rights reserved.</p>
            <address>100 N Riverside Plaza, Chicago, IL 60606</address>
        </footer>
    </body>
    </html>
    """
    evidence = EntityEngine.evaluate(html, url="https://techsolutions.com/")
    
    # Check og:site_name signal
    og_signals = [e for e in evidence.detected_entities if e.signal_type == EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL]
    assert len(og_signals) == 1
    assert og_signals[0].name == "TechSolutions Brand"
    assert og_signals[0].source == EntitySource.META_TAG

    # Check author signal
    author_signals = [e for e in evidence.detected_entities if e.signal_type == EntitySignalType.AUTHOR_BYLINE_SIGNAL]
    assert len(author_signals) == 1
    assert author_signals[0].name == "Dr. Jane Doe"
    assert author_signals[0].entity_type == EntityType.PERSON

    # Check copyright signal
    copy_signals = [e for e in evidence.detected_entities if e.signal_type == EntitySignalType.COPYRIGHT_SIGNAL]
    assert len(copy_signals) >= 1
    assert any("TechSolutions" in e.name for e in copy_signals)

    # Check visible tel link
    tel_signals = [e for e in evidence.detected_entities if e.telephone]
    assert any("3125550199" in (e.telephone or "") for e in tel_signals)


def test_structured_vs_visible_normalized_match():
    """Verify that corporate suffix differences qualify as NORMALIZED_MATCH, not a mismatch."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "ABC Calibration Private Limited"
        }
        </script>
        <meta property="og:site_name" content="ABC Calibration">
    </head>
    <body>
        <footer>&copy; 2026 ABC Calibration. All rights reserved.</footer>
    </body>
    </html>
    """
    evidence = EntityEngine.evaluate(html, url="https://abccalibration.com/")
    
    comparisons = [c for c in evidence.structured_vs_visible if c.attribute_name == "organization_name"]
    assert len(comparisons) >= 1
    # Both og:site_name and copyright say "ABC Calibration", JSON-LD says "ABC Calibration Private Limited"
    # This must be recognized as NORMALIZED_MATCH
    match_statuses = [c.alignment_status for c in comparisons]
    assert EntityAlignmentStatus.NORMALIZED_MATCH in match_statuses
    assert EntityAlignmentStatus.DIVERGENT_IDENTITY_SUSPECTED not in match_statuses


def test_structured_vs_visible_divergent_identity():
    """Verify that completely disjoint brand names in the same context are flagged as DIVERGENT_IDENTITY_SUSPECTED."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "XYZ Global Technologies Inc"
        }
        </script>
        <meta property="og:site_name" content="ABC Calibration">
    </head>
    <body>
        <footer>&copy; 2026 ABC Calibration.</footer>
    </body>
    </html>
    """
    evidence = EntityEngine.evaluate(html, url="https://abccalibration.com/")
    
    comparisons = [c for c in evidence.structured_vs_visible if c.attribute_name == "organization_name"]
    assert len(comparisons) >= 1
    assert any(c.alignment_status == EntityAlignmentStatus.DIVERGENT_IDENTITY_SUSPECTED for c in comparisons)


def test_empty_html_handling():
    """Verify robust handling of empty/None HTML without raising exceptions."""
    ev_none = EntityEngine.evaluate(None, url="https://example.com/")
    assert ev_none.total_entities_detected == 0
    assert len(ev_none.facts) >= 1

    ev_empty = EntityEngine.evaluate("   \n\t  ", url="https://example.com/")
    assert ev_empty.total_entities_detected == 0
