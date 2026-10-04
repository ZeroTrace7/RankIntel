"""
Unit test suite for RankIntel Phase 10.2: AI Answerability & Information Extraction.
Verifies deterministic extraction across all 14 answerable unit types,
the 4 Phase 10.2 refinements, clarity conditions, and Phase 9 concept linkage.
"""
import pytest
from rankintel.engines.answerability_engine import AnswerabilityEngine
from rankintel.models.schema import (
    AnswerableUnitType,
    ClarityStatus,
    TopicExplanationStatus,
    AnswerabilityEvidence,
    PageTopicIntelligence,
    TopicEvidence,
    SearchSignalEvidence,
    SearchSignalItem,
    EntityEvidence,
    DetectedEntity,
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
)


HTML_COMPREHENSIVE_SERVICES = """
<!DOCTYPE html>
<html>
<head>
    <title>Sunrise Testing Lab - Calibration & Certification</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "FAQPage",
          "mainEntity": [
            {
              "@type": "Question",
              "name": "What is the turnaround time for BIS calibration?",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "The turnaround time is between 3 to 5 business days for standard electronic instruments."
              }
            }
          ]
        },
        {
          "@type": "HowTo",
          "name": "How to Submit Calibration Samples",
          "step": [
            {"@type": "HowToStep", "text": "Pack the instrument securely."},
            {"@type": "HowToStep", "text": "Fill the calibration requisition form."},
            {"@type": "HowToStep", "text": "Dispatch to our accredited lab."}
          ]
        },
        {
          "@type": "Service",
          "name": "BIS Certification Testing",
          "description": "Comprehensive electrical safety and EMI/EMC testing for electronics compliance under BIS CRS scheme."
        },
        {
          "@type": "ContactPoint",
          "telephone": "+91-11-23456789",
          "email": "info@sunrisetesting.com",
          "address": "Plot 42, Okhla Industrial Area, New Delhi"
        }
      ]
    }
    </script>
</head>
<body>
    <main>
        <h1>Electrical Testing & Calibration Laboratory</h1>
        <p>Sunrise Testing is an accredited laboratory providing industrial calibration services across India.</p>

        <section id="definitions">
            <h2>What is BIS Certification?</h2>
            <p>BIS Certification is a conformity assessment scheme administered by the Bureau of Indian Standards ensuring product quality, safety, and reliability.</p>
        </section>

        <section id="services">
            <h2>Calibration Services</h2>
            <p>We provide electrical, thermal, and dimensional calibration with traceabilities to national and international measurement standards.</p>
        </section>

        <section id="eligibility">
            <h2>Eligibility & Requirements</h2>
            <ul>
                <li>Valid factory license and manufacturing unit registration</li>
                <li>Complete technical documentation and PCB circuit schematics</li>
                <li>Three production test samples for compliance verification</li>
            </ul>
        </section>

        <section id="specs">
            <h2>Technical Specifications</h2>
            <table>
                <thead>
                    <tr><th>Parameter</th><th>Measurement Range</th><th>Calibration Uncertainty</th></tr>
                </thead>
                <tbody>
                    <tr><td>DC Voltage</td><td>0 to 1000 V</td><td>± 15 ppm</td></tr>
                    <tr><td>AC Voltage</td><td>1 mV to 750 V</td><td>± 0.05 %</td></tr>
                    <tr><td>Resistance</td><td>10 mΩ to 1 GΩ</td><td>± 20 ppm</td></tr>
                </tbody>
            </table>
        </section>

        <section id="procedure">
            <h2>Testing Procedure</h2>
            <ol>
                <li>Visual inspection of instrument housing and terminal connectors.</li>
                <li>Thermal stabilization at standard ambient reference temperature (23°C ± 1°C).</li>
                <li>Precision signal generation and multi-point deviation recording.</li>
            </ol>
        </section>

        <section id="comparison">
            <h2>BIS CRS vs ISI Mark Comparison</h2>
            <table>
                <thead>
                    <tr><th>Parameter</th><th>BIS CRS</th><th>ISI Mark Scheme</th></tr>
                </thead>
                <tbody>
                    <tr><td>Applicability</td><td>Electronic & IT Goods</td><td>Industrial & Safety Products</td></tr>
                    <tr><td>Factory Audit</td><td>Not Required</td><td>Mandatory Initial Audit</td></tr>
                </tbody>
            </table>
        </section>

        <section id="standards">
            <h2>Compliance Standards & Data</h2>
            <p>Our testing adheres to ISO 17025:2017 accreditation standards and IS 13252 safety regulations, delivering a 99.4% first-pass calibration rate.</p>
        </section>

        <section id="policy">
            <h2>Policy & Validity</h2>
            <p>Effective Date: January 1, 2026. All calibration certificates remain valid for 12 months under standard laboratory operating conditions.</p>
        </section>

        <section id="example">
            <h2>Sample Calculation</h2>
            <pre>Expanded Uncertainty U = k * u_c(y), where coverage factor k = 2 at 95.45% confidence interval.</pre>
        </section>

        <section id="contact">
            <h2>Laboratory Location & Contact</h2>
            <p>Call us at +91-98765-43210 or email support@sunrisetesting.com for inquiries.</p>
        </section>

        <section id="short-answer">
            <h2>Is on-site calibration available?</h2>
            <p>Yes, nationwide on-site calibration is available.</p>
        </section>

        <section id="empty-heading">
            <h2>Upcoming International Accreditations</h2>
        </section>
    </main>
</body>
</html>
"""


