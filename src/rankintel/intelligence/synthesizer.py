"""
Intelligence Synthesizer — Reconciles evidence from all engines,
computes holistic health scores, builds prioritized action plans, and generates fixes.
"""
from __future__ import annotations
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List

from rankintel.models.schema import (
    EngineResult,
    ConflictFinding,
    PrioritizedAction,
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence
)
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.intelligence.fixer import FixGenerator
from rankintel.references.quality_gates import META_LENGTH_BOUNDS, HEADING_HIERARCHY_RULES

class IntelligenceSynthesizer:
    """Synthesizes multi-engine findings into a single unified intelligence audit."""

    def __init__(self):
        self.conflict_detector = ConflictDetector()

    def synthesize(self, url: str, engine_results: Dict[str, EngineResult]) -> SynthesisReport:
        parsed = urlparse(url)
        domain = parsed.netloc
        timestamp = datetime.now().strftime("%Y-%m-%d")

        # Detect conflicts across engines
        conflicts = self.conflict_detector.detect(engine_results)

        # Reconcile Unified State (Prioritizing Browser DOM if available, otherwise static SEO)
        seo_res = engine_results.get("advertools_seo")
        browser_res = engine_results.get("browser_engine")
        geo_res = engine_results.get("rankintel_geo")

        # 1. OnPage Reconciliation
        if browser_res and browser_res.on_page and browser_res.on_page.status_code == 200:
            unified_on_page = browser_res.on_page
        elif seo_res and seo_res.on_page:
            unified_on_page = seo_res.on_page
        else:
            unified_on_page = OnPageEvidence(url=url)

        # 2. Robots Reconciliation (advertools is primary authority)
        if seo_res and seo_res.robots:
            unified_robots = seo_res.robots
        else:
            unified_robots = RobotsEvidence()

        # 3. Schema Reconciliation (Union of static + browser)
        all_schemas = set()
        validation_issues = []
        is_js_injected = False

        if seo_res and seo_res.schema_data:
            all_schemas.update(seo_res.schema_data.detected_types)
            validation_issues.extend(seo_res.schema_data.validation_issues)

        if browser_res and browser_res.schema_data:
            all_schemas.update(browser_res.schema_data.detected_types)
            validation_issues.extend(browser_res.schema_data.validation_issues)
            if any(c.category == "CLIENT_RENDERED_SCHEMA" for c in conflicts):
                is_js_injected = True

        unified_schema = SchemaEvidence(
            detected_types=list(all_schemas),
            blocks_count=len(all_schemas),
            is_injected_via_js=is_js_injected,
            validation_issues=list(set(validation_issues)),
            engine_source="triangulated_union"
        )

        # 4. GEO Reconciliation
        if geo_res and geo_res.geo_aeo:
            unified_geo = geo_res.geo_aeo
        else:
            unified_geo = GeoAeoEvidence()

        # Compute Categorical Scores
        tech_score = self._compute_technical_score(unified_on_page, unified_robots, unified_schema)
        geo_score = unified_geo.overall_citability_score or 40
        overall_health = int(round((tech_score * 0.55) + (geo_score * 0.45)))

        # Build Prioritized Actions
        actions = self._build_prioritized_actions(
            unified_on_page, unified_robots, unified_schema, unified_geo, conflicts
        )

        # Generate Production Fixes
        meta_fixes = FixGenerator.generate_meta_fixes(unified_on_page, domain)
        jsonld_fix = FixGenerator.generate_jsonld_schema(url, domain, unified_on_page)
        llms_fix = FixGenerator.generate_llms_txt(domain, url, unified_on_page, unified_geo)
        robots_fix = FixGenerator.generate_hardened_robots_txt()

        fixes = {
            **meta_fixes,
            "jsonld_schema": jsonld_fix,
            "llms_txt": llms_fix,
            "hardened_robots": robots_fix
        }

        return SynthesisReport(
            url=url,
            domain=domain,
            timestamp=timestamp,
            overall_health_score=overall_health,
            geo_readiness_score=geo_score,
            technical_health_score=tech_score,
            engines_executed=[k for k, v in engine_results.items() if v.status == "success"],
            conflicts_detected=conflicts,
            prioritized_actions=actions,
            unified_on_page=unified_on_page,
            unified_robots=unified_robots,
            unified_schema=unified_schema,
            unified_geo=unified_geo,
            fixes=fixes
        )

    def _compute_technical_score(
        self, on_page: OnPageEvidence, robots: RobotsEvidence, schema: SchemaEvidence
    ) -> int:
        score = 100

        # Title checks
        if on_page.title_length < META_LENGTH_BOUNDS["title_min"] or on_page.title_length > META_LENGTH_BOUNDS["title_max"]:
            score -= 10
        if not on_page.title:
            score -= 25

        # Description checks
        if on_page.meta_desc_length < META_LENGTH_BOUNDS["desc_min"] or on_page.meta_desc_length > META_LENGTH_BOUNDS["desc_max"]:
            score -= 10
        if not on_page.meta_description:
            score -= 20

        # H1 checks
        if on_page.h1_count != 1:
            score -= 15

        # Image alt checks
        if on_page.total_images > 0:
            alt_ratio = on_page.images_with_alt / on_page.total_images
            if alt_ratio < 0.8:
                score -= 10

        # Schema checks
        if not schema.detected_types:
            score -= 20

        return max(score, 10)

    def _build_prioritized_actions(
        self,
        on_page: OnPageEvidence,
        robots: RobotsEvidence,
        schema: SchemaEvidence,
        geo: GeoAeoEvidence,
        conflicts: List[ConflictFinding]
    ) -> List[PrioritizedAction]:
        actions: List[PrioritizedAction] = []

        # High/Critical Conflicts first
        for c in conflicts:
            if c.severity in ("HIGH", "CRITICAL"):
                actions.append(PrioritizedAction(
                    level="CRITICAL",
                    title=f"Resolve Triangulation Conflict: {c.feature}",
                    finding=c.description,
                    rationale=c.interpretation,
                    engine_confidence="VERY HIGH (Cross-engine divergence)"
                ))

        # Title issues
        if on_page.title_length > 65 or on_page.title_length < 30:
            actions.append(PrioritizedAction(
                level="HIGH",
                title="Optimize Title Tag Length & CTR Hook",
                finding=f"Current title is {on_page.title_length} characters.",
                rationale="Titles over 60 chars are truncated in SERPs with ellipses. Target 50-60 chars with primary keyword front-loaded.",
                engine_confidence="HIGH (Deterministic measurement)"
            ))

        # Description issues
        if on_page.meta_desc_length > 165 or on_page.meta_desc_length < 110:
            actions.append(PrioritizedAction(
                level="HIGH",
                title="Rewrite Meta Description with Active Call-to-Action",
                finding=f"Current description is {on_page.meta_desc_length} characters.",
                rationale="Descriptions over 160 chars are clipped. Overly short descriptions fail to compel searcher clicks.",
                engine_confidence="HIGH (Deterministic measurement)"
            ))

        # H1 tags
        if on_page.h1_count > 1:
            actions.append(PrioritizedAction(
                level="HIGH",
                title="Consolidate Multiple H1 Headings into Single Logical H1",
                finding=f"Found {on_page.h1_count} H1 tags on page.",
                rationale="Multiple H1 tags dilute topical focus. Best practice is a single clear H1 reflecting page intent.",
                engine_confidence="HIGH"
            ))
        elif on_page.h1_count == 0:
            actions.append(PrioritizedAction(
                level="CRITICAL",
                title="Add Missing H1 Heading",
                finding="Zero H1 tags detected.",
                rationale="Search engines depend on H1 for primary topical categorization.",
                engine_confidence="HIGH"
            ))

        # Schema Markup
        if not schema.detected_types:
            actions.append(PrioritizedAction(
                level="CRITICAL",
                title="Deploy JSON-LD Structured Data",
                finding="Zero Schema.org types detected on page.",
                rationale="Structured data is required for rich snippets and assists generative AI models in entity disambiguation.",
                engine_confidence="HIGH (Verified by both static and browser engines)"
            ))

        # GEO llms.txt
        if not geo.llms_txt_found:
            actions.append(PrioritizedAction(
                level="GEO_WIN",
                title="Publish Standard /llms.txt AI Agent Manifest",
                finding="/llms.txt is missing from root domain.",
                rationale="Provides AI assistants (ChatGPT, Claude, Perplexity) with clean, curated markdown documentation.",
                engine_confidence="HIGH"
            ))

        # GEO Citability
        if geo.answer_first_ratio < 0.3:
            actions.append(PrioritizedAction(
                level="GEO_WIN",
                title="Implement Answer-First H2 Structure",
                finding=f"Only {int(geo.answer_first_ratio * 100)}% of H2 sections open with direct factual answers.",
                rationale="AutoGEO research proves AI models prioritize passages providing concrete numbers/facts in the first 150 characters.",
                engine_confidence="MEDIUM (Heuristic NLP)"
            ))

        return actions
