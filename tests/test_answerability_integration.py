"""
Integration test suite for RankIntel Phase 10.2: AI Answerability & Information Extraction.
Verifies end-to-end integration across:
- EvidenceCollector (Step 18, zero redundant network calls)
- ProvenanceTagger (provenance preservation)
- ConflictDetector (answerability conflicts, data-nosnippet suppression)
- IntelligenceSynthesizer (reconciliation & health score formula invariance)
- MarkdownReporter (single-page section & site crawl intelligence)
- JsonReporter (schema compliance & serialization)
- CLI (scorecard compact row)
- MCP Server (rankintel_audit telemetry fields)
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from rankintel.evidence.collector import EvidenceCollector
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.reporters.markdown import MarkdownReporter
from rankintel.reporters.json_reporter import JsonReporter
from rankintel.mcp.server import rankintel_audit
from rankintel.cli import main
from rankintel.models.schema import (
    CrawlRecord,
    CrawlStatus,
    SiteCrawlResult,
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    CloudIntelligenceEvidence,
    EngineResult,
    AnswerabilityEvidence,
    SiteAnswerabilityIntelligence,
    AnswerableUnitType,
    ClarityStatus,
    TopicExplanationStatus,
    AnswerableInformationUnit,
    InformationClarityAssessment,
    TopicAnswerabilityLink,
)


def build_mock_answerability_evidence(url: str = "https://example.com") -> AnswerabilityEvidence:
    """Build a deterministic mock AnswerabilityEvidence object."""
    unit1 = AnswerableInformationUnit(
        unit_id="unit-faq-0",
        unit_type=AnswerableUnitType.FAQ,
        secondary_types=[AnswerableUnitType.DIRECT_ANSWER],
        section_heading="What is BIS Certification?",
        snippet="Q: What is BIS Certification? | A: BIS Certification guarantees product safety.",
        content_location="body > section > p",
        structural_type="heading_question_answer",
        is_explicit=True,
        extraction_method="dom_heading_question_answer",
        confidence="high",
    )
    unit2 = AnswerableInformationUnit(
        unit_id="unit-table-1",
        unit_type=AnswerableUnitType.TABLE,
        section_heading="Technical Specifications",
        snippet="Voltage | 230 V\nFrequency | 50 Hz",
        content_location="body > table",
        structural_type="html_table_3rows",
        is_explicit=True,
        extraction_method="dom_table_parser",
        confidence="high",
    )
    clarity = InformationClarityAssessment(
        heading_content_relationship=ClarityStatus.OBSERVED,
        question_answer_patterns=ClarityStatus.PRESENT,
        definition_patterns=ClarityStatus.PRESENT,
        step_list_structure=ClarityStatus.PRESENT,
        table_availability=ClarityStatus.PRESENT,
        unsupported_concepts=[],
        buried_facts=[],
        obscured_or_fragmented_items=[],
    )
    topic_link = TopicAnswerabilityLink(
        topic_name="BIS Certification",
        status=TopicExplanationStatus.EXPLAINED,
        section_heading="What is BIS Certification?",
        associated_unit_ids=["unit-faq-0"],
        unit_types=[AnswerableUnitType.FAQ],
        explanation_snippet="BIS Certification guarantees product safety.",
        is_explicit=True,
    )
    return AnswerabilityEvidence(
        url=url,
        engine_source="answerability_engine",
        total_units_detected=2,
        units_by_type={"FAQ": 1, "TABLE": 1},
        units=[unit1, unit2],
        clarity_assessment=clarity,
        topic_links=[topic_link],
        explained_topics_count=1,
        mentioned_only_topics_count=0,
        unsupported_heading_topics_count=0,
        facts=["Detected 2 observable information units."],
        analyses=["Page features structured FAQ and tabular specs."],
    )


class TestCollectorStep18Integration:
    """Verifies that EvidenceCollector properly executes Step 18 without extra HTTP requests."""

    def test_collector_runs_answerability_engine(self):
        collector = EvidenceCollector()
        mock_html = """
        <html><body>
        <h2>What is Calibration?</h2>
        <p>Calibration is defined as comparing a device to an established standard.</p>
        </body></html>
        """
        mock_browser = EngineResult(
            engine_name="browser_engine",
            status="success",
            raw_html=mock_html,
            on_page=OnPageEvidence(url="https://example.com", status_code=200),
        )
        mock_seo = EngineResult(
            engine_name="advertools_seo",
            status="success",
            on_page=OnPageEvidence(url="https://example.com", status_code=200, title="Calibration"),
            robots=RobotsEvidence(status_code=200, raw_content="User-agent: *\nAllow: /\n"),
        )

        # Patch heavy network engines
        with patch.object(collector.seo_engine, "execute", return_value=mock_seo), \
             patch.object(collector.browser_engine, "execute_sync", return_value=mock_browser), \
             patch.object(collector.geo_engine, "execute", return_value=EngineResult(engine_name="rankintel_geo", status="success")), \
             patch.object(collector.performance_engine, "execute", return_value=EngineResult(engine_name="performance_engine", status="success")), \
             patch.object(collector.mcp_engine, "execute", return_value=EngineResult(engine_name="mcp_cloud", status="skipped")):

            results = collector.collect("https://example.com")

            assert "answerability_engine" in results
            ans_res = results["answerability_engine"]
            assert ans_res.status == "success"
            assert ans_res.answerability is not None
            assert ans_res.answerability.total_units_detected >= 1


class TestConflictDetection:
    """Verifies conflict detection for answerability and snippet suppression."""

    def test_unsupported_heading_conflict(self):
        unsupported_link = TopicAnswerabilityLink(
            topic_name="ISO Certification",
            status=TopicExplanationStatus.UNSUPPORTED_HEADING,
            section_heading="ISO Certification Process",
            is_explicit=False,
        )
        ans_ev = AnswerabilityEvidence(
            url="https://example.com",
            total_units_detected=0,
            topic_links=[unsupported_link],
        )
        engine_results = {
            "answerability_engine": EngineResult(
                engine_name="answerability_engine",
                status="success",
                answerability=ans_ev,
            )
        }
        conflicts = ConflictDetector().detect(engine_results)
        gap_conflicts = [c for c in conflicts if c.category == "CONTENT_ANSWERABILITY_GAP"]
        assert len(gap_conflicts) == 1
        assert "ISO Certification" in gap_conflicts[0].description

    def test_data_nosnippet_suppression_conflict(self):
        clarity = InformationClarityAssessment(
            obscured_or_fragmented_items=["Unit 'unit-faq-0' obscured by data-nosnippet at div#faq"],
        )
        ans_ev = AnswerabilityEvidence(
            url="https://example.com",
            total_units_detected=1,
            clarity_assessment=clarity,
        )
        engine_results = {
            "answerability_engine": EngineResult(
                engine_name="answerability_engine",
                status="success",
                answerability=ans_ev,
            )
        }
        conflicts = ConflictDetector().detect(engine_results)
        snip_conflicts = [c for c in conflicts if c.category == "SNIPPET_SUPPRESSION_CONFLICT"]
        assert len(snip_conflicts) == 1
        assert "data-nosnippet" in snip_conflicts[0].description


class TestProvenanceTagger:
    """Verifies evidence provenance tracking for answerability findings."""

    def test_provenance_tagging(self):
        ans_ev = build_mock_answerability_evidence("https://example.com")
        engine_results = {
            "answerability_engine": EngineResult(
                engine_name="answerability_engine",
                status="success",
                answerability=ans_ev,
            )
        }
        tags = ProvenanceTagger.tag(engine_results)
        ans_tags = [t for t in tags if t.engine == "answerability_engine"]
        assert len(ans_tags) >= 1
        assert any("Observable Information Units" in t.finding for t in ans_tags)


class TestSynthesizerFormulaInvariance:
    """Verifies that unified_answerability is reconciled and health scores remain strictly invariant."""

    def test_formula_invariance_and_reconciliation(self):
        synthesizer = IntelligenceSynthesizer()
        ans_ev = build_mock_answerability_evidence("https://example.com")

        # Baseline run without answerability
        res_baseline = {
            "advertools_seo": EngineResult(
                engine_name="advertools_seo",
                status="success",
                on_page=OnPageEvidence(url="https://example.com", title="Example Title for Compliance", meta_description="Example meta description for compliance"),
                robots=RobotsEvidence(found=True, is_allowed=True),
                schema_data=SchemaEvidence(),
            ),
            "rankintel_geo": EngineResult(engine_name="rankintel_geo", status="success", geo_aeo=GeoAeoEvidence()),
            "crawl4ai_browser": EngineResult(engine_name="crawl4ai_browser", status="success", on_page=OnPageEvidence(url="https://example.com")),
            "performance_engine": EngineResult(engine_name="performance_engine", status="success", performance=PerformanceEvidence()),
        }
        report_baseline = synthesizer.synthesize("https://example.com", res_baseline)

        # Run with answerability engine added
        res_with_ans = dict(res_baseline)
        res_with_ans["answerability_engine"] = EngineResult(
            engine_name="answerability_engine",
            status="success",
            answerability=ans_ev,
        )
        report_with_ans = synthesizer.synthesize("https://example.com", res_with_ans)

        # Strict score formula invariance check!
        assert report_with_ans.overall_health_score == report_baseline.overall_health_score
        assert report_with_ans.geo_readiness_score == report_baseline.geo_readiness_score
        assert report_with_ans.technical_health_score == report_baseline.technical_health_score
        assert report_with_ans.trust_score == report_baseline.trust_score
        assert report_with_ans.performance_score == report_baseline.performance_score
        assert report_with_ans.score_formula_mode == report_baseline.score_formula_mode

        # Check reconciliation
        assert report_with_ans.unified_answerability is not None
        assert report_with_ans.unified_answerability.total_units_detected == 2


class TestMarkdownAndJsonReporting:
    """Verifies single-page and crawl markdown sections and JSON serialization."""

    def test_markdown_single_page_and_crawl_sections(self):
        synthesizer = IntelligenceSynthesizer()
        ans_ev = build_mock_answerability_evidence("https://example.com")
        engine_results = {
            "advertools_seo": EngineResult(
                engine_name="advertools_seo",
                status="success",
                on_page=OnPageEvidence(url="https://example.com", title="Test Title", meta_description="Test Description"),
                robots=RobotsEvidence(found=True, is_allowed=True),
                schema_data=SchemaEvidence(),
            ),
            "rankintel_geo": EngineResult(engine_name="rankintel_geo", status="success", geo_aeo=GeoAeoEvidence()),
            "crawl4ai_browser": EngineResult(engine_name="crawl4ai_browser", status="success", on_page=OnPageEvidence(url="https://example.com")),
            "performance_engine": EngineResult(engine_name="performance_engine", status="success", performance=PerformanceEvidence()),
            "answerability_engine": EngineResult(engine_name="answerability_engine", status="success", answerability=ans_ev),
        }
        report = synthesizer.synthesize("https://example.com", engine_results)

        # Attach mock site_crawl
        report.site_crawl = SiteCrawlResult(
            completeness_status="CRAWL_COMPLETE",
            pages_crawled=1,
            answerability_intelligence=SiteAnswerabilityIntelligence(
                status="success",
                total_pages_evaluated=1,
                total_site_units_detected=2,
                pages_with_faq=["https://example.com"],
                facts=["Evaluated 1 page."],
            ),
        )

        md = MarkdownReporter.render(report)
        assert "## 💡 AI ANSWERABILITY & INFORMATION EXTRACTION" in md
        assert "### 📐 Structural Clarity Assessment:" in md
        assert "### 🎯 Concept Explanation vs Mention Matrix:" in md
        assert "### 💡 Site-Wide AI Answerability & Information Extraction" in md

    def test_json_serialization(self):
        synthesizer = IntelligenceSynthesizer()
        ans_ev = build_mock_answerability_evidence("https://example.com")
        engine_results = {
            "advertools_seo": EngineResult(
                engine_name="advertools_seo",
                status="success",
                on_page=OnPageEvidence(url="https://example.com", title="Title", meta_description="Desc"),
                robots=RobotsEvidence(found=True, is_allowed=True),
                schema_data=SchemaEvidence(),
            ),
            "rankintel_geo": EngineResult(engine_name="rankintel_geo", status="success", geo_aeo=GeoAeoEvidence()),
            "crawl4ai_browser": EngineResult(engine_name="crawl4ai_browser", status="success", on_page=OnPageEvidence(url="https://example.com")),
            "performance_engine": EngineResult(engine_name="performance_engine", status="success", performance=PerformanceEvidence()),
            "answerability_engine": EngineResult(engine_name="answerability_engine", status="success", answerability=ans_ev),
        }
        report = synthesizer.synthesize("https://example.com", engine_results)

        json_str = JsonReporter.render_audit(report)
        data = json.loads(json_str)
        assert "unified_answerability" in data
        assert data["unified_answerability"]["total_units_detected"] == 2


class TestCliAndMcpIntegration:
    """Verifies CLI table scorecard row and FastMCP tool outputs."""

    def test_cli_renders_answerability_scorecard_row(self):
        runner = CliRunner()
        ans_ev = build_mock_answerability_evidence("https://example.com")
        mock_report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-04",
            overall_health_score=85,
            geo_readiness_score=80,
            technical_health_score=90,
            unified_answerability=ans_ev,
        )

        with patch("rankintel.cli.EvidenceCollector") as mock_col_cls, \
             patch("rankintel.cli.IntelligenceSynthesizer") as mock_syn_cls, \
             patch("rankintel.cli.JsonReporter.save_audit"), \
             patch("rankintel.cli.MarkdownReporter.save", return_value="audits/test.md"):

            mock_syn_cls.return_value.synthesize.return_value = mock_report
            result = runner.invoke(main, ["audit", "https://example.com"])
            assert result.exit_code == 0
            assert "AI Answerability" in result.output
            assert "2 unit(s)" in result.output

    def test_mcp_rankintel_audit_returns_answerability_fields(self):
        ans_ev = build_mock_answerability_evidence("https://example.com")
        mock_report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-04",
            overall_health_score=85,
            geo_readiness_score=80,
            technical_health_score=90,
            unified_answerability=ans_ev,
        )

        with patch("rankintel.mcp.server.EvidenceCollector"), \
             patch("rankintel.mcp.server.IntelligenceSynthesizer") as mock_syn_cls:

            mock_syn_cls.return_value.synthesize.return_value = mock_report
            mcp_output = rankintel_audit("https://example.com")

            assert "answerability_units_detected" in mcp_output
            assert mcp_output["answerability_units_detected"] == 2
            assert mcp_output["answerability_explained_topics_count"] == 1
            assert mcp_output["answerability_clarity_qa_status"] == "PRESENT"
