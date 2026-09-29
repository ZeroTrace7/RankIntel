"""
Unit tests for GEO / AEO citability and answer-first analysis.
"""
from bs4 import BeautifulSoup
from rankintel.engines.geo_engine import GeoEngine

def test_geo_answer_first_detection():
    html = """
    <html>
        <body>
            <h2>What is BIS Certification in India?</h2>
            <p>BIS certification is mandatory for over 380 products under the Foreign Manufacturers Certification Scheme.</p>
            <h2>How to apply for ISI Mark?</h2>
            <p>The process requires submitting Form V along with factory audit documentation.</p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    engine = GeoEngine()
    evidence = engine.analyze_citability(soup, "https://example.com")

    assert evidence.overall_citability_score > 0
    assert len(evidence.question_h2s) == 2
    assert evidence.answer_first_ratio >= 0.5
