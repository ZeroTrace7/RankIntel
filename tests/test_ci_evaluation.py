import pytest
from rankintel.intelligence.ci_evaluator import CIEvaluator
from rankintel.models.schema import SynthesisReport, CIPolicyConfig, RemediationRecord, RemediationClassification

def test_ci_policy_passed():
    report = SynthesisReport(url="https://test.com", domain="test.com", timestamp="2026-10-01")
    report.remediation_records = [
        RemediationRecord(
            remediation_id="R1", finding_id="F1", category="seo", problem="p", why_it_matters="w", 
            recommended_action="a", evidence_provenance="p", confidence_status="high", 
            classification=RemediationClassification.AUTO_SAFE
        )
    ]
    policy = CIPolicyConfig(enabled=True)
    result = CIEvaluator.evaluate(report, policy)
    assert result.passed is True
    assert result.remediation_count == 1

def test_ci_policy_failed_on_classification():
    report = SynthesisReport(url="https://test.com", domain="test.com", timestamp="2026-10-01")
    report.remediation_records = [
        RemediationRecord(
            remediation_id="R1", finding_id="F1", category="seo", problem="p", why_it_matters="w", 
            recommended_action="a", evidence_provenance="p", confidence_status="high", 
            classification=RemediationClassification.HUMAN_REVIEW
        )
    ]
    policy = CIPolicyConfig(enabled=True, fail_on_classifications=["HUMAN_REVIEW"])
    result = CIEvaluator.evaluate(report, policy)
    assert result.passed is False
    assert "HUMAN_REVIEW" in result.failed_classifications_found

def test_ci_policy_failed_on_threshold():
    report = SynthesisReport(url="https://test.com", domain="test.com", timestamp="2026-10-01")
    report.remediation_records = [
        RemediationRecord(
            remediation_id="R1", finding_id="F1", category="seo", problem="p", why_it_matters="w", 
            recommended_action="a", evidence_provenance="p", confidence_status="high", 
            classification=RemediationClassification.AUTO_SAFE
        ),
        RemediationRecord(
            remediation_id="R2", finding_id="F2", category="seo", problem="p", why_it_matters="w", 
            recommended_action="a", evidence_provenance="p", confidence_status="high", 
            classification=RemediationClassification.AUTO_SAFE
        )
    ]
    policy = CIPolicyConfig(enabled=True, max_remediations=1)
    result = CIEvaluator.evaluate(report, policy)
    assert result.passed is False
    assert result.remediation_count == 2