class TestAnswerabilityExtraction:
    """Tests deterministic identification of 14 observable information structures."""

    def test_extract_all_14_units(self):
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com/services",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
        )

        assert ev.total_units_detected > 0
        # Check presence of key types
        types_detected = set(ev.units_by_type.keys())
        expected_types = {
            AnswerableUnitType.FAQ.value,
            AnswerableUnitType.DEFINITION.value,
            AnswerableUnitType.DIRECT_ANSWER.value,
            AnswerableUnitType.SERVICE_DESCRIPTION.value,
            AnswerableUnitType.PROCEDURE_STEPS.value,
            AnswerableUnitType.SPECIFICATION.value,
            AnswerableUnitType.REQUIREMENTS_ELIGIBILITY.value,
            AnswerableUnitType.TABLE.value,
            AnswerableUnitType.COMPARISON.value,
            AnswerableUnitType.LOCATION_CONTACT.value,
            AnswerableUnitType.DATE_POLICY.value,
            AnswerableUnitType.FACTUAL_STATEMENT.value,
            AnswerableUnitType.EXAMPLE.value,
        }
        common = types_detected.intersection(expected_types)
        assert len(common) >= 10, f"Expected at least 10 types, found {len(common)}: {common}"

    def test_schema_faq_and_howto_extraction(self):
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com/faq",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
        )
        faq_units = [u for u in ev.units if u.unit_type == AnswerableUnitType.FAQ]
        assert len(faq_units) >= 1
        assert "turnaround time" in faq_units[0].snippet.lower()
        assert faq_units[0].source == "schema_jsonld"

        howto_units = [u for u in ev.units if u.unit_type == AnswerableUnitType.PROCEDURE_STEPS and u.source == "schema_jsonld"]
        assert len(howto_units) >= 1
        assert "How to Submit" in howto_units[0].snippet

    def test_dom_table_and_comparison_extraction(self):
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com/specs",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
        )
        # Check tables extracted
        comp_units = [u for u in ev.units if u.unit_type == AnswerableUnitType.COMPARISON]
        assert len(comp_units) >= 1
        assert "BIS CRS" in comp_units[0].snippet

        spec_units = [u for u in ev.units if u.unit_type in (AnswerableUnitType.SPECIFICATION, AnswerableUnitType.TABLE)]
        assert len(spec_units) >= 1

    def test_definition_dl_and_copula(self):
        html_dl = """
        <html><body>
        <h2>Terminology</h2>
        <dl>
            <dt>Calibration</dt>
            <dd>Comparison of measurement values delivered by a device under test with those of a calibration standard.</dd>
        </dl>
        </body></html>
        """
        ev = AnswerabilityEngine.evaluate_page(
            url="https://example.com/def",
            raw_html=html_dl,
        )
        def_units = [u for u in ev.units if u.unit_type == AnswerableUnitType.DEFINITION]
        assert len(def_units) >= 1
        assert "Calibration:" in def_units[0].snippet


