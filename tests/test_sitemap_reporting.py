"""
Tests for Sitemap Reconciliation Markdown reporting, JSON serialization,
and end-to-end integration (Milestone M6.5).
"""
import pytest
import httpx
import json

from rankintel.models.schema import (
    CrawlConfig,
    SiteCrawlResult,
    SynthesisReport,
    SitemapFormat,
    SitemapFetchStatus,
    SitemapDocumentRecord,
    SitemapUrlRecord,
    CrossSignalConflictType,
    CrossSignalConflictSeverity,
    CrossSignalConflictRecord,
    SitemapReconciliationSummary,
    EvidenceNature,
)
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.crawler.deep_crawler import AsyncDeepCrawler


def test_markdown_report_renders_sitemap_section():
    doc = SitemapDocumentRecord(
        url="https://example.com/sitemap.xml",
        status=SitemapFetchStatus.SUCCESS,
        format=SitemapFormat.URLSET,
        urls_found_count=2,
        fetch_time_sec=0.045,
    )
    conflict = CrossSignalConflictRecord(
        url="https://example.com/blocked",
        conflict_type=CrossSignalConflictType.SITEMAP_ROBOTS_BLOCKED,
        severity=CrossSignalConflictSeverity.HIGH,
        signal_a_source="sitemap:https://example.com/sitemap.xml",
        signal_a_state="included_in_sitemap",
        signal_b_source="robots.txt",
        signal_b_state="BLOCKED",
        evidence_nature=EvidenceNature.OBSERVED,
        summary="Sitemap URL is disallowed under robots.txt.",
        recommended_reconciliation="Unblock or remove.",
    )
    sr = SitemapReconciliationSummary(
        total_sitemaps_discovered=1,
        total_sitemaps_parsed=1,
        total_unique_sitemap_urls=2,
        crawled_sitemap_urls_count=1,
        uncrawled_sitemap_urls_count=1,
        internal_urls_missing_from_sitemap_count=1,
        sitemap_documents=[doc],
        conflicts=[conflict],
        internal_urls_missing_from_sitemap=["https://example.com/extra-service"],
        uncrawled_sitemap_urls=["https://example.com/uncrawled"],
    )
    site_crawl = SiteCrawlResult(
        pages_crawled=1,
        sitemap_reconciliation=sr,
    )
    report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-10-02",
        site_crawl=site_crawl,
    )

    md = MarkdownReporter.render(report)

    assert "XML Sitemap Reconciliation & Cross-Signal Triangulation" in md
    assert "Sitemaps Traversed:" in md
    assert "Cross-Signal Conflict Matrix:" in md
    assert "SITEMAP_ROBOTS_BLOCKED" in md
    assert "Internal URLs Omitted from Sitemap (Coverage Discrepancies):" in md
    assert "https://example.com/extra-service" in md
    assert "Uncrawled Sitemap URLs" in md
    assert "https://example.com/uncrawled" in md


def test_json_serialization_sitemap_reconciliation():
    doc = SitemapDocumentRecord(
        url="https://example.com/sitemap.xml",
        status=SitemapFetchStatus.SUCCESS,
        format=SitemapFormat.URLSET,
        urls_found_count=1,
    )
    sr = SitemapReconciliationSummary(
        total_sitemaps_discovered=1,
        total_sitemaps_parsed=1,
        total_unique_sitemap_urls=1,
        sitemap_documents=[doc],
    )
    site_crawl = SiteCrawlResult(sitemap_reconciliation=sr)
    report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-10-02",
        site_crawl=site_crawl,
    )

    json_str = JsonReporter.render_audit(report)
    parsed = json.loads(json_str)

    assert "site_crawl" in parsed
    assert "sitemap_reconciliation" in parsed["site_crawl"]
    rec = parsed["site_crawl"]["sitemap_reconciliation"]
    assert rec["total_sitemaps_discovered"] == 1
    assert rec["sitemap_documents"][0]["url"] == "https://example.com/sitemap.xml"


def test_backward_compatibility_none_sitemap():
    """Verify reports render without error when sitemap_reconciliation is None."""
    site_crawl = SiteCrawlResult(pages_crawled=2, sitemap_reconciliation=None)
    report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-10-02",
        site_crawl=site_crawl,
    )

    md = MarkdownReporter.render(report)
    assert "XML Sitemap Reconciliation" not in md

    json_str = JsonReporter.render_audit(report)
    parsed = json.loads(json_str)
    assert parsed["site_crawl"]["sitemap_reconciliation"] is None


def test_deep_crawler_with_sitemap_analysis_integration():
    """Test full integration: crawler with enable_sitemap_analysis=True."""
    html_home = """<!DOCTYPE html><html><body><a href="/about">About</a></body></html>"""
    html_about = """<!DOCTYPE html><html><body>About Us</body></html>"""
    robots_txt = """User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml"""
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/</loc></url>
        <url><loc>https://example.com/about</loc></url>
        <url><loc>https://example.com/external-target</loc></url>
    </urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str.endswith("/robots.txt"):
            return httpx.Response(200, text=robots_txt)
        elif url_str.endswith("/sitemap.xml"):
            return httpx.Response(200, content=sitemap_xml, headers={"Content-Type": "application/xml"})
        elif url_str.endswith("/about"):
            return httpx.Response(200, text=html_about, headers={"Content-Type": "text/html"})
        else:
            return httpx.Response(200, text=html_home, headers={"Content-Type": "text/html"})

    transport = httpx.MockTransport(handler)
    config = CrawlConfig(
        max_pages=5,
        max_depth=2,
        enable_sitemap_analysis=True,
    )
    crawler = AsyncDeepCrawler(config=config, transport=transport)
    result = crawler.crawl_sync("https://example.com/")

    assert result.sitemap_reconciliation is not None
    sr = result.sitemap_reconciliation
    assert sr.total_sitemaps_discovered >= 1
    assert sr.total_unique_sitemap_urls == 3
    assert sr.crawled_sitemap_urls_count >= 2
