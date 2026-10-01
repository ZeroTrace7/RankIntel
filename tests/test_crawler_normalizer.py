"""
Unit tests for UrlNormalizer in RankIntel Crawl Layer.
Verifies two-tier normalization (crawl deduplication vs URL identity),
domain boundary enforcement, and MIME type filtering.
"""
from rankintel.crawler.normalizer import UrlNormalizer


def test_strip_tracking_parameters_and_preserve_content_params():
    """Verify that marketing parameters are stripped while content IDs remain."""
    raw_url = "https://example.com/products?utm_source=google&id=42&utm_medium=cpc&category=books&gclid=ABC123xyz"
    normalized = UrlNormalizer.normalize_for_crawl(raw_url)

    # Tracking parameters must be completely gone
    assert "utm_source" not in normalized
    assert "utm_medium" not in normalized
    assert "gclid" not in normalized

    # Content parameters must be retained in sorted order
    assert normalized == "https://example.com/products?category=books&id=42"


def test_alphabetical_query_sorting():
    """Verify parameters are sorted alphabetically to prevent duplicate crawling."""
    url_a = "https://example.com/filter?size=L&color=red&brand=acme"
    url_b = "https://example.com/filter?brand=acme&size=L&color=red"

    norm_a = UrlNormalizer.normalize_for_crawl(url_a)
    norm_b = UrlNormalizer.normalize_for_crawl(url_b)

    assert norm_a == norm_b
    assert norm_a == "https://example.com/filter?brand=acme&color=red&size=L"


def test_strip_fragments():
    """Verify URL fragments (#section) are stripped."""
    url = "https://example.com/docs/guide#installation"
    assert UrlNormalizer.normalize_for_crawl(url) == "https://example.com/docs/guide"


def test_scheme_and_hostname_lowercasing_and_port_stripping():
    """Verify scheme and host are lowercased and default ports stripped."""
    url_https = "HTTPS://WWW.EXAMPLE.COM:443/Services/"
    norm_https = UrlNormalizer.normalize_for_crawl(url_https)
    assert norm_https == "https://www.example.com/Services"

    url_http = "HTTP://EXAMPLE.COM:80/"
    norm_http = UrlNormalizer.normalize_for_crawl(url_http)
    assert norm_http == "http://example.com/"


def test_relative_url_resolution():
    """Verify relative URLs resolve against parent_url."""
    parent = "https://example.com/blog/article-1"
    child = "../contact"
    normalized = UrlNormalizer.normalize_for_crawl(child, parent_url=parent)
    assert normalized == "https://example.com/contact"


def test_url_identity_preserves_content_delineation():
    """Verify that distinct resource parameters produce distinct identities."""
    id_1 = UrlNormalizer.get_url_identity("https://example.com/catalog?product_id=101")
    id_2 = UrlNormalizer.get_url_identity("https://example.com/catalog?product_id=102")

    assert id_1 != id_2
    assert "product_id=101" in id_1
    assert "product_id=102" in id_2


def test_domain_boundary_enforcement():
    """Verify same-domain vs cross-domain boundaries and subdomain options."""
    base = "https://example.com/"

    # Same host
    assert UrlNormalizer.is_same_domain("https://example.com/about", base) is True
    assert UrlNormalizer.is_same_domain("/about", base) is True

    # Different domain
    assert UrlNormalizer.is_same_domain("https://competitor.com/about", base) is False

    # Subdomain boundary check
    assert UrlNormalizer.is_same_domain("https://blog.example.com/", base, allow_subdomains=False) is False
    assert UrlNormalizer.is_same_domain("https://blog.example.com/", base, allow_subdomains=True) is True


def test_mime_filtering():
    """Verify binary assets and media files are excluded from crawling."""
    assert UrlNormalizer.is_crawlable_mime("https://example.com/report.pdf") is False
    assert UrlNormalizer.is_crawlable_mime("https://example.com/hero.jpg") is False
    assert UrlNormalizer.is_crawlable_mime("https://example.com/video.mp4") is False
    assert UrlNormalizer.is_crawlable_mime("https://example.com/bundle.js") is False
    assert UrlNormalizer.is_crawlable_mime("https://example.com/styles.css") is False
    assert UrlNormalizer.is_crawlable_mime("https://example.com/about-us") is True
    assert UrlNormalizer.is_crawlable_mime("https://example.com/index.html") is True
    assert UrlNormalizer.is_crawlable_mime("mailto:info@example.com") is False
    assert UrlNormalizer.is_crawlable_mime("tel:+123456789") is False