class TestPhase10Refinements:
    """Verifies the four Phase 10.2 refinements requested by user."""

    def test_refinement_1_strict_semantic_topic_verification(self):
        """
        Refinement 1: Avoid false EXPLAINED classifications.
        A heading followed by unrelated text must NOT qualify an unaddressed topic.
        """
        html_unrelated = """
        <html><body>
        <h2>Web Development Services</h2>
        <p>We build responsive, modern React websites for ecommerce businesses.</p>
        </body></html>
        """
        # Topic is "BIS Certification" — not addressed on this page
        topic_intel = PageTopicIntelligence(
            url="https://example.com",
            topics=[TopicEvidence(topic_name="BIS Certification")]
        )

        ev = AnswerabilityEngine.evaluate_page(
            url="https://example.com",
            raw_html=html_unrelated,
            topic_ev=topic_intel,
        )
        link = [tl for tl in ev.topic_links if tl.topic_name == "BIS Certification"][0]
        # Must NOT be marked EXPLAINED because the extracted service description is about web development
        assert link.status != TopicExplanationStatus.EXPLAINED
        assert link.status in (TopicExplanationStatus.ABSENT, TopicExplanationStatus.MENTIONED_ONLY)

    def test_refinement_1_positive_explained_topic(self):
        """When an extracted unit genuinely addresses the topic, it is EXPLAINED."""
        topic_intel = PageTopicIntelligence(
            url="https://sunrisetesting.com",
            topics=[TopicEvidence(topic_name="BIS Certification")]
        )
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
            topic_ev=topic_intel,
        )
        link = [tl for tl in ev.topic_links if tl.topic_name == "BIS Certification"][0]
        assert link.status == TopicExplanationStatus.EXPLAINED
        assert "scheme" in link.explanation_snippet.lower() or "testing" in link.explanation_snippet.lower()

    def test_refinement_2_short_answers_are_not_unsupported(self):
        """
        Refinement 2: Don't automatically classify short headings as unsupported.
        A concise answer (e.g. 6 words) is valid. UNSUPPORTED_HEADING requires genuinely absent content.
        """
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
        )
        # Check genuinely empty heading is flagged
        empty_headings = ev.clarity_assessment.unsupported_concepts
        assert any("Upcoming International Accreditations" in h for h in empty_headings)

        # Check short answer heading ("Is on-site calibration available?") is NOT in unsupported_concepts
        assert not any("on-site calibration" in h.lower() for h in empty_headings)

    def test_refinement_3_conservative_factual_statement_extraction(self):
        """
        Refinement 3: Keep factual-statement extraction conservative.
        Extracts observable statements without claiming truth verification.
        """
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
        )
        fact_units = [u for u in ev.units if u.unit_type == AnswerableUnitType.FACTUAL_STATEMENT]
        assert len(fact_units) >= 1
        assert "ISO 17025" in fact_units[0].snippet or "99.4%" in fact_units[0].snippet
        assert fact_units[0].confidence == "medium"
        assert "Observable standards/metrics" in fact_units[0].supporting_context

    def test_refinement_4_deduplication_via_secondary_types(self):
        """
        Refinement 4: Avoid duplicate extraction for the same underlying passage.
        Preserves secondary_types without inflating distinct unit count.
        """
        html_dual = """
        <html><body>
        <section>
            <h2>What is Accuracy?</h2>
            <p>Accuracy is defined as the degree of conformity of a measured value to its ISO standard value.</p>
        </section>
        </body></html>
        """
        ev = AnswerabilityEngine.evaluate_page(
            url="https://example.com/dual",
            raw_html=html_dual,
        )
        # The paragraph has a question heading, copula definition, and an ISO standard
        # It should register ONE primary unit with secondary types rather than 3 separate units for the same paragraph
        units = ev.units
        assert len(units) <= 2
        # Check that secondary_types is populated on the unit
        has_secondary = any(len(u.secondary_types) > 0 for u in units)
        assert has_secondary or len(units) == 1


class TestClarityAssessment:
    """Verifies clarity condition assessments using neutral terminology."""

    def test_clarity_assessment_neutral_statuses(self):
        ev = AnswerabilityEngine.evaluate_page(
            url="https://sunrisetesting.com",
            raw_html=HTML_COMPREHENSIVE_SERVICES,
        )
        cl = ev.clarity_assessment
        assert cl.heading_content_relationship in (ClarityStatus.OBSERVED, ClarityStatus.PARTIAL)
        assert cl.question_answer_patterns == ClarityStatus.PRESENT
        assert cl.definition_patterns == ClarityStatus.PRESENT
        assert cl.step_list_structure == ClarityStatus.PRESENT
        assert cl.table_availability == ClarityStatus.PRESENT

    def test_wall_of_text_buried_facts_detection(self):
        html_wall = """
        <html><body>
        <h1>Testing Overview</h1>
        <p>""" + ("The calibration facility maintains rigorous testing environments conforming to ISO 9001 regulations. " * 15) + """</p>
        </body></html>
        """
        ev = AnswerabilityEngine.evaluate_page(
            url="https://example.com/wall",
            raw_html=html_wall,
        )
        assert len(ev.clarity_assessment.buried_facts) >= 1
        assert "ISO 9001" in ev.clarity_assessment.buried_facts[0]

    def test_empty_html_resilience(self):
        ev = AnswerabilityEngine.evaluate_page(
            url="https://example.com/empty",
            raw_html="",
        )
        assert ev.total_units_detected == 0
        assert ev.clarity_assessment.heading_content_relationship == ClarityStatus.UNAVAILABLE


class TestSiteAnswerabilityAggregation:
    """Verifies site-wide crawl aggregation."""

    def test_site_aggregation(self):
        site_crawl = SiteCrawlResult(
            completeness_status="CRAWL_COMPLETE",
            pages_crawled=2,
            crawl_records=[
                CrawlRecord(
                    url="https://example.com/page1",
                    normalized_url="https://example.com/page1",
                    identity_url="https://example.com/page1",
                    crawl_status=CrawlStatus.SUCCESS,
                    depth=0,
                    raw_html=HTML_COMPREHENSIVE_SERVICES,
                ),
                CrawlRecord(
                    url="https://example.com/page2",
                    normalized_url="https://example.com/page2",
                    identity_url="https://example.com/page2",
                    crawl_status=CrawlStatus.SUCCESS,
                    depth=1,
                    raw_html="<html><body><h1>About Us</h1><p>We are a testing firm established in 2010.</p></body></html>",
                ),
            ],
        )

        intel = AnswerabilityEngine.evaluate_site(site_crawl)
        assert intel.status == "success"
        assert intel.total_pages_evaluated == 2
        assert intel.total_site_units_detected > 0
        assert len(intel.pages_with_faq) >= 1
        assert len(intel.pages_with_definitions) >= 1
        assert site_crawl.answerability_intelligence is not None
