import pytest
from bs4 import BeautifulSoup
from rankintel.engines.image_engine import ImageEngine

def test_missing_alt_vs_empty_vs_generic():
    html = """
    <html>
        <body>
            <img src="missing.jpg" />
            <img src="empty.jpg" alt="" />
            <img src="generic.jpg" alt="image" />
            <img src="photo1.jpg" alt="photo.jpg" />
            <img src="optimal.jpg" alt="A beautiful sunset" />
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    
    assert evidence.total_images == 5
    assert evidence.missing_alt_count == 1
    assert evidence.decorative_alt_count == 1
    assert evidence.generic_alt_count == 2
    
    images = evidence.images
    assert images[0].alt_status == "MISSING"
    assert images[1].alt_status == "EMPTY_DECORATIVE"
    assert images[2].alt_status == "GENERIC_FILENAME"
    assert images[3].alt_status == "GENERIC_FILENAME"
    assert images[4].alt_status == "OPTIMAL"

def test_decorative_alt_inside_anchor_flagged_as_empty_link():
    html = """
    <html>
        <body>
            <a href="/home"><img src="icon.png" alt="" /></a>
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    assert evidence.total_images == 1
    assert evidence.images[0].alt_status == "MISSING" # Because it's an empty link

def test_missing_dimensions_potential_layout_shift_risk():
    html = """
    <html>
        <body>
            <img src="nodims.jpg" />
            <img src="dims.jpg" width="100" height="100" />
            <img src="aspect.jpg" style="aspect-ratio: 16/9;" />
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    assert evidence.missing_dimensions_count == 1
    assert evidence.images[0].potential_layout_shift_risk is True
    assert evidence.images[1].potential_layout_shift_risk is False
    assert evidence.images[2].potential_layout_shift_risk is False

def test_declared_format_classification():
    html = """
    <html>
        <body>
            <img src="img.webp" />
            <picture>
                <source type="image/avif" srcset="img.avif">
                <img src="img.jpg" />
            </picture>
            <img src="img.png" />
            <img src="img.jpg?q=80" />
            <img src="/api/image/1" />
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    images = evidence.images
    
    assert images[0].format_evidence.declared_format == "webp"
    assert images[0].format_evidence.is_modern_format is True
    
    assert images[1].format_evidence.declared_format == "avif"
    assert images[1].format_evidence.is_modern_format is True
    
    assert images[2].format_evidence.declared_format == "png"
    assert images[2].format_evidence.is_modern_format is False
    
    assert images[3].format_evidence.declared_format == "jpg"
    assert images[3].format_evidence.is_modern_format is False
    
    assert images[4].format_evidence.declared_format == "UNKNOWN"
    assert images[4].format_evidence.observed_mime_type == "UNKNOWN"

def test_early_image_lazy_loading_heuristic_lcp_warning():
    html = """
    <html>
        <body>
            <header>
                <img src="logo.png" loading="lazy" />
            </header>
            <img src="hero.jpg" loading="lazy" />
            <img src="img3.jpg" loading="lazy" />
            <img src="img4.jpg" loading="lazy" />
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    images = evidence.images
    
    # Logo in header is early
    assert images[0].potential_lcp_risk is True
    # Hero is index 1, also early
    assert images[1].potential_lcp_risk is True
    # Img3 is index 2, not early, not in header
    assert images[2].potential_lcp_risk is False
    
    assert evidence.early_lazy_lcp_risks_count == 2
    assert evidence.lazy_loaded_count == 4

def test_viewport_configuration_parsing():
    html = """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body></body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    head_audit = evidence.head_audit
    
    assert head_audit.viewport_present is True
    assert head_audit.viewport_configuration == "width=device-width, initial-scale=1.0"
    assert head_audit.responsive_behavior == "UNKNOWN"

def test_heading_skip_detection():
    html = """
    <html>
        <body>
            <h1>Main Title</h1>
            <h3>Subtitle (Skip H2)</h3>
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    head_audit = evidence.head_audit
    
    assert head_audit.heading_hierarchy_valid is False
    assert any("Skipped from H1 to H3" in s for s in head_audit.heading_skips)

def test_insecure_asset_url_extraction():
    html = """
    <html>
        <body>
            <img src="http://insecure.com/img.jpg" />
            <script src="http://insecure.com/script.js"></script>
            <link href="https://secure.com/style.css" />
        </body>
    </html>
    """
    evidence = ImageEngine.evaluate(html, "https://example.com")
    head_audit = evidence.head_audit
    
    assert "http://insecure.com/img.jpg" in head_audit.insecure_resource_urls
    assert "http://insecure.com/script.js" in head_audit.insecure_resource_urls
    assert "https://secure.com/style.css" not in head_audit.insecure_resource_urls
    assert len(head_audit.insecure_resource_urls) == 2
