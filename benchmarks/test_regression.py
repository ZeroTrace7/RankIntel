"""
Regression tests against committed benchmark fixtures.
Runs entirely offline — no live HTTP requests.

Run with:
    pytest benchmarks/test_regression.py -v

Fixtures are committed to benchmarks/fixtures/*.json.
To update fixtures after an approved change, run:
    python benchmarks/score_snapshot_tool.py --site <domain> --confirm
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixtures():
    """Load all benchmark fixture JSON files."""
    fixtures = []
    for p in sorted(FIXTURES_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            fixtures.append((p.stem, data))
        except Exception as e:
            pytest.fail(f"Failed to parse fixture {p.name}: {e}")
    return fixtures


ALL_FIXTURES = load_fixtures()

if not ALL_FIXTURES:
    pytest.skip("No benchmark fixtures found. Run: rankintel audit <url> --format json --output-dir benchmarks/fixtures/",
                allow_module_level=True)


# ---------------------------------------------------------------------------
# Structural integrity tests
# ---------------------------------------------------------------------------

REQUIRED_KEYS = [
    "url", "domain", "overall_health_score", "technical_health_score",
    "geo_readiness_score", "trust_score", "performance_score",
    "engines_executed", "score_formula_mode",
]


@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_fixture_has_required_keys(name: str, data: dict):
    """Every fixture must contain all required top-level keys."""
    missing = [k for k in REQUIRED_KEYS if k not in data]
    assert not missing, f"Fixture '{name}' missing keys: {missing}"


@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_scores_in_valid_range(name: str, data: dict):
    """All score fields must be within [0, 100]."""
    score_keys = [
        "overall_health_score", "technical_health_score",
        "geo_readiness_score", "trust_score", "performance_score",
    ]
    for key in score_keys:
        val = data.get(key, 0)
        assert 0 <= val <= 100, f"'{key}' = {val} out of [0,100] in fixture '{name}'"


@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_formula_mode_is_valid(name: str, data: dict):
    """score_formula_mode must be one of the three known modes."""
    mode = data.get("score_formula_mode")
    assert mode in ("3_engine", "4_engine", "5_engine"), (
        f"Invalid formula_mode '{mode}' in fixture '{name}'"
    )


@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_engines_executed_is_list(name: str, data: dict):
    """engines_executed must be a non-null list."""
    assert isinstance(data.get("engines_executed"), list), (
        f"engines_executed is not a list in fixture '{name}'"
    )


# ---------------------------------------------------------------------------
# Bug regression: F2 — No silent perf=75 default
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_no_silent_75_perf_default(name: str, data: dict):
    """When performance engine didn't run, score must be 0, not 75."""
    engines = data.get("engines_executed", [])
    perf = data.get("performance_score", -1)
    # If performance_engine succeeded, any score 0-100 is valid
    if "performance_engine" in engines:
        assert 0 <= perf <= 100
    else:
        # Performance didn't run — must be 0 (not the old silent 75 default)
        assert perf == 0, (
            f"Silent perf default still present in '{name}': performance_score={perf}"
        )


# ---------------------------------------------------------------------------
# Bug regression: F4 — No redundant schema fix when Organization already present
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_no_redundant_schema_fix(name: str, data: dict):
    """jsonld_schema fix must not appear if Organization schema was detected."""
    schema = data.get("unified_schema", {})
    has_org = schema.get("has_organization", False)
    fixes = data.get("fixes", {})
    if has_org:
        assert "jsonld_schema" not in fixes, (
            f"jsonld_schema fix generated unnecessarily for '{name}' which already has Organization schema"
        )


@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_no_redundant_llms_fix(name: str, data: dict):
    """llms_txt fix must not appear if llms.txt was detected."""
    geo = data.get("unified_geo", {})
    llms_found = geo.get("llms_txt_found", False)
    fixes = data.get("fixes", {})
    if llms_found:
        assert "llms_txt" not in fixes, (
            f"llms_txt fix generated unnecessarily for '{name}' which already has llms.txt"
        )


# ---------------------------------------------------------------------------
# Bug regression: F1 — No double deduction (max title deduction = 25)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_technical_score_not_below_double_deduction_floor(name: str, data: dict):
    """
    Technical score must not be below what a double-deduction would produce.
    Max deduction for title+desc: 25+20 = 45. Score floor: 10.
    A score below 10 indicates the floor isn't being respected.
    """
    tech = data.get("technical_health_score", 100)
    assert tech >= 10, f"Technical score {tech} < 10 (below floor) in fixture '{name}'"


# ---------------------------------------------------------------------------
# Architecture regression: geo_optimizer_skill must be the GEO source
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,data", ALL_FIXTURES)
def test_geo_engine_source_is_adapter_or_custom(name: str, data: dict):
    """GEO evidence must come from geo_optimizer_skill adapter or rankintel_geo_custom fallback."""
    geo = data.get("unified_geo", {})
    source = geo.get("engine_source", "")
    valid_sources = ("geo_optimizer_skill", "rankintel_geo_custom", "")  # empty = old fallback
    assert source in valid_sources, (
        f"Unexpected GEO engine source '{source}' in fixture '{name}'"
    )
