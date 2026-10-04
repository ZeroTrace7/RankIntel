from typing import List, Dict, Any
from uuid import uuid4
from rankintel.models.schema import (
    SynthesisReport,
    RemediationRecord,
    RemediationClassification,
    SecuritySeverity,
    AccessibilitySeverity
)

class RemediationEngine:
    """
    Phase 12.1 - Remediation Intelligence Layer.
    Converts existing verified findings into structured remediation guidance.
    Operates deterministically on available evidence.
    """

    @staticmethod
    def generate_remediations(report: SynthesisReport) -> List[RemediationRecord]:
        remediations: List[RemediationRecord] = []
        url = report.url

        # 1. Missing/Weak Title
        on_page = report.unified_on_page
        if on_page and on_page.status_code == 200 and on_page.engine_source:
            if not on_page.title:
                remediations.append(RemediationRecord(
                    remediation_id=f"REM-TITLE-MISSING-{uuid4().hex[:8]}",
                    finding_id="FINDING-ON-PAGE-NO-TITLE",
                    category="TECHNICAL_SEO",
                    problem="The page is missing a <title> tag.",
                    why_it_matters="The title tag is a primary ranking signal and controls the main link text in search results.",
                    recommended_action="Add a descriptive <title> tag reflecting the core topic and brand.",
                    affected_urls=[url],
                    supporting_evidence={"title_detected": False},
                    evidence_provenance="on_page_engine",
                    confidence_status="HIGH",
                    classification=RemediationClassification.AUTO_SAFE,
                    implementation_notes="Ensure title is inside the <head> section."
                ))
            
            # 2. Missing Meta Description
            if not on_page.meta_description:
                remediations.append(RemediationRecord(
                    remediation_id=f"REM-DESC-MISSING-{uuid4().hex[:8]}",
                    finding_id="FINDING-ON-PAGE-NO-DESC",
                    category="TECHNICAL_SEO",
                    problem="The page is missing a meta description.",
                    why_it_matters="Meta descriptions influence click-through rates from search results.",
                    recommended_action="Add a concise meta description summarizing the page's value proposition.",
                    affected_urls=[url],
                    supporting_evidence={"meta_description_detected": False},
                    evidence_provenance="on_page_engine",
                    confidence_status="HIGH",
                    classification=RemediationClassification.HUMAN_REVIEW,
                    implementation_notes="Keep under 160 characters."
                ))
            
            # 4. Missing Canonical
            if not getattr(on_page, 'canonical_url', getattr(on_page, 'canonical', None)):
                remediations.append(RemediationRecord(
                    remediation_id=f"REM-CANON-MISSING-{uuid4().hex[:8]}",
                    finding_id="FINDING-ON-PAGE-NO-CANONICAL",
                    category="TECHNICAL_SEO",
                    problem="The page is missing a self-referencing canonical tag.",
                    why_it_matters="Without a canonical tag, URL variations (parameters, tracking) may cause duplicate content issues.",
                    recommended_action=f"Add <link rel=\"canonical\" href=\"{url}\" /> to the <head>.",
                    affected_urls=[url],
                    supporting_evidence={"canonical_detected": False},
                    evidence_provenance="on_page_engine",
                    confidence_status="HIGH",
                    classification=RemediationClassification.AUTO_SAFE
                ))
        
        # 3. Missing Image Alt Text
        image_seo = report.unified_image_seo
        if image_seo and image_seo.images and hasattr(image_seo, 'engine_source') and image_seo.engine_source:
            missing_alt_images = [img for img in image_seo.images if not img.alt]
            if missing_alt_images:
                img_urls = [img.src for img in missing_alt_images[:3]]
                remediations.append(RemediationRecord(
                    remediation_id=f"REM-IMG-ALT-{uuid4().hex[:8]}",
                    finding_id="FINDING-IMAGE-MISSING-ALT",
                    category="ACCESSIBILITY_SEO",
                    problem=f"{len(missing_alt_images)} images are missing alt text.",
                    why_it_matters="Images without alt text are inaccessible to screen readers and missed by image search engines.",
                    recommended_action="Add descriptive alt attributes explaining the image content or function.",
                    affected_urls=[url],
                    supporting_evidence={"missing_alt_count": len(missing_alt_images), "sample_images": img_urls},
                    evidence_provenance="image_engine",
                    confidence_status="HIGH",
                    classification=RemediationClassification.HUMAN_REVIEW,
                    implementation_notes="Decorative images should use alt=\"\"."
                ))

        # 5. Missing robots.txt
        robots = report.unified_robots
        if robots and getattr(robots, 'engine_source', '') and not getattr(robots, 'found', False):
            remediations.append(RemediationRecord(
                remediation_id=f"REM-ROBOTS-MISSING-{uuid4().hex[:8]}",
                finding_id="FINDING-ROBOTS-TXT-MISSING",
                category="CRAWLABILITY",
                problem="No robots.txt file was found at the domain root.",
                why_it_matters="A missing robots.txt prevents explicit crawler control and search agent opt-ins.",
                recommended_action="Deploy a valid robots.txt file at the root directory.",
                affected_urls=[f"https://{report.domain}/robots.txt"],
                supporting_evidence={"robots_txt_found": False},
                evidence_provenance="robots_engine",
                confidence_status="HIGH",
                classification=RemediationClassification.AUTO_SAFE
            ))

        # 6. Structured Data Agreement (Divergent)
        entity = report.unified_entity
        if entity and entity.structured_vs_visible and getattr(entity, 'engine_source', ''):
            for comp in entity.structured_vs_visible:
                if comp.alignment_status.value == "DIVERGENT_IDENTITY_SUSPECTED":
                    remediations.append(RemediationRecord(
                        remediation_id=f"REM-SCHEMA-DIV-{uuid4().hex[:8]}",
                        finding_id="FINDING-ENTITY-DIVERGENT",
                        category="SEMANTIC_SEO",
                        problem=f"Structured {comp.attribute_name} '{comp.structured_value}' differs from visible '{comp.visible_value}'.",
                        why_it_matters="Conflicting entity signals between schema and visible DOM confuse search knowledge graphs.",
                        recommended_action="Align the JSON-LD structured data to match the visible on-page branding.",
                        affected_urls=[url],
                        supporting_evidence={"structured_value": comp.structured_value, "visible_value": comp.visible_value},
                        evidence_provenance="entity_engine",
                        confidence_status="MEDIUM",
                        classification=RemediationClassification.HUMAN_REVIEW
                    ))

        # 7. Inaccessible Form Labels
        a11y = report.unified_accessibility
        if a11y and a11y.violations and getattr(a11y, 'engine_source', ''):
            label_violations = [v for v in a11y.violations if v.rule_id == 'label']
            if label_violations:
                remediations.append(RemediationRecord(
                    remediation_id=f"REM-A11Y-LABEL-{uuid4().hex[:8]}",
                    finding_id="FINDING-A11Y-MISSING-LABEL",
                    category="ACCESSIBILITY",
                    problem="Form elements are missing associated labels.",
                    why_it_matters="Inputs without labels are completely unusable by screen reader users.",
                    recommended_action="Wrap input elements with a <label> or link them using the 'for' attribute.",
                    affected_urls=[url],
                    supporting_evidence={"violation_count": len(label_violations)},
                    evidence_provenance="accessibility_engine",
                    confidence_status="HIGH",
                    classification=RemediationClassification.AUTO_SAFE
                ))

        # 8. Security Header Deficiencies
        security = report.unified_security
        if security and security.findings:
            for f in security.findings:
                if f.severity == SecuritySeverity.CRITICAL or f.severity == SecuritySeverity.HIGH:
                    if f.title == "Content-Security-Policy Missing":
                        remediations.append(RemediationRecord(
                            remediation_id=f"REM-SEC-CSP-{uuid4().hex[:8]}",
                            finding_id="FINDING-SEC-CSP-MISSING",
                            category="SECURITY",
                            problem="Content-Security-Policy header is missing.",
                            why_it_matters="CSP prevents Cross-Site Scripting (XSS) and data injection attacks.",
                            recommended_action="Implement a Content-Security-Policy HTTP response header.",
                            affected_urls=[url],
                            supporting_evidence={"missing_header": "Content-Security-Policy"},
                            evidence_provenance="security_engine",
                            confidence_status="HIGH",
                            classification=RemediationClassification.HUMAN_REVIEW,
                            implementation_notes="Requires testing to avoid breaking inline scripts."
                        ))
                    elif f.title == "Strict-Transport-Security Missing":
                        remediations.append(RemediationRecord(
                            remediation_id=f"REM-SEC-HSTS-{uuid4().hex[:8]}",
                            finding_id="FINDING-SEC-HSTS-MISSING",
                            category="SECURITY",
                            problem="Strict-Transport-Security (HSTS) header is missing.",
                            why_it_matters="HSTS forces secure HTTPS connections, preventing downgrade attacks.",
                            recommended_action="Implement an HSTS HTTP response header with a max-age.",
                            affected_urls=[url],
                            supporting_evidence={"missing_header": "Strict-Transport-Security"},
                            evidence_provenance="security_engine",
                            confidence_status="HIGH",
                            classification=RemediationClassification.AUTO_SAFE
                        ))

        # 9. Dead-end / Internal-Link Issues
        internal_link = report.unified_internal_link
        if internal_link and internal_link.empty_anchor_count > 0 and getattr(internal_link, 'engine_source', ''):
            remediations.append(RemediationRecord(
                remediation_id=f"REM-LINK-ANCHOR-{uuid4().hex[:8]}",
                finding_id="FINDING-LINK-EMPTY-ANCHOR",
                category="ARCHITECTURE",
                problem=f"{internal_link.empty_anchor_count} internal links have empty anchor text.",
                why_it_matters="Empty anchor text deprives crawlers and users of link context.",
                recommended_action="Provide descriptive anchor text or aria-labels for the affected links.",
                affected_urls=[url],
                supporting_evidence={"empty_anchor_count": internal_link.empty_anchor_count},
                evidence_provenance="internal_link_engine",
                confidence_status="HIGH",
                classification=RemediationClassification.HUMAN_REVIEW
            ))

        # 10. Unsupported Answerability Structures
        answerability = report.unified_answerability
        if answerability and getattr(answerability, 'engine_source', ''):
            if answerability.unsupported_heading_topics_count > 0:
                remediations.append(RemediationRecord(
                    remediation_id=f"REM-ANS-UNSUPPORTED-{uuid4().hex[:8]}",
                    finding_id="FINDING-ANS-UNSUPPORTED-HEADING",
                    category="CONTENT",
                    problem=f"{answerability.unsupported_heading_topics_count} topic headings lack supporting explanatory text.",
                    why_it_matters="Headings without immediate supporting content appear as broken architectures to AI answer engines.",
                    recommended_action="Add clear, answer-first explanatory paragraphs immediately following empty headings.",
                    affected_urls=[url],
                    supporting_evidence={"unsupported_headings_count": answerability.unsupported_heading_topics_count},
                    evidence_provenance="answerability_engine",
                    confidence_status="HIGH",
                    classification=RemediationClassification.HUMAN_REVIEW
                ))

        return remediations
