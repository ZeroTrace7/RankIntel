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
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
    CloudIntelligenceEvidence,
    ImageSEOEvidence,
    AccessibilityEvidence,
    SecurityEvidence,
    SecurityStatus,
    WcagStatus,
    SecuritySeverity,
    AccessibilitySeverity
)
from rankintel.evidence.conflicts import ConflictDetector
from rankintel.evidence.provenance import ProvenanceTagger
from rankintel.intelligence.fixer import FixGenerator
from rankintel.references.quality_gates import META_LENGTH_BOUNDS, HEADING_HIERARCHY_RULES
from rankintel.analyzers.trust_evaluator import TrustEvaluator

class IntelligenceSynthesizer:
    """Synthesizes multi-engine findings into a single unified intelligence audit."""

    def __init__(self):
        self.conflict_detector = ConflictDetector()

    def synthesize(self, url: str, engine_results: Dict[str, EngineResult]) -> SynthesisReport:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        parsed = urlparse(url)
        domain = parsed.netloc
        timestamp = datetime.now().strftime("%Y-%m-%d")

        # Detect conflicts across engines
        conflicts = self.conflict_detector.detect(engine_results)

        # Build evidence provenance chain
        provenance = ProvenanceTagger.tag(engine_results)

        # Reconcile Unified State (Prioritizing Browser DOM if available, otherwise static SEO)
        seo_res = engine_results.get("advertools_seo")
        browser_res = engine_results.get("browser_engine")
        geo_res = engine_results.get("rankintel_geo")
        perf_res = engine_results.get("performance_engine")

        # 1. OnPage Reconciliation
        if browser_res and browser_res.on_page and browser_res.on_page.status_code == 200:
            unified_on_page = browser_res.on_page
            # Merge response headers, links, title, description, and canonical if static SEO had them
            if seo_res and seo_res.on_page:
                if not unified_on_page.title and seo_res.on_page.title:
                    unified_on_page.title = seo_res.on_page.title
                    unified_on_page.title_length = seo_res.on_page.title_length
                if not unified_on_page.meta_description and seo_res.on_page.meta_description:
                    unified_on_page.meta_description = seo_res.on_page.meta_description
                    unified_on_page.meta_desc_length = seo_res.on_page.meta_desc_length
                if not unified_on_page.canonical_url and seo_res.on_page.canonical_url:
                    unified_on_page.canonical_url = seo_res.on_page.canonical_url
                if not unified_on_page.response_headers and seo_res.on_page.response_headers:
                    unified_on_page.response_headers = seo_res.on_page.response_headers
                if not unified_on_page.internal_links and seo_res.on_page.internal_links:
                    unified_on_page.internal_links = seo_res.on_page.internal_links
                if not unified_on_page.external_links and seo_res.on_page.external_links:
                    unified_on_page.external_links = seo_res.on_page.external_links
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
        sameas_urls = set()
        has_org = False
        has_author = False
        is_js_injected = False

        if seo_res and seo_res.schema_data:
            all_schemas.update(seo_res.schema_data.detected_types)
            validation_issues.extend(seo_res.schema_data.validation_issues)
            sameas_urls.update(seo_res.schema_data.sameas_urls)
            has_org = has_org or seo_res.schema_data.has_organization
            has_author = has_author or seo_res.schema_data.has_author

        if browser_res and browser_res.schema_data:
            all_schemas.update(browser_res.schema_data.detected_types)
            validation_issues.extend(browser_res.schema_data.validation_issues)
            sameas_urls.update(browser_res.schema_data.sameas_urls)
            has_org = has_org or browser_res.schema_data.has_organization
            has_author = has_author or browser_res.schema_data.has_author
            if any(c.category == "CLIENT_RENDERED_SCHEMA" for c in conflicts):
                is_js_injected = True

        unified_schema = SchemaEvidence(
            detected_types=list(all_schemas),
            deprecated_types_detected=[s for s in all_schemas if s in ["FAQPage", "SpecialAnnouncement"]],
            blocks_count=len(all_schemas),
            is_injected_via_js=is_js_injected,
            validation_issues=list(set(validation_issues)),
            sameas_urls=list(sameas_urls),
            has_organization=has_org,
            has_author=has_author,
            engine_source="triangulated_union"
        )

        # 4. GEO Reconciliation
        if geo_res and geo_res.geo_aeo:
            unified_geo = geo_res.geo_aeo
        else:
            unified_geo = GeoAeoEvidence()

        # 5. Trust Stack Reconciliation — pass raw_html so soup is no longer None
        browser_res = engine_results.get("browser_engine")
        _raw_html = browser_res.raw_html if browser_res else None
        unified_trust = TrustEvaluator.evaluate(
            url=url,
            on_page=unified_on_page,
            schema=unified_schema,
            geo=unified_geo,
            raw_html=_raw_html,
        )


        # 6. Performance Telemetry Reconciliation
        if perf_res and perf_res.performance:
            unified_performance = perf_res.performance
        else:
            unified_performance = PerformanceEvidence(
                overall_performance_score=0,
                source="unavailable",
                notes=["Performance engine did not execute — score excluded from holistic formula."],
            )


        # 7. Cloud Intelligence Reconciliation (OpenSEO MCP)
        cloud_res = engine_results.get("mcp_cloud")
        cloud_intelligence = (
            cloud_res.cloud_intelligence
            if cloud_res and cloud_res.cloud_intelligence
            else CloudIntelligenceEvidence()
        )

        keyword_score = 0
        if cloud_intelligence.available and cloud_intelligence.keywords:
            traffic = cloud_intelligence.keywords.estimated_monthly_traffic
            if traffic >= 100_000:
                keyword_score = 95
            elif traffic >= 25_000:
                keyword_score = 80
            elif traffic >= 5_000:
                keyword_score = 65
            elif traffic >= 500:
                keyword_score = 50
            else:
                keyword_score = 35

        # Compute Holistic Health Score
        tech_score = self._compute_technical_score(unified_on_page, unified_robots, unified_schema)
        geo_score = (
            unified_geo.overall_citability_score
            if (geo_res and geo_res.status == "success")
            else 40  # Default only when GEO engine didn't execute
        )
        trust_score = unified_trust.overall_score
        perf_score = unified_performance.overall_performance_score
        perf_available = unified_performance.source != "unavailable"

        # Holistic Triangulated Score — formula depends on which engines ran:
        if cloud_intelligence.available and keyword_score > 0:
            # 5-Engine Formula: Tech 30% | GEO 25% | Trust 20% | Perf 15% | Keyword 10%
            formula_mode = "5_engine"
            if perf_available:
                overall_health = int(round(
                    (tech_score * 0.30) + (geo_score * 0.25) +
                    (trust_score * 0.20) + (perf_score * 0.15) + (keyword_score * 0.10)
                ))
            else:
                # Redistribute perf weight across remaining components
                formula_mode = "4_engine"
                overall_health = int(round(
                    (tech_score * 0.35) + (geo_score * 0.30) +
                    (trust_score * 0.25) + (keyword_score * 0.10)
                ))
        elif perf_available:
            # Standard 4-Engine Formula: Tech 35% | GEO 30% | Trust 20% | Perf 15%
            formula_mode = "4_engine"
            overall_health = int(round(
                (tech_score * 0.35) + (geo_score * 0.30) +
                (trust_score * 0.20) + (perf_score * 0.15)
            ))
        else:
            # 3-Engine Formula (no performance): Tech 44% | GEO 37% | Trust 19%
            formula_mode = "3_engine"
            overall_health = int(round(
                (tech_score * 0.44) + (geo_score * 0.37) + (trust_score * 0.19)
            ))

        # Build Prioritized Actions
        actions = self._build_prioritized_actions(
            unified_on_page, unified_robots, unified_schema, unified_geo, unified_trust, unified_performance, conflicts
        )

        # Generate Production Fixes — only when genuinely needed
        meta_fixes = FixGenerator.generate_meta_fixes(unified_on_page, domain)
        jsonld_fix = FixGenerator.generate_jsonld_schema(url, domain, unified_on_page, unified_schema)
        llms_fix = FixGenerator.generate_llms_txt(domain, url, unified_on_page, unified_geo)
        robots_fix = FixGenerator.generate_hardened_robots_txt()

        fixes: dict = {**meta_fixes}
        if jsonld_fix:
            fixes["jsonld_schema"] = jsonld_fix
        if llms_fix:
            fixes["llms_txt"] = llms_fix
        if robots_fix:
            fixes["hardened_robots"] = robots_fix

        return SynthesisReport(
            url=url,
            domain=domain,
            timestamp=timestamp,
            overall_health_score=overall_health,
            geo_readiness_score=geo_score,
            technical_health_score=tech_score,
            trust_score=trust_score,
            performance_score=perf_score,
            keyword_score=keyword_score,
            score_formula_mode=formula_mode,
            engines_executed=[k for k, v in engine_results.items() if v.status == "success"],
            conflicts_detected=conflicts,
            prioritized_actions=actions,
            provenance=provenance,
            unified_on_page=unified_on_page,
            unified_robots=unified_robots,
            unified_schema=unified_schema,
            unified_geo=unified_geo,
            unified_trust=unified_trust,
            unified_performance=unified_performance,
            cloud_intelligence=cloud_intelligence,
            fixes=fixes
        )

    def _compute_technical_score(
        self, on_page: OnPageEvidence, robots: RobotsEvidence, schema: SchemaEvidence
    ) -> int:
        score = 100

        # Title checks — mutually exclusive: absence OR wrong length, never both
        if not on_page.title:
            score -= 25
        elif on_page.title_length < META_LENGTH_BOUNDS["title_min"] or on_page.title_length > META_LENGTH_BOUNDS["title_max"]:
            score -= 10

        # Description checks — mutually exclusive: absence OR wrong length, never both
        if not on_page.meta_description:
            score -= 20
        elif on_page.meta_desc_length < META_LENGTH_BOUNDS["desc_min"] or on_page.meta_desc_length > META_LENGTH_BOUNDS["desc_max"]:
            score -= 10

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
        trust: TrustStackResult,
        perf: PerformanceEvidence,
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

        # Trust Stack: Missing Security Headers
        tech_layer = trust.layers.get("technical")
        if tech_layer and tech_layer.signals_missing:
            actions.append(PrioritizedAction(
                level="HIGH",
                title="Harden Technical Trust & Security Headers",
                finding=", ".join(tech_layer.signals_missing),
                rationale="HSTS and Content-Security-Policy prevent security downgrades and satisfy AI agent reliability gates.",
                engine_confidence="HIGH (Header telemetry)"
            ))

        # Trust Stack: Identity & Organization
        ident_layer = trust.layers.get("identity")
        if ident_layer and not schema.has_organization:
            actions.append(PrioritizedAction(
                level="HIGH",
                title="Add Organization Schema & Entity Anchors",
                finding="No Organization / LocalBusiness entity defined in structured data.",
                rationale="Essential for establishing E-E-A-T and anchoring your entity in Google's Knowledge Graph.",
                engine_confidence="HIGH"
            ))

        # Performance / Latency
        if perf.ttfb_ms > 1200:
            actions.append(PrioritizedAction(
                level="HIGH",
                title="Reduce Server Latency (TTFB)",
                finding=f"Time to First Byte is {perf.ttfb_ms:.0f}ms (threshold is 800ms).",
                rationale="High TTFB delays page hydration, crawler budget efficiency, and hurts user interaction metrics.",
                engine_confidence="HIGH"
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
