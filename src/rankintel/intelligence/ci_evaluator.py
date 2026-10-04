"""
CI Evaluation Module - Determines if an audit complies with continuous integration policies.
"""
from typing import List
from rankintel.models.schema import SynthesisReport, CIPolicyConfig, CIPolicyResult

class CIEvaluator:
    """Evaluates SynthesisReport against a defined CI policy."""

    @staticmethod
    def evaluate(report: SynthesisReport, policy: CIPolicyConfig) -> CIPolicyResult:
        if not policy.enabled:
            return CIPolicyResult(passed=True)

        passed = True
        failure_reasons = []
        failed_classifications = set()
        
        remediations = getattr(report, "remediation_records", [])
        count = len(remediations)

        if policy.max_remediations is not None and count > policy.max_remediations:
            passed = False
            failure_reasons.append(f"Total remediations ({count}) exceeded maximum threshold ({policy.max_remediations}).")

        if policy.fail_on_classifications:
            for r in remediations:
                if r.classification.value in policy.fail_on_classifications:
                    passed = False
                    failed_classifications.add(r.classification.value)
            
            if failed_classifications:
                failure_reasons.append(f"Found remediations matching failing classifications: {', '.join(sorted(failed_classifications))}")

        return CIPolicyResult(
            passed=passed,
            remediation_count=count,
            failed_classifications_found=sorted(list(failed_classifications)),
            failure_reasons=failure_reasons
        )
