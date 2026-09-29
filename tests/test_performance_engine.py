"""
Unit tests for PerformanceEngine and Core Web Vitals telemetry.
"""
from unittest.mock import patch, MagicMock
from rankintel.engines.performance_engine import PerformanceEngine
from rankintel.references.cwv_thresholds import CWV_THRESHOLDS

def test_performance_engine_metric_evaluation():
    engine = PerformanceEngine()

    # Good LCP (2.1s <= 2.5s)
    m_good = engine._evaluate_metric("LCP", 2.1)
    assert m_good.status == "GOOD"
    assert m_good.value == 2.1

    # Needs Improvement LCP (3.2s)
    m_med = engine._evaluate_metric("LCP", 3.2)
    assert m_med.status == "NEEDS_IMPROVEMENT"

    # Poor LCP (5.0s)
    m_poor = engine._evaluate_metric("LCP", 5.0)
    assert m_poor.status == "POOR"

def test_performance_engine_ttfb():
    engine = PerformanceEngine()
    m_ttfb = engine._evaluate_metric("TTFB", 0.45)
    assert m_ttfb.status == "GOOD"
    assert m_ttfb.threshold_good == 0.8

def test_performance_engine_crux_parsing():
    engine = PerformanceEngine()

    fake_response = {
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2100},
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 120},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5},
                "EXPERIMENTAL_TIME_TO_FIRST_BYTE": {"percentile": 450}
            }
        },
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.88}}
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("requests.get", return_value=mock_resp):
        evidence = engine._query_pagespeed_api("https://example.com")

    assert evidence is not None
    assert evidence.source == "pagespeed_crux_field"
    assert evidence.lcp_ms == 2100.0
    assert evidence.inp_ms == 120.0
    assert evidence.cls == 0.05
    assert evidence.ttfb_ms == 450.0
    assert evidence.overall_performance_score == 88

def test_performance_engine_lighthouse_fallback():
    engine = PerformanceEngine()

    # Response without loadingExperience (small site)
    fake_response = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.72}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 3100},
                "cumulative-layout-shift": {"numericValue": 0.08},
                "first-contentful-paint": {"numericValue": 1400},
                "server-response-time": {"numericValue": 550},
                "total-blocking-time": {"numericValue": 180}
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("requests.get", return_value=mock_resp):
        evidence = engine._query_pagespeed_api("https://small-site.com")

    assert evidence is not None
    assert evidence.source == "pagespeed_lighthouse_lab"
    assert evidence.lcp_ms == 3100.0
    assert evidence.cls == 0.08
    assert evidence.overall_performance_score == 72
