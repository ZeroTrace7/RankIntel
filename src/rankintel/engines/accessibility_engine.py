import os
import json
import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    AccessibilityEvidence, AccessibilityViolation, 
    AccessibilitySeverity, WcagLevel, WcagStatus
)

class AccessibilityEngine:
    """
    Two-tier accessibility engine:
    1. Static HTML AST evaluations (offline, fast, deterministic).
    2. Axe-core Playwright evaluation (if browser is available).
    """

    @classmethod
    def evaluate_static(cls, raw_html: str, url: str) -> AccessibilityEvidence:
        """Evaluates accessibility rules statically using BeautifulSoup."""
        evidence = AccessibilityEvidence(url=url, engine_source="static_ast_auditor")
        
        if not raw_html:
            evidence.notes.append("No HTML provided for static evaluation.")
            return evidence

        soup = BeautifulSoup(raw_html, "lxml")
        
        # 1. HTML Lang
        html_tag = soup.find("html")
        if not html_tag or not html_tag.get("lang") or not str(html_tag.get("lang")).strip():
            evidence.violations.append(AccessibilityViolation(
                rule_id="html-has-lang",
                wcag_sc="3.1.1",
                level=WcagLevel.A,
                severity=AccessibilitySeverity.SERIOUS,
                description="<html> element must have a lang attribute",
                failure_summary="No lang attribute found on <html> element."
            ))

        # 2. Document Title
        title_tag = soup.find("title")
        if not title_tag or not title_tag.get_text(strip=True):
            evidence.violations.append(AccessibilityViolation(
                rule_id="document-title",
                wcag_sc="2.4.2",
                level=WcagLevel.A,
                severity=AccessibilitySeverity.SERIOUS,
                description="Documents must have <title> element to aid in navigation",
                failure_summary="Document <title> is missing or empty."
            ))

        # 3. Form control labels
        inputs = soup.find_all(["input", "textarea", "select"])
        for inp in inputs:
            # Skip hidden, submit, button, reset, image inputs which don't need explicit labels
            if inp.name == "input":
                typ = inp.get("type", "").lower()
                if typ in ["hidden", "submit", "button", "reset", "image"]:
                    continue

            has_label = False
            # Check aria-label
            if inp.get("aria-label"):
                has_label = True
            # Check aria-labelledby
            elif inp.get("aria-labelledby"):
                has_label = True
            # Check title (fallback)
            elif inp.get("title"):
                has_label = True
            # Check parent label
            elif inp.find_parent("label"):
                has_label = True
            # Check id mapping
            elif inp.get("id"):
                inp_id = inp.get("id")
                if soup.find("label", attrs={"for": inp_id}):
                    has_label = True

            if not has_label:
                snippet = str(inp)[:150]
                evidence.violations.append(AccessibilityViolation(
                    rule_id="label",
                    wcag_sc="3.3.2",
                    level=WcagLevel.A,
                    severity=AccessibilitySeverity.CRITICAL,
                    description="Form controls must have labels",
                    html_snippet=snippet,
                    failure_summary=f"Form control missing label."
                ))

        # 4. Main landmark
        main_tags = soup.find_all("main")
        main_roles = soup.find_all(attrs={"role": "main"})
        if not main_tags and not main_roles:
            evidence.violations.append(AccessibilityViolation(
                rule_id="landmark-one-main",
                wcag_sc="1.3.1",
                level=WcagLevel.A,
                severity=AccessibilitySeverity.MODERATE,
                description="Page must have one main landmark",
                failure_summary="No <main> element or role='main' found."
            ))

        # 5. Duplicate IDs
        ids_found = set()
        duplicate_ids = set()
        for el in soup.find_all(id=True):
            el_id = el.get("id")
            if el_id in ids_found:
                duplicate_ids.add(el_id)
            else:
                ids_found.add(el_id)
        
        for dup_id in duplicate_ids:
            evidence.violations.append(AccessibilityViolation(
                rule_id="duplicate-id",
                wcag_sc="4.1.1",
                level=WcagLevel.A,
                severity=AccessibilitySeverity.MINOR,
                description="id attribute value must be unique",
                failure_summary=f"Duplicate id '{dup_id}' found."
            ))

        # 6. Heading order
        headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
        current_level = 0
        for h in headings:
            level = int(h.name[1])
            if current_level != 0 and level > current_level + 1:
                evidence.violations.append(AccessibilityViolation(
                    rule_id="heading-order",
                    wcag_sc="1.3.1",
                    level=WcagLevel.A,
                    severity=AccessibilitySeverity.MODERATE,
                    description="Heading levels should only increase by one",
                    html_snippet=str(h)[:150],
                    failure_summary=f"Skipped heading level from H{current_level} to H{level}."
                ))
            current_level = level

        # 7. Accessible names for links/buttons
        links_and_buttons = soup.find_all(["a", "button"])
        for el in links_and_buttons:
            # Check for name/text
            name = el.get_text(strip=True)
            if not name:
                name = el.get("aria-label", "").strip()
            if not name:
                name = el.get("aria-labelledby", "").strip()
            if not name and el.name == "a":
                # Check for image inside anchor with alt text
                img = el.find("img")
                if img and img.get("alt", "").strip():
                    name = img.get("alt").strip()
            if not name and el.name == "button":
                # check value or title
                name = el.get("title", "").strip()
            
            if not name:
                # Could be a hidden button or empty decorative anchor. 
                # If it has href (for a) or is a button, it should have a name.
                if el.name == "a" and not el.get("href"):
                    continue # Not a functional link
                # Check if it's explicitly hidden
                if el.get("aria-hidden") == "true" or "display: none" in el.get("style", ""):
                    continue

                evidence.violations.append(AccessibilityViolation(
                    rule_id=f"{el.name}-name",
                    wcag_sc="4.1.2",
                    level=WcagLevel.A,
                    severity=AccessibilitySeverity.CRITICAL,
                    description=f"{el.name.capitalize()}s must have discernible text",
                    html_snippet=str(el)[:150],
                    failure_summary=f"No accessible name found for <{el.name}>."
                ))

        # 8. Meaningful image alt attributes
        images = soup.find_all("img")
        for img in images:
            alt = img.get("alt")
            if alt is None:
                # Missing alt entirely
                evidence.violations.append(AccessibilityViolation(
                    rule_id="image-alt",
                    wcag_sc="1.1.1",
                    level=WcagLevel.A,
                    severity=AccessibilitySeverity.CRITICAL,
                    description="Images must have alternate text",
                    html_snippet=str(img)[:150],
                    failure_summary="<img> missing 'alt' attribute."
                ))
            elif alt.strip() == "" and img.find_parent("a") and not img.find_parent("a").get_text(strip=True):
                # Empty alt inside a link with no other text (caught by link-name too, but let's be explicit)
                evidence.violations.append(AccessibilityViolation(
                    rule_id="image-alt",
                    wcag_sc="1.1.1",
                    level=WcagLevel.A,
                    severity=AccessibilitySeverity.CRITICAL,
                    description="Images inside links must have alternate text if link has no other text",
                    html_snippet=str(img)[:150],
                    failure_summary="<img> with empty alt inside an empty link."
                ))

        # 9. ARIA roles basic validity
        valid_roles = {"alert", "alertdialog", "application", "article", "banner", "button", "cell", 
                       "checkbox", "columnheader", "combobox", "complementary", "contentinfo", "definition", 
                       "dialog", "directory", "document", "feed", "figure", "form", "grid", "gridcell", 
                       "group", "heading", "img", "link", "list", "listbox", "listitem", "log", "main", 
                       "marquee", "math", "menu", "menubar", "menuitem", "menuitemcheckbox", "menuitemradio", 
                       "navigation", "none", "note", "option", "presentation", "progressbar", "radio", 
                       "radiogroup", "region", "row", "rowgroup", "rowheader", "scrollbar", "search", 
                       "searchbox", "separator", "slider", "spinbutton", "status", "switch", "tab", "table", 
                       "tablist", "tabpanel", "term", "textbox", "timer", "toolbar", "tooltip", "tree", 
                       "treegrid", "treeitem"}
        
        elements_with_roles = soup.find_all(attrs={"role": True})
        for el in elements_with_roles:
            roles = el.get("role", "").split()
            for role in roles:
                if role and role not in valid_roles:
                    evidence.violations.append(AccessibilityViolation(
                        rule_id="aria-roles",
                        wcag_sc="4.1.2",
                        level=WcagLevel.A,
                        severity=AccessibilitySeverity.SERIOUS,
                        description="ARIA roles used must conform to valid values",
                        html_snippet=str(el)[:150],
                        failure_summary=f"Invalid ARIA role: '{role}'."
                    ))

        # Tally
        cls._tally_violations(evidence)
        return evidence

    @classmethod
    async def evaluate_async(cls, url: str, raw_html: str = "") -> AccessibilityEvidence:
        import os
        import json
        evidence = cls.evaluate_static(raw_html, url)
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            evidence.notes.append("Playwright not installed. Browser rendering UNAVAILABLE.")
            evidence.wcag_aa_status = WcagStatus.UNAVAILABLE
            return evidence

        axe_path = os.path.join(os.path.dirname(__file__), "..", "references", "assets", "axe.min.js")
        if not os.path.exists(axe_path):
            evidence.notes.append(f"axe.min.js not found at {axe_path}. Browser rendering UNAVAILABLE.")
            evidence.wcag_aa_status = WcagStatus.UNAVAILABLE
            return evidence

        try:
            with open(axe_path, "r", encoding="utf-8") as f:
                axe_script = f.read()

            async with async_playwright() as p:
                # Use chromium headless
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Navigate
                response = await page.goto(url, timeout=15000, wait_until="load")
                if not response or response.status >= 400:
                    evidence.notes.append(f"Browser navigation failed or returned HTTP {response.status if response else 'Unknown'}.")
                    evidence.wcag_aa_status = WcagStatus.UNAVAILABLE
                    await browser.close()
                    return evidence

                # Inject axe-core
                await page.evaluate(axe_script)
                
                # Configure and run axe
                axe_options = {
                    "runOnly": {
                        "type": "tag",
                        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"]
                    }
                }
                
                results = await page.evaluate(f"axe.run(document, {json.dumps(axe_options)})")
                
                evidence.engine_source = "axe_core_playwright"
                evidence.browser_evaluated = True
                
                # Overwrite static violations with much more accurate rendered ones
                evidence.violations.clear()
                
                for v in results.get("violations", []):
                    impact = v.get("impact", "minor")
                    if impact == "critical":
                        sev = AccessibilitySeverity.CRITICAL
                    elif impact == "serious":
                        sev = AccessibilitySeverity.SERIOUS
                    elif impact == "moderate":
                        sev = AccessibilitySeverity.MODERATE
                    else:
                        sev = AccessibilitySeverity.MINOR
                        
                    tags = v.get("tags", [])
                    wcag_sc = next((tag for tag in tags if tag.startswith("wcag")), "")
                    level = WcagLevel.AA if "aa" in wcag_sc else (WcagLevel.A if "a" in wcag_sc else WcagLevel.UNKNOWN)
                    
                    nodes = v.get("nodes", [])
                    for node in nodes:
                        snippet = node.get("html", "")
                        target = node.get("target", [])
                        selector = target[0] if target else None
                        failure_summary = node.get("failureSummary", "")
                        
                        evidence.violations.append(AccessibilityViolation(
                            rule_id=v.get("id", ""),
                            wcag_sc=wcag_sc,
                            level=level,
                            severity=sev,
                            description=v.get("description", ""),
                            help_url=v.get("helpUrl", ""),
                            selector=selector,
                            html_snippet=snippet,
                            failure_summary=failure_summary,
                            tier="axe_rendered"
                        ))
                
                evidence.rules_evaluated_count = len(results.get("passes", [])) + len(results.get("violations", []))
                evidence.rules_passed_count = len(results.get("passes", []))
                
                cls._tally_violations(evidence)
                
                if evidence.total_violations == 0 and evidence.rules_evaluated_count > 0:
                    evidence.wcag_aa_status = WcagStatus.PASS
                    
                await browser.close()
                
        except Exception as e:
            # Fallback to static if playwright fails (e.g. timeout, no browser binary)
            evidence.notes.append(f"Browser rendering failed ({str(e)}). Falling back to static evaluation.")
            evidence.wcag_aa_status = WcagStatus.UNAVAILABLE

        return evidence

    @classmethod
    def _tally_violations(cls, evidence: AccessibilityEvidence):
        evidence.total_violations = len(evidence.violations)
        evidence.critical_count = sum(1 for v in evidence.violations if v.severity == AccessibilitySeverity.CRITICAL)
        evidence.serious_count = sum(1 for v in evidence.violations if v.severity == AccessibilitySeverity.SERIOUS)
        evidence.moderate_count = sum(1 for v in evidence.violations if v.severity == AccessibilitySeverity.MODERATE)
        evidence.minor_count = sum(1 for v in evidence.violations if v.severity == AccessibilitySeverity.MINOR)

        if evidence.critical_count > 0 or evidence.serious_count > 0:
            evidence.wcag_aa_status = WcagStatus.FAIL
        elif evidence.total_violations == 0:
            if not evidence.browser_evaluated:
                evidence.wcag_aa_status = WcagStatus.UNKNOWN
        else:
            evidence.wcag_aa_status = WcagStatus.PARTIAL
