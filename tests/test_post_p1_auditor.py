from rankintel.benchmark.post_p1_auditor import generate_audit_report, GapStatus

def test_audit_report_generation():
    report = generate_audit_report()
    
    assert report.entity_audit.status == GapStatus.RESOLVED
    assert report.topic_audit.status == GapStatus.RESOLVED
    assert report.intent_audit.status == GapStatus.RESOLVED
    assert report.forms_buttons_audit.status == GapStatus.RESOLVED
    
    # Verify reclassifications
    gaps = {g.gap_id: g.status for g in report.gap_reclassifications}
    assert gaps["GAP-ENT-001"] == GapStatus.RESOLVED
    assert gaps["GAP-TOPIC-001"] == GapStatus.RESOLVED
    assert gaps["GAP-INTENT-001"] == GapStatus.RESOLVED
    assert gaps["GAP-AGENT-001"] == GapStatus.RESOLVED
    
    assert gaps["GAP-ENT-004"] == GapStatus.STILL_VALID
    
    # Verify new gaps
    new_gaps = {g.gap_id: g.status for g in report.newly_discovered_gaps}
    assert "GAP-RETRIEVAL-003" in new_gaps
    assert new_gaps["GAP-RETRIEVAL-003"] == GapStatus.NEWLY_DISCOVERED
