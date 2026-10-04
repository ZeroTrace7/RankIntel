import pytest
from rankintel.intelligence.remediation_engine import RemediationEngine
from rankintel.models.schema import (
    SynthesisReport,
    OnPageEvidence,
    ImageSEOEvidence,
    ImageDetail,
    RemediationClassification,
    SecurityEvidence,
    SecurityFinding,
    SecuritySeverity,
    RobotsEvidence,
    EntityEvidence,
    StructuredVisibleAgreement,
    StructuredVisibleAgreementStatus,
    AccessibilityEvidence,
    AccessibilityViolation,
    AccessibilitySeverity,
    InternalLinkEvidence
)

@pytest.fixture
def empty_report():
    return SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_on_page=OnPageEvidence(status_code=200, title="Test", meta_description="Desc", h1_text=["Test"], canonical="https://test.com", canonical_url="https://test.com", engine_source="on_page_engine")
    )

def test_remediation_generated_from_valid_finding():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_on_page=OnPageEvidence(status_code=200, title="", meta_description="Desc", h1_text=["Test"], canonical="https://test.com", canonical_url="https://test.com", engine_source="on_page_engine")
    )
    remediations = RemediationEngine.generate_remediations(report)
    assert len(remediations) == 1
    assert remediations[0].finding_id == "FINDING-ON-PAGE-NO-TITLE"
    assert remediations[0].classification == RemediationClassification.AUTO_SAFE
    assert remediations[0].evidence_provenance == "on_page_engine"

def test_remediation_preserves_finding_provenance():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_robots=RobotsEvidence(found=False, engine_source="robots_engine")
    )
    remediations = RemediationEngine.generate_remediations(report)
    assert len(remediations) == 1
    assert remediations[0].evidence_provenance == "robots_engine"
    assert remediations[0].supporting_evidence["robots_txt_found"] is False

def test_unknown_unavailable_evidence_does_not_produce_unsafe_remediation():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_on_page=OnPageEvidence(status_code=404, engine_source="on_page_engine") # Not 200, so we shouldn't recommend title changes
    )
    remediations = RemediationEngine.generate_remediations(report)
    assert len(remediations) == 0

def test_auto_safe_classification():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_security=SecurityEvidence(engine_source="security_engine", findings=[
            SecurityFinding(
                code="HSTS_MISSING",
                title="Strict-Transport-Security Missing",
                category="security_vulnerability",
                description="desc",
                severity=SecuritySeverity.HIGH,
                recommendation="rec"
            )
        ])
    )
    remediations = RemediationEngine.generate_remediations(report)
    assert any(r.classification == RemediationClassification.AUTO_SAFE and r.finding_id == "FINDING-SEC-HSTS-MISSING" for r in remediations)

def test_human_review_classification():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_on_page=OnPageEvidence(status_code=200, title="Test", meta_description="", engine_source="on_page_engine", canonical="https://test.com", canonical_url="https://test.com")
    )
    remediations = RemediationEngine.generate_remediations(report)
    assert any(r.classification == RemediationClassification.HUMAN_REVIEW and r.finding_id == "FINDING-ON-PAGE-NO-DESC" for r in remediations)

def test_multiple_findings_do_not_create_duplicate_records():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_accessibility=AccessibilityEvidence(engine_source="accessibility_engine", violations=[
            AccessibilityViolation(rule_id="label", description="desc1", severity=AccessibilitySeverity.CRITICAL),
            AccessibilityViolation(rule_id="label", description="desc2", severity=AccessibilitySeverity.CRITICAL)
        ])
    )
    remediations = RemediationEngine.generate_remediations(report)
    assert len(remediations) == 1
    assert remediations[0].supporting_evidence["violation_count"] == 2

def test_remediation_output_deterministic():
    report = SynthesisReport(
        url="https://test.com",
        domain="test.com",
        timestamp="2026-10-01",
        unified_on_page=OnPageEvidence(status_code=200, title="", meta_description="", engine_source="on_page_engine")
    )
    remediations1 = RemediationEngine.generate_remediations(report)
    remediations2 = RemediationEngine.generate_remediations(report)
    # IDs will be different due to uuid4, but everything else same
    assert [r.finding_id for r in remediations1] == [r.finding_id for r in remediations2]
    assert [r.classification for r in remediations1] == [r.classification for r in remediations2]

def test_existing_recommendation_behavior_remains_compatible(empty_report):
    # This just ensures we can still create a report with empty remediations and valid old actions.
    empty_report.remediation_records = RemediationEngine.generate_remediations(empty_report)
    assert empty_report.prioritized_actions == []
    assert empty_report.remediation_records == []
