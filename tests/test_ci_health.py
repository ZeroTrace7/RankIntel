"""
CI Health Check Test Suite — Verifies that all core entry points,
CLI runners, and multi-engine modules load cleanly without import errors.
"""
import pytest

def test_cli_entrypoint_importable():
    from rankintel.cli import main
    assert callable(main)
    assert "audit" in main.commands
    assert "compare" in main.commands

def test_mcp_server_entrypoint_importable():
    from rankintel.mcp.server import run_server, mcp
    assert callable(run_server)
    assert mcp is not None

def test_engines_all_importable():
    from rankintel.engines.seo_engine import SeoEngine
    from rankintel.engines.browser_engine import BrowserEngine
    from rankintel.engines.geo_engine import GeoEngine
    from rankintel.engines.mcp_engine import McpEngine
    from rankintel.engines.performance_engine import PerformanceEngine

    assert SeoEngine is not None
    assert BrowserEngine is not None
    assert GeoEngine is not None
    assert McpEngine is not None
    assert PerformanceEngine is not None
