"""
Phase 11.1 — Benchmark Intelligence Collection Models.
Defines structured, provenance-preserving evidence packages and dimensions
across the permanent 11-site benchmark.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BenchmarkDimensionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"
    DISABLED = "DISABLED"


# ── 15 Benchmark Dimensions ──────────────────────────────────────────────────

class CrawlDiscoveryDimension(BaseModel):
    """Dimension 1: Crawl and discovery evidence."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    url: str = ""
    http_status_code: int = 0
    is_redirect: bool = False
    canonical_url: Optional[str] = None
    internal_links_count: int = 0
    external_links_count: int = 0
    robots_txt_found: bool = False
    robots_txt_url: str = ""
    sitemaps_declared: List[str] = Field(default_factory=list)
    crawl_limitations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class TechnicalSeoDimension(BaseModel):
    """Dimension 2: Technical SEO foundation."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    h1_count: int = 0
    h1_samples: List[str] = Field(default_factory=list)
    h2_count: int = 0
    h3_count: int = 0
    detected_schema_types: List[str] = Field(default_factory=list)
    schema_blocks_count: int = 0
    schema_validation_issues: List[str] = Field(default_factory=list)
    ttfb_ms: float = 0.0
    performance_score: int = 0
    performance_source: str = "local_probe"
    notes: List[str] = Field(default_factory=list)


class AccessibilityDimension(BaseModel):
    """Dimension 3: Automated WCAG accessibility checks."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    wcag_status: str = "UNKNOWN"
    engine_source: str = "accessibility_engine"
    browser_evaluated: bool = False
    total_violations: int = 0
    critical_count: int = 0
    serious_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    rules_checked_count: int = 0
    rules_passed_count: int = 0
    violation_samples: List[Dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = "Automated checks evaluate observable criteria; non-certification scope."
    notes: List[str] = Field(default_factory=list)


class SecurityDimension(BaseModel):
    """Dimension 4: Security and transport layer intelligence."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    overall_status: str = "UNKNOWN"
    is_https: bool = False
    tls_valid: Optional[bool] = None
    tls_protocol: Optional[str] = None
    tls_days_remaining: Optional[int] = None
    hsts_present: bool = False
    hsts_preload: bool = False
    csp_present: bool = False
    x_frame_options: Optional[str] = None
    x_content_type_options: Optional[str] = None
    referrer_policy: Optional[str] = None
    mixed_content_count: int = 0
    server_leakage: List[str] = Field(default_factory=list)
    findings_count: int = 0
    findings_samples: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ContentDimension(BaseModel):
    """Dimension 5: Content intelligence and structural depth."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    main_content_words: int = 0
    total_body_words: int = 0
    content_to_boilerplate_ratio: float = 0.0
    paragraph_count: int = 0
    extraction_method: str = "UNAVAILABLE"
    thin_content_tier: str = "UNAVAILABLE"
    has_placeholder_text: bool = False
    exact_content_hash: str = ""
    simhash: str = ""
    title_h1_alignment: str = "UNAVAILABLE"
    title_h1_token_overlap: float = 0.0
    heading_hierarchy_valid: bool = True
    heading_skips: List[str] = Field(default_factory=list)
    empty_sections_count: int = 0
    notes: List[str] = Field(default_factory=list)


class EntityDimension(BaseModel):
    """Dimension 6: Entity intelligence and declarations."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_entities_detected: int = 0
    entity_names: List[str] = Field(default_factory=list)
    entity_types_detected: List[str] = Field(default_factory=list)
    relationships_count: int = 0
    structured_vs_visible_comparisons_count: int = 0
    aligned_comparisons_count: int = 0
    divergent_comparisons_count: int = 0
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class InternalLinkDimension(BaseModel):
    """Dimension 7: Internal and navigation link intelligence."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_internal_links: int = 0
    unique_internal_targets: int = 0
    total_external_links: int = 0
    unique_external_targets: int = 0
    empty_anchors_count: int = 0
    sample_internal_targets: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class SearchTopicQueryIntentDimension(BaseModel):
    """Dimension 8: Search signals, topics, query mapping, and intent."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    search_signals_count: int = 0
    topics_detected_count: int = 0
    topics_sample: List[str] = Field(default_factory=list)
    query_page_concepts_count: int = 0
    primary_intent: str = "INFORMATIONAL"
    secondary_intents: List[str] = Field(default_factory=list)
    intent_evidence_items_count: int = 0
    notes: List[str] = Field(default_factory=list)


class CannibalizationSearchGapDimension(BaseModel):
    """Dimension 9: Cannibalization signals and observable topic gaps."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    potential_cannibalization_signals_count: int = 0
    observable_gaps_count: int = 0
    overlap_signals_sample: List[Dict[str, Any]] = Field(default_factory=list)
    gaps_sample: List[Dict[str, Any]] = Field(default_factory=list)
    layer_boundary_note: str = (
        "Strictly deterministic identification of observable on-site topic overlaps and gaps. "
        "No external ranking, GSC, or competitor superiority claims."
    )
    notes: List[str] = Field(default_factory=list)


class RetrievalReadinessDimension(BaseModel):
    """Dimension 10: AI retrieval and crawler access readiness."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_bots_evaluated: int = 12
    search_index_allowed_count: int = 0
    ai_training_allowed_count: int = 0
    user_fetch_allowed_count: int = 0
    waf_or_challenge_detected: bool = False
    waf_blocked: bool = False
    waf_provider: Optional[str] = None
    has_nosnippet: bool = False
    has_data_nosnippet: bool = False
    max_snippet: Optional[int] = None
    static_words: int = 0
    rendered_words: int = 0
    word_count_delta: int = 0
    rendering_impact_summary: str = ""
    notes: List[str] = Field(default_factory=list)


class AnswerabilityDimension(BaseModel):
    """Dimension 11: AI answerability and structured information units."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_units_detected: int = 0
    units_by_type: Dict[str, int] = Field(default_factory=dict)
    heading_content_relationship: str = "UNKNOWN"
    question_answer_patterns: str = "UNKNOWN"
    definition_patterns: str = "UNKNOWN"
    step_list_structure: str = "UNKNOWN"
    table_availability: str = "UNKNOWN"
    explained_topics_count: int = 0
    mentioned_only_topics_count: int = 0
    unsupported_heading_topics_count: int = 0
    unsupported_headings_sample: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ClaimGroundingDimension(BaseModel):
    """Dimension 12: Claim grounding and multi-surface consistency."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_claims_detected: int = 0
    supported_claims_count: int = 0
    partially_supported_count: int = 0
    uncorroborated_count: int = 0
    contradicted_count: int = 0
    structured_agreements_count: int = 0
    structured_disagreements_count: int = 0
    entity_consistency_breakdown: Dict[str, int] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class MultimodalDimension(BaseModel):
    """Dimension 13: Multimodal asset readiness."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_visual_assets: int = 0
    informational_assets_count: int = 0
    decorative_assets_count: int = 0
    alt_represented_count: int = 0
    caption_represented_count: int = 0
    text_represented_count: int = 0
    visual_only_observed_gaps: int = 0
    modern_format_count: int = 0
    missing_dimensions_count: int = 0
    notes: List[str] = Field(default_factory=list)


class AgentReadinessDimension(BaseModel):
    """Dimension 14: Agent action surfaces and access paths."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.AVAILABLE
    total_forms_detected: int = 0
    labeled_forms_count: int = 0
    action_buttons_detected: int = 0
    meaningful_accessible_buttons_count: int = 0
    descriptive_navigation_links_count: int = 0
    schema_actions_detected: int = 0
    webmcp_declarations_detected: int = 0
    total_access_paths: int = 0
    action_surface_gaps: int = 0
    notes: List[str] = Field(default_factory=list)


class ExternalAiDimension(BaseModel):
    """Dimension 15: Controlled external AI visibility observations."""
    status: BenchmarkDimensionStatus = BenchmarkDimensionStatus.DISABLED
    providers_evaluated: List[str] = Field(default_factory=list)
    queries_executed_count: int = 0
    successful_observations_count: int = 0
    failed_observations_count: int = 0
    target_domain_cited_count: int = 0
    target_domain_mentioned_count: int = 0
    total_external_citations: int = 0
    failure_reason: Optional[str] = None
    limitation_disclaimer: str = (
        "Controlled empirical observations under explicit API configurations. "
        "Strictly opt-in; does not imply universal AI rankings or traffic."
    )
    notes: List[str] = Field(default_factory=list)


# ── Epistemic Separation Container ───────────────────────────────────────────

class EpistemicSeparation(BaseModel):
    """Strictly partitioned epistemic categories for website findings."""
    facts: List[str] = Field(default_factory=list)
    external_observations: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


# ── Structured Package Per Website ───────────────────────────────────────────

class SiteIntelligencePackage(BaseModel):
    """Structured, provenance-preserving intelligence package for a single benchmark site."""
    site_url: str
    domain: str
    name: str = ""
    role: str = "competitor"  # "competitor" or "target" / "sunrise"
    collection_timestamp: str
    collection_status: str = "SUCCESS"  # "SUCCESS", "PARTIAL", "FAILED"
    error_message: Optional[str] = None
    execution_time_sec: float = 0.0
    
    # Invariant health scores
    overall_health_score: int = 0
    technical_health_score: int = 0
    geo_readiness_score: int = 0
    trust_score: int = 0
    performance_score: int = 0
    score_formula_mode: str = "4_engine"
    formula_invariance_verified: bool = True
    
    # Environmental / crawl limits
    crawl_limitations: List[str] = Field(default_factory=list)

    # 15 Normalized Dimensions
    crawl_discovery: CrawlDiscoveryDimension = Field(default_factory=CrawlDiscoveryDimension)
    technical_seo: TechnicalSeoDimension = Field(default_factory=TechnicalSeoDimension)
    accessibility: AccessibilityDimension = Field(default_factory=AccessibilityDimension)
    security: SecurityDimension = Field(default_factory=SecurityDimension)
    content: ContentDimension = Field(default_factory=ContentDimension)
    entity: EntityDimension = Field(default_factory=EntityDimension)
    internal_links: InternalLinkDimension = Field(default_factory=InternalLinkDimension)
    search_topic_query_intent: SearchTopicQueryIntentDimension = Field(default_factory=SearchTopicQueryIntentDimension)
    cannibalization_search_gaps: CannibalizationSearchGapDimension = Field(default_factory=CannibalizationSearchGapDimension)
    retrieval_readiness: RetrievalReadinessDimension = Field(default_factory=RetrievalReadinessDimension)
    answerability: AnswerabilityDimension = Field(default_factory=AnswerabilityDimension)
    claim_grounding: ClaimGroundingDimension = Field(default_factory=ClaimGroundingDimension)
    multimodal: MultimodalDimension = Field(default_factory=MultimodalDimension)
    agent_readiness: AgentReadinessDimension = Field(default_factory=AgentReadinessDimension)
    external_ai: ExternalAiDimension = Field(default_factory=ExternalAiDimension)

    # Epistemic segregation
    epistemic_separation: EpistemicSeparation = Field(default_factory=EpistemicSeparation)

    # Provenance and cross-engine telemetry
    provenance_tags: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts_detected: List[Dict[str, Any]] = Field(default_factory=list)
    engines_executed: List[str] = Field(default_factory=list)
    raw_report_paths: Dict[str, str] = Field(default_factory=dict)


# ── Aggregate Benchmark Dataset ──────────────────────────────────────────────

class BenchmarkCollectionDataset(BaseModel):
    """Aggregate dataset collecting all benchmark site intelligence packages."""
    benchmark_version: str = "11.1"
    created_at: str
    wall_clock_sec: float = 0.0
    workers_used: int = 1
    total_sites: int = 11
    sites_succeeded: int = 0
    sites_partial: int = 0
    sites_failed: int = 0
    sites_list: List[str] = Field(default_factory=list)
    packages: Dict[str, SiteIntelligencePackage] = Field(default_factory=dict)
    summary_matrix: List[Dict[str, Any]] = Field(default_factory=list)
