"""
Evidence Provenance Tagger — Tracks the source engine, file origin,
confidence, and cross-engine confirmation/contradiction for each finding.
"""
from __future__ import annotations
from typing import Dict, List
from rankintel.models.schema import EngineResult, EvidenceProvenanceTag

class ProvenanceTagger:
    """Attaches source attribution and cross-engine agreement to key SEO/GEO/Trust findings."""

    @staticmethod
    def tag(engine_results: Dict[str, EngineResult]) -> List[EvidenceProvenanceTag]:
        tags: List[EvidenceProvenanceTag] = []
        seo = engine_results.get("advertools_seo")
        browser = engine_results.get("browser_engine")
        geo = engine_results.get("rankintel_geo")
        perf = engine_results.get("performance_engine")

        # 1. robots.txt findings
        if seo and seo.robots and seo.robots.found:
            for bot, status in seo.robots.bot_access.items():
                tags.append(EvidenceProvenanceTag(
                    finding=f"{bot}: {status.status}",
                    source_file="robots.txt",
                    engine="seo_engine",
                    evidence_snippet=f"User-agent: {bot} -> {status.status}",
                    confidence="high",
                    confirmed_by=[],
                    contradicted_by=[]
                ))

        # 2. Schema detection — cross-engine confirmation vs JS injection
        if seo and seo.schema_data and browser and browser.schema_data:
            static_types = set(seo.schema_data.detected_types)
            browser_types = set(browser.schema_data.detected_types)
            confirmed = sorted(list(static_types & browser_types))
            js_only = sorted(list(browser_types - static_types))

            for t in confirmed:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Schema type '{t}' detected",
                    source_file="application/ld+json",
                    engine="seo_engine",
                    confidence="high",
                    confirmed_by=["browser_engine"]
                ))
            for t in js_only:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Schema type '{t}' is JS-injected (invisible to static crawlers)",
                    source_file="DOM (JavaScript)",
                    engine="browser_engine",
                    confidence="high",
                    contradicted_by=["seo_engine"]
                ))
        elif seo and seo.schema_data:
            for t in seo.schema_data.detected_types:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Schema type '{t}' detected in raw HTML",
                    source_file="application/ld+json",
                    engine="seo_engine",
                    confidence="high"
                ))

        # 3. Heading and Title structure
        if seo and seo.on_page:
            tags.append(EvidenceProvenanceTag(
                finding=f"Page Title ({seo.on_page.title_length} chars): '{seo.on_page.title[:45]}...'",
                source_file="<title> tag",
                engine="seo_engine",
                confidence="high",
                confirmed_by=["browser_engine"] if (browser and browser.on_page and browser.on_page.title == seo.on_page.title) else []
            ))
            if browser and browser.on_page and browser.on_page.title and browser.on_page.title != seo.on_page.title:
                tags.append(EvidenceProvenanceTag(
                    finding=f"Rendered Title differs from Static Title",
                    source_file="DOM (hydration)",
                    engine="browser_engine",
                    confidence="high",
                    contradicted_by=["seo_engine"]
                ))

        # 4. TTFB & Performance Telemetry
        if perf and perf.performance:
            tags.append(EvidenceProvenanceTag(
                finding=f"TTFB Latency: {perf.performance.ttfb_ms:.0f}ms",
                source_file="HTTP response probe",
                engine="performance_engine",
                evidence_snippet=f"Telemetry Source: {perf.performance.source}",
                confidence="high" if perf.performance.source.startswith("pagespeed") else "medium"
            ))

        # 5. GEO & llms.txt provenance
        if geo and geo.geo_aeo:
            found = geo.geo_aeo.llms_txt_found
            tags.append(EvidenceProvenanceTag(
                finding=f"/llms.txt: {'PRESENT' if found else 'MISSING'}",
                source_file="/llms.txt HTTP check",
                engine="rankintel_geo",
                confidence="high"
            ))
            tags.append(EvidenceProvenanceTag(
                finding=f"Princeton GEO Citability: {geo.geo_aeo.overall_citability_score}/100",
                source_file="DOM content passages",
                engine="rankintel_geo",
                confidence="high"
            ))

        return tags
