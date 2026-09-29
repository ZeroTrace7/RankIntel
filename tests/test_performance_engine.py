"""
Unit tests for PerformanceEngine and Core Web Vitals telemetry.
"""
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
