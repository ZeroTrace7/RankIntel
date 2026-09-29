"""
Unit tests for RankIntel cross-engine conflict detection.
"""
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.models.schema import (
    EngineResult,
    RobotsEvidence,
    BotStatus,
    SchemaEvidence
)

def test_detect_ai_bot_misconfiguration():
    detector = ConflictDetector()

    robots_ev = RobotsEvidence(found=True)
    robots_ev.bot_access["OAI-SearchBot"] = BotStatus(
        bot="OAI-SearchBot", status="BLOCKED", category="search"
    )
    robots_ev.bot_access["GPTBot"] = BotStatus(
        bot="GPTBot", status="ALLOWED", category="training"
    )

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            robots=robots_ev
        )
    }

    conflicts = detector.detect(results)
    assert any(c.category == "AI_CRAWLER_MISCONFIG" for c in conflicts)

def test_detect_js_injected_schema():
    detector = ConflictDetector()

    static_schema = SchemaEvidence(detected_types=["Organization"])
    browser_schema = SchemaEvidence(detected_types=["Organization", "Product", "Review"])

    results = {
        "advertools_seo": EngineResult(
            engine_name="advertools_seo",
            schema_data=static_schema
        ),
        "browser_engine": EngineResult(
            engine_name="browser_engine",
            schema_data=browser_schema
        )
    }

    conflicts = detector.detect(results)
    assert any(c.category == "CLIENT_RENDERED_SCHEMA" for c in conflicts)
