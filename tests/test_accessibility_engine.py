import pytest
import os
from bs4 import BeautifulSoup
from unittest.mock import patch, MagicMock

from rankintel.engines.accessibility_engine import AccessibilityEngine
from rankintel.models.schema import WcagStatus, AccessibilitySeverity

def test_static_html_lang_missing():
    html = "<html><head><title>Test</title></head><body></body></html>"
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    
    assert evidence.engine_source == "static_ast_auditor"
    assert evidence.total_violations > 0
    violation = next((v for v in evidence.violations if v.rule_id == "html-has-lang"), None)
    assert violation is not None
    assert violation.severity == AccessibilitySeverity.SERIOUS

def test_static_document_title_missing():
    html = "<html lang='en'><head></head><body></body></html>"
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    
    violation = next((v for v in evidence.violations if v.rule_id == "document-title"), None)
    assert violation is not None
    assert violation.severity == AccessibilitySeverity.SERIOUS

def test_static_form_control_labels():
    html = """
    <html lang="en">
    <head><title>Test</title></head>
    <body>
        <main>
            <input type="text" id="no-label" />
            <input type="submit" value="Submit" />
            
            <label for="has-label">Name</label>
            <input type="text" id="has-label" />
            
            <input type="text" aria-label="Search" />
        </main>
    </body>
    </html>
    """
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    violations = [v for v in evidence.violations if v.rule_id == "label"]
    assert len(violations) == 1
    assert "no-label" in violations[0].html_snippet

def test_static_main_landmark():
    html = "<html lang='en'><head><title>Test</title></head><body><div>No main</div></body></html>"
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    violation = next((v for v in evidence.violations if v.rule_id == "landmark-one-main"), None)
    assert violation is not None

def test_static_duplicate_ids():
    html = """
    <html lang='en'><head><title>Test</title></head>
    <body>
        <main>
            <div id="duplicate">First</div>
            <div id="duplicate">Second</div>
        </main>
    </body></html>
    """
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    violation = next((v for v in evidence.violations if v.rule_id == "duplicate-id"), None)
    assert violation is not None
    assert "duplicate" in violation.failure_summary

def test_static_heading_order():
    html = """
    <html lang='en'><head><title>Test</title></head>
    <body>
        <main>
            <h1>Main Title</h1>
            <h3>Sub Title (Skipped h2)</h3>
        </main>
    </body></html>
    """
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    violation = next((v for v in evidence.violations if v.rule_id == "heading-order"), None)
    assert violation is not None
    assert "H1 to H3" in violation.failure_summary

def test_static_link_button_names():
    html = """
    <html lang='en'><head><title>Test</title></head>
    <body>
        <main>
            <a href="/link1"></a> <!-- Empty -->
            <button></button> <!-- Empty -->
            <a href="/link2">Valid</a>
            <button aria-label="close"></button>
            <a href="/link3"><img src="x.jpg" alt="Home" /></a>
            <a href="/link4"><img src="y.jpg" alt="" /></a> <!-- Empty alt -->
        </main>
    </body></html>
    """
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    
    a_violations = [v for v in evidence.violations if v.rule_id == "a-name"]
    btn_violations = [v for v in evidence.violations if v.rule_id == "button-name"]
    img_alt_violations = [v for v in evidence.violations if v.rule_id == "image-alt"]
    
    assert len(a_violations) == 2 # link1 and link4
    assert len(btn_violations) == 1 # first button
    assert len(img_alt_violations) == 1 # img in link4

def test_static_clean_html_produces_unknown_status():
    html = """
    <html lang='en'><head><title>Test</title></head>
    <body>
        <main>
            <h1>Title</h1>
            <p>Content</p>
        </main>
    </body></html>
    """
    evidence = AccessibilityEngine.evaluate_static(html, "https://example.com")
    assert evidence.total_violations == 0
    # Because static analysis cannot prove a full PASS, it must be UNKNOWN
    assert evidence.wcag_aa_status == WcagStatus.UNKNOWN

@pytest.mark.anyio
async def test_evaluate_async_without_playwright_fallback():
    # Force ImportError for playwright
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == "playwright.async_api":
            raise ImportError()
        return original_import(name, *args, **kwargs)
        
    with patch("builtins.__import__", side_effect=mock_import):
        html = "<html lang='en'><head><title>Test</title></head><body></body></html>"
        evidence = await AccessibilityEngine.evaluate_async("https://example.com", html)
        assert evidence.browser_evaluated is False
        assert evidence.wcag_aa_status == WcagStatus.UNAVAILABLE
        assert "Playwright not installed" in "".join(evidence.notes)

@pytest.mark.anyio
async def test_evaluate_async_with_axe_mock():
    mock_axe_results = {
        "passes": [{}, {}],
        "violations": [
            {
                "id": "color-contrast",
                "impact": "serious",
                "tags": ["wcag2aa", "wcag143"],
                "description": "Elements must have sufficient color contrast",
                "nodes": [{"html": "<div style='color: white; background: white;'>Text</div>"}]
            }
        ]
    }

    class MockResponse:
        status = 200

    class MockPage:
        async def goto(self, url, **kwargs):
            return MockResponse()
        async def evaluate(self, script):
            if "axe.run" in script:
                return mock_axe_results
            return None

    class MockContext:
        async def new_page(self):
            return MockPage()

    class MockBrowser:
        async def new_context(self):
            return MockContext()
        async def close(self):
            pass

    class MockPlaywright:
        @property
        def chromium(self):
            class Chromium:
                async def launch(self, **kwargs):
                    return MockBrowser()
            return Chromium()
            
    class MockAsyncPlaywrightContextManager:
        async def __aenter__(self):
            return MockPlaywright()
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Mock async_playwright
    with patch("playwright.async_api.async_playwright", return_value=MockAsyncPlaywrightContextManager()):
        html = "<html lang='en'><head><title>Test</title></head><body><main><h1>Hello</h1></main></body></html>"
        evidence = await AccessibilityEngine.evaluate_async("https://example.com", html)
        
        assert evidence.browser_evaluated is True
        assert evidence.engine_source == "axe_core_playwright"
        assert evidence.total_violations == 1
        assert evidence.violations[0].rule_id == "color-contrast"
        assert evidence.violations[0].severity == AccessibilitySeverity.SERIOUS
        assert evidence.wcag_aa_status == WcagStatus.FAIL
