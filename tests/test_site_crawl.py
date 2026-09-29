"""
Unit tests for multi-page site crawling and issue aggregation.
"""
from unittest.mock import patch, MagicMock
import pandas as pd
from rankintel.engines.seo_engine import SeoEngine
from rankintel.models.schema import SiteCrawlResult

def test_site_crawl_aggregates_issues_from_dataframe():
    engine = SeoEngine()

    fake_crawl_df = pd.DataFrame([
        {
            "url": "https://example.com/",
            "status": 200,
            "title": "Example Home",
            "meta_description": "Valid description length over 120 characters here for proper search snippet testing.",
            "h1": "Welcome",
            "body_text": "This is a full page with lots of rich words to test the word count parser correctly without triggering thin content limits. " * 30,
            "canonical": "https://example.com/"
        },
        {
            "url": "https://example.com/broken",
            "status": 404,
            "title": "Not Found",
            "meta_description": "",
            "h1": "",
            "body_text": "404",
            "canonical": ""
        },
        {
            "url": "https://example.com/missing-h1",
            "status": 200,
            "title": "Example Home",  # duplicate title
            "meta_description": "Valid description length over 120 characters here for proper search snippet testing.",
            "h1": "",              # missing H1
            "body_text": "Short",  # thin content (<300 words)
            "canonical": ""
        }
    ])

    with patch("advertools.crawl") as mock_crawl, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=500), \
         patch("pandas.read_json", return_value=fake_crawl_df), \
         patch("os.remove"):

        result = engine.crawl_site("https://example.com", max_pages=10)

    assert result.pages_crawled == 3
    assert "https://example.com/broken" in result.broken_links
    assert "https://example.com/missing-h1" in result.missing_h1_pages
    assert "https://example.com/missing-h1" in result.thin_content_pages
    assert "Example Home" in result.duplicate_titles
    assert len(result.site_wide_issues) >= 3

def test_site_crawl_fallback_when_no_advertools():
    engine = SeoEngine()

    with patch("rankintel.engines.seo_engine.HAS_ADVERTOOLS", False), \
         patch.object(engine, "discover_site_urls", return_value=["https://example.com/page1"]), \
         patch.object(engine, "audit_static_page", return_value=(
             MagicMock(status_code=200, title="Page 1", title_length=6, meta_desc_length=0,
                       meta_description="", h1_count=0, canonical_url=None, word_count=50),
             MagicMock()
         )):
        result = engine.crawl_site("https://example.com", max_pages=5)

    assert result.pages_crawled == 1
    assert "MISSING_H1" in result.pages[0].issues
    assert "THIN_CONTENT" in result.pages[0].issues
