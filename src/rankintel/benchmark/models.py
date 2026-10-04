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


# ── Phase 11.2 Website Intelligence Review Models ─────────────────────────────

class ReviewDimensionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"
    DISABLED = "DISABLED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ObservableBusinessProfile(BaseModel):
    """Observable company branding, declared name, and business nature."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    business_name: str = ""
    legal_name: Optional[str] = None
    branding_title: str = ""
    meta_description_summary: str = ""
    business_nature_summary: str = ""
    primary_industry_domain: str = ""
    evidence_sources: List[str] = Field(default_factory=list)
    confidence: str = "high"


class EntityProfile(BaseModel):
    """Named entities, organization identifiers, and multi-surface alignment."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    total_entities_detected: int = 0
    entity_types_detected: List[str] = Field(default_factory=list)
    named_entities: List[str] = Field(default_factory=list)
    relationships_count: int = 0
    structured_vs_visible_comparisons: int = 0
    aligned_comparisons: int = 0
    divergent_comparisons: int = 0
    entity_alignment_summary: str = ""
    samples: List[Dict[str, Any]] = Field(default_factory=list)


class ServiceProductProfile(BaseModel):
    """Observable services, products, and core capabilities evidenced on-site."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    services_observed: List[str] = Field(default_factory=list)
    product_offerings: List[str] = Field(default_factory=list)
    service_descriptions_count: int = 0
    structured_units_count: int = 0
    evidence_sources: List[str] = Field(default_factory=list)
    summary: str = ""


class TopicTaxonomyProfile(BaseModel):
    """Primary and supporting topics identified deterministically on-site."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    total_topics_detected: int = 0
    primary_topics: List[str] = Field(default_factory=list)
    supporting_topics: List[str] = Field(default_factory=list)
    topics_sample: List[str] = Field(default_factory=list)
    dominant_concepts: List[str] = Field(default_factory=list)
    summary: str = ""


class SearchIntentProfile(BaseModel):
    """Observable search intent classification supported by structural evidence."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    primary_intent: str = "INFORMATIONAL"
    secondary_intents: List[str] = Field(default_factory=list)
    intent_evidence_count: int = 0
    intent_evidence_summary: str = ""


class TopicDistributionProfile(BaseModel):
    """Concept-to-page distribution and structural topical depth."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    direct_primary_concepts_count: int = 0
    secondary_supported_concepts_count: int = 0
    query_page_concepts_count: int = 0
    total_words: int = 0
    paragraphs_count: int = 0
    explained_topics_count: int = 0
    mentioned_only_topics_count: int = 0
    concept_density_per_100_words: float = 0.0
    summary: str = ""


class PageTopicConcentrationProfile(BaseModel):
    """Topical concentration, cannibalization risk, and heading alignment."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    content_to_boilerplate_ratio: float = 0.0
    title_h1_alignment: str = "UNAVAILABLE"
    title_h1_token_overlap: float = 0.0
    heading_hierarchy_valid: bool = True
    heading_skips: List[str] = Field(default_factory=list)
    empty_sections_count: int = 0
    potential_cannibalization_signals_count: int = 0
    observable_gaps_count: int = 0
    concentration_summary: str = ""
    layer_boundary_note: str = ""


class TechnicalSeoReviewProfile(BaseModel):
    """Technical SEO foundation, indexability, metadata, and performance."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    title: str = ""
    title_length: int = 0
    title_status: str = "NORMAL"
    meta_description: str = ""
    meta_description_length: int = 0
    meta_desc_status: str = "NORMAL"
    h1_count: int = 0
    h1_samples: List[str] = Field(default_factory=list)
    h2_count: int = 0
    h3_count: int = 0
    schema_types: List[str] = Field(default_factory=list)
    schema_blocks_count: int = 0
    schema_validation_issues: List[str] = Field(default_factory=list)
    canonical_url: Optional[str] = None
    canonical_status: str = "MATCHING"
    robots_txt_found: bool = False
    sitemaps_declared: List[str] = Field(default_factory=list)
    ttfb_ms: float = 0.0
    performance_score: int = 0
    performance_source: str = "local_probe"
    summary: str = ""


class AccessibilitySecurityProfile(BaseModel):
    """Automated WCAG 2.1 checks and transport/header security posture."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    wcag_status: str = "UNKNOWN"
    total_accessibility_violations: int = 0
    critical_violations: int = 0
    serious_violations: int = 0
    rules_checked_count: int = 0
    rules_passed_count: int = 0
    a11y_disclaimer: str = "Automated checks evaluate observable criteria; non-certification scope."
    security_status: str = "UNKNOWN"
    is_https: bool = False
    tls_valid: Optional[bool] = None
    tls_protocol: Optional[str] = None
    tls_days_remaining: Optional[int] = None
    hsts_present: bool = False
    csp_present: bool = False
    x_frame_options: Optional[str] = None
    x_content_type_options: Optional[str] = None
    referrer_policy: Optional[str] = None
    mixed_content_count: int = 0
    server_leakage: List[str] = Field(default_factory=list)
    security_findings_count: int = 0
    summary: str = ""


class InternalLinkStructureProfile(BaseModel):
    """Internal navigation topology and link architecture."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    total_internal_links: int = 0
    unique_internal_targets: int = 0
    total_external_links: int = 0
    unique_external_targets: int = 0
    empty_anchors_count: int = 0
    sample_internal_targets: List[str] = Field(default_factory=list)
    link_density_ratio: float = 0.0
    summary: str = ""


class RetrievalReadinessProfile(BaseModel):
    """Search/AI crawler access matrix, WAF status, and rendering delta."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
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
    llms_txt_present: bool = False
    geo_score: int = 0
    summary: str = ""


class AnswerabilityReviewProfile(BaseModel):
    """Structured information units and factual explanation coverage."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
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
    summary: str = ""


class ClaimGroundingReviewProfile(BaseModel):
    """Claim extraction, on-site support verification, and schema consistency."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    total_claims_detected: int = 0
    supported_claims_count: int = 0
    partially_supported_count: int = 0
    uncorroborated_count: int = 0
    contradicted_count: int = 0
    structured_agreements_count: int = 0
    structured_disagreements_count: int = 0
    entity_consistency_breakdown: Dict[str, int] = Field(default_factory=dict)
    grounding_ratio: float = 0.0
    summary: str = ""


class MultimodalReviewProfile(BaseModel):
    """Visual asset analysis, text/alt fallbacks, and layout shift risks."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    total_visual_assets: int = 0
    informational_assets_count: int = 0
    decorative_assets_count: int = 0
    alt_represented_count: int = 0
    caption_represented_count: int = 0
    text_represented_count: int = 0
    visual_only_observed_gaps: int = 0
    modern_format_count: int = 0
    missing_dimensions_count: int = 0
    alt_coverage_ratio: float = 0.0
    summary: str = ""


class AgentReadinessReviewProfile(BaseModel):
    """Autonomous agent action surfaces, form labels, and access paths."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    total_forms_detected: int = 0
    labeled_forms_count: int = 0
    action_buttons_detected: int = 0
    meaningful_accessible_buttons_count: int = 0
    descriptive_navigation_links_count: int = 0
    schema_actions_detected: int = 0
    webmcp_declarations_detected: int = 0
    total_access_paths: int = 0
    action_surface_gaps: int = 0
    summary: str = ""


class ExternalAiReviewProfile(BaseModel):
    """Controlled external AI visibility observations."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.DISABLED
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
    summary: str = ""


class EvidenceLimitationsProfile(BaseModel):
    """Explicit evidence boundaries, crawl limits, uncertainty, and conflicts."""
    status: ReviewDimensionStatus = ReviewDimensionStatus.AVAILABLE
    crawl_limitations: List[str] = Field(default_factory=list)
    dimension_statuses: Dict[str, str] = Field(default_factory=dict)
    cross_engine_conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    summary: str = ""


class WebsiteIntelligenceReview(BaseModel):
    """Structured, reusable Website Intelligence Review representing synthesized website understanding."""
    domain: str
    site_url: str
    name: str = ""
    role: str = "competitor"
    collection_timestamp: str
    review_timestamp: str
    
    # Invariant health scores (strictly delta = 0)
    overall_health_score: int = 0
    technical_health_score: int = 0
    geo_readiness_score: int = 0
    trust_score: int = 0
    performance_score: int = 0
    score_formula_mode: str = "4_engine"
    formula_invariance_verified: bool = True
    
    # 18 Synthesized Review Profiles
    business_profile: ObservableBusinessProfile = Field(default_factory=ObservableBusinessProfile)
    entity_profile: EntityProfile = Field(default_factory=EntityProfile)
    service_profile: ServiceProductProfile = Field(default_factory=ServiceProductProfile)
    topic_taxonomy: TopicTaxonomyProfile = Field(default_factory=TopicTaxonomyProfile)
    dominant_concepts: List[str] = Field(default_factory=list)
    search_intent: SearchIntentProfile = Field(default_factory=SearchIntentProfile)
    topic_distribution: TopicDistributionProfile = Field(default_factory=TopicDistributionProfile)
    concentration_and_overlap: PageTopicConcentrationProfile = Field(default_factory=PageTopicConcentrationProfile)
    technical_seo: TechnicalSeoReviewProfile = Field(default_factory=TechnicalSeoReviewProfile)
    accessibility_security: AccessibilitySecurityProfile = Field(default_factory=AccessibilitySecurityProfile)
    internal_links: InternalLinkStructureProfile = Field(default_factory=InternalLinkStructureProfile)
    retrieval_readiness: RetrievalReadinessProfile = Field(default_factory=RetrievalReadinessProfile)
    answerability: AnswerabilityReviewProfile = Field(default_factory=AnswerabilityReviewProfile)
    claim_grounding: ClaimGroundingReviewProfile = Field(default_factory=ClaimGroundingReviewProfile)
    multimodal: MultimodalReviewProfile = Field(default_factory=MultimodalReviewProfile)
    agent_readiness: AgentReadinessReviewProfile = Field(default_factory=AgentReadinessReviewProfile)
    external_ai: ExternalAiReviewProfile = Field(default_factory=ExternalAiReviewProfile)
    limitations_and_uncertainty: EvidenceLimitationsProfile = Field(default_factory=EvidenceLimitationsProfile)
    
    # Epistemic separation container
    epistemic_separation: EpistemicSeparation = Field(default_factory=EpistemicSeparation)
    
    # Provenance tags & engine telemetry
    provenance_tags: List[Dict[str, Any]] = Field(default_factory=list)
    engines_executed: List[str] = Field(default_factory=list)
    raw_evidence_summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkReviewDataset(BaseModel):
    """Aggregate dataset collecting all 11 website intelligence reviews."""
    review_version: str = "11.2"
    created_at: str
    total_sites: int = 11
    sites_reviewed: int = 0
    reviews: Dict[str, WebsiteIntelligenceReview] = Field(default_factory=dict)
    summary_index: List[Dict[str, Any]] = Field(default_factory=list)


# ── Phase 11.3 Cross-Site Comparison & Void Analysis Models ──────────────────

class ComparisonState(str, Enum):
    """Explicit epistemological state for cross-site comparisons."""
    OBSERVED_DIFFERENCE = "OBSERVED_DIFFERENCE"
    COMMON = "COMMON"
    UNIQUE = "UNIQUE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class CrossSiteMatrixItem(BaseModel):
    """Summary row for cross-site comparison matrices across the 11-site benchmark."""
    domain: str
    name: str = ""
    role: str = "competitor"  # "competitor" or "target" / "sunrise"
    health_score: int = 0
    technical_health_score: int = 0
    geo_readiness_score: int = 0
    trust_score: int = 0
    performance_score: int = 0
    primary_intent: str = "INFORMATIONAL"
    entities_count: int = 0
    topics_count: int = 0
    dominant_concepts_count: int = 0
    schema_types_count: int = 0
    answer_units_count: int = 0
    claims_grounded_ratio: float = 0.0
    visual_assets_count: int = 0
    alt_coverage_ratio: float = 0.0
    action_surfaces_count: int = 0
    a11y_violations_count: int = 0
    security_findings_count: int = 0
    waf_barrier: str = "None"
    llms_txt_present: bool = False


class EntityComparisonAnalysis(BaseModel):
    """Common vs unique entities and entity types across the benchmark."""
    total_unique_entities_across_benchmark: int = 0
    common_entities: List[str] = Field(default_factory=list)
    unique_entities_by_site: Dict[str, List[str]] = Field(default_factory=dict)
    entity_types_coverage: Dict[str, List[str]] = Field(default_factory=dict)
    entity_alignment_summary: Dict[str, str] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class ServiceProductComparisonAnalysis(BaseModel):
    """Common vs unique services/products across the benchmark."""
    all_observed_services: List[str] = Field(default_factory=list)
    common_services: List[str] = Field(default_factory=list)
    unique_services_by_site: Dict[str, List[str]] = Field(default_factory=dict)
    service_offerings_by_site: Dict[str, List[str]] = Field(default_factory=dict)
    target_common_services: List[str] = Field(default_factory=list)
    target_unique_services: List[str] = Field(default_factory=list)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class TopicConceptComparisonAnalysis(BaseModel):
    """Topic and concept overlap, breadth, and Jaccard similarity matrix."""
    all_dominant_concepts: List[str] = Field(default_factory=list)
    common_concepts: List[str] = Field(default_factory=list)
    unique_concepts_by_site: Dict[str, List[str]] = Field(default_factory=dict)
    jaccard_similarity_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    topic_breadth_by_site: Dict[str, int] = Field(default_factory=dict)
    topic_breadth_tier: Dict[str, str] = Field(default_factory=dict)
    target_concept_overlap_with_cohort: Dict[str, float] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class SearchIntentComparisonAnalysis(BaseModel):
    """Search intent distribution and corroborating structural signals."""
    intent_distribution: Dict[str, int] = Field(default_factory=dict)
    primary_intent_by_site: Dict[str, str] = Field(default_factory=dict)
    secondary_intents_by_site: Dict[str, List[str]] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class ConcentrationOverlapComparisonAnalysis(BaseModel):
    """Content-to-boilerplate, title-H1 alignment, and cannibalization signals."""
    content_to_boilerplate_by_site: Dict[str, float] = Field(default_factory=dict)
    title_h1_overlap_by_site: Dict[str, float] = Field(default_factory=dict)
    heading_hierarchy_valid_by_site: Dict[str, bool] = Field(default_factory=dict)
    potential_cannibalization_counts: Dict[str, int] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class SchemaCoverageComparisonAnalysis(BaseModel):
    """Schema types detected, block counts, and structured data adoption."""
    schema_adoption_counts: Dict[str, int] = Field(default_factory=dict)
    all_detected_schema_types: List[str] = Field(default_factory=list)
    schema_types_by_site: Dict[str, List[str]] = Field(default_factory=dict)
    schema_distribution_across_benchmark: Dict[str, int] = Field(default_factory=dict)
    sites_with_no_schema: List[str] = Field(default_factory=list)
    target_schema_status: str = "ABSENT"
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class AnswerabilityComparisonAnalysis(BaseModel):
    """Answer units across sites and structural types distribution."""
    total_units_by_site: Dict[str, int] = Field(default_factory=dict)
    unit_types_distribution_across_benchmark: Dict[str, int] = Field(default_factory=dict)
    units_by_site_and_type: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    structural_diversity_by_site: Dict[str, int] = Field(default_factory=dict)
    zero_unit_sites: List[str] = Field(default_factory=list)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class ClaimGroundingComparisonAnalysis(BaseModel):
    """Claim grounding ratios, supported claims, and verification rates."""
    total_claims_by_site: Dict[str, int] = Field(default_factory=dict)
    supported_claims_by_site: Dict[str, int] = Field(default_factory=dict)
    grounding_ratios_by_site: Dict[str, float] = Field(default_factory=dict)
    contradicted_claims_by_site: Dict[str, int] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class AiRetrievalComparisonAnalysis(BaseModel):
    """12-bot access matrix, WAF challenge barriers, and GEO scores."""
    search_bots_allowed_by_site: Dict[str, int] = Field(default_factory=dict)
    ai_bots_allowed_by_site: Dict[str, int] = Field(default_factory=dict)
    waf_barrier_by_site: Dict[str, str] = Field(default_factory=dict)
    word_count_delta_by_site: Dict[str, int] = Field(default_factory=dict)
    llms_txt_presence_by_site: Dict[str, bool] = Field(default_factory=dict)
    geo_score_by_site: Dict[str, int] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class MultimodalAgentComparisonAnalysis(BaseModel):
    """Visual assets, alt coverage, and autonomous agent action surfaces."""
    visual_assets_by_site: Dict[str, int] = Field(default_factory=dict)
    alt_coverage_ratio_by_site: Dict[str, float] = Field(default_factory=dict)
    visual_gaps_by_site: Dict[str, int] = Field(default_factory=dict)
    forms_by_site: Dict[str, int] = Field(default_factory=dict)
    buttons_by_site: Dict[str, int] = Field(default_factory=dict)
    schema_actions_by_site: Dict[str, int] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class TechnicalA11ySecurityComparisonAnalysis(BaseModel):
    """Technical SEO, automated WCAG 2.1 AA violations, and security headers."""
    title_length_by_site: Dict[str, int] = Field(default_factory=dict)
    meta_desc_length_by_site: Dict[str, int] = Field(default_factory=dict)
    ttfb_ms_by_site: Dict[str, float] = Field(default_factory=dict)
    a11y_violations_by_site: Dict[str, int] = Field(default_factory=dict)
    critical_a11y_violations_by_site: Dict[str, int] = Field(default_factory=dict)
    a11y_disclaimer: str = "Automated checks evaluate observable criteria; non-certification scope."
    https_by_site: Dict[str, bool] = Field(default_factory=dict)
    hsts_by_site: Dict[str, bool] = Field(default_factory=dict)
    csp_by_site: Dict[str, bool] = Field(default_factory=dict)
    security_findings_by_site: Dict[str, int] = Field(default_factory=dict)
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    summary: str = ""


class ObservableVoidItem(BaseModel):
    """Deterministic, provenance-preserving representation of an observable gap or void."""
    void_id: str
    category: str  # "SCHEMA", "ANSWERABILITY", "MULTIMODAL", "ACTION_SURFACE", "TOPIC", "SERVICE", "SECURITY", "GEO"
    title: str
    description: str
    state: ComparisonState = ComparisonState.OBSERVED_DIFFERENCE
    source_sites_present: List[str] = Field(default_factory=list)
    source_sites_absent: List[str] = Field(default_factory=list)
    target_site_status: str = "ABSENT"  # "PRESENT", "ABSENT", "PARTIAL", "INSUFFICIENT_EVIDENCE"
    supporting_fields: List[str] = Field(default_factory=list)
    provenance_sources: List[str] = Field(default_factory=list)
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list)
    epistemic_tier: str = "ANALYSIS"


class TargetVsBenchmarkComparison(BaseModel):
    """Target-centric comparison of sunrisetesting.vercel.app against the 10-site competitor benchmark cohort."""
    target_domain: str = "sunrisetesting.vercel.app"
    benchmark_cohort_domains: List[str] = Field(default_factory=list)
    target_role: str = "sunrise"
    common_capabilities: List[str] = Field(default_factory=list)
    target_unique_capabilities: List[str] = Field(default_factory=list)
    observable_voids: List[ObservableVoidItem] = Field(default_factory=list)
    dimensional_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""


class EvidenceUncertaintyProfile(BaseModel):
    """Evidence boundaries, crawl limitations, and comparison uncertainty."""
    crawl_limitations_summary: str = ""
    dimensional_statuses: Dict[str, str] = Field(default_factory=dict)
    insufficient_evidence_notes: List[str] = Field(default_factory=list)
    not_comparable_notes: List[str] = Field(default_factory=list)
    epistemic_disclaimer: str = (
        "All comparisons represent observable website differences derived solely from static DOM, "
        "rendered browser DOM, HTTP headers, and robots.txt. No inference of commercial market leadership, "
        "search engine rankings, traffic volume, or overall business performance is made."
    )


class BenchmarkComparisonReport(BaseModel):
    """Complete, self-contained cross-site comparison and void analysis report."""
    comparison_version: str = "11.3"
    created_at: str
    total_sites: int = 11
    target_domain: str = "sunrisetesting.vercel.app"
    cohort_domains: List[str] = Field(default_factory=list)
    cross_site_matrix: List[CrossSiteMatrixItem] = Field(default_factory=list)
    entity_comparison: EntityComparisonAnalysis = Field(default_factory=EntityComparisonAnalysis)
    service_comparison: ServiceProductComparisonAnalysis = Field(default_factory=ServiceProductComparisonAnalysis)
    topic_concept_comparison: TopicConceptComparisonAnalysis = Field(default_factory=TopicConceptComparisonAnalysis)
    search_intent_comparison: SearchIntentComparisonAnalysis = Field(default_factory=SearchIntentComparisonAnalysis)
    concentration_comparison: ConcentrationOverlapComparisonAnalysis = Field(default_factory=ConcentrationOverlapComparisonAnalysis)
    schema_comparison: SchemaCoverageComparisonAnalysis = Field(default_factory=SchemaCoverageComparisonAnalysis)
    answerability_comparison: AnswerabilityComparisonAnalysis = Field(default_factory=AnswerabilityComparisonAnalysis)
    claim_grounding_comparison: ClaimGroundingComparisonAnalysis = Field(default_factory=ClaimGroundingComparisonAnalysis)
    retrieval_comparison: AiRetrievalComparisonAnalysis = Field(default_factory=AiRetrievalComparisonAnalysis)
    multimodal_agent_comparison: MultimodalAgentComparisonAnalysis = Field(default_factory=MultimodalAgentComparisonAnalysis)
    technical_a11y_security_comparison: TechnicalA11ySecurityComparisonAnalysis = Field(default_factory=TechnicalA11ySecurityComparisonAnalysis)
    observable_voids: List[ObservableVoidItem] = Field(default_factory=list)
    target_vs_benchmark: TargetVsBenchmarkComparison = Field(default_factory=TargetVsBenchmarkComparison)
    uncertainty_and_limitations: EvidenceUncertaintyProfile = Field(default_factory=EvidenceUncertaintyProfile)
    epistemic_separation: EpistemicSeparation = Field(default_factory=EpistemicSeparation)
    formula_invariance_verified: bool = True
    provenance_tags: List[Dict[str, Any]] = Field(default_factory=list)


# ── Phase 11.4 Capability-Gap Discovery Models ───────────────────────────────


class GapSeverity(str, Enum):
    P0 = "P0"  # Critical architectural or detection gap causing total engine blindness
    P1 = "P1"  # Major semantic or extraction gap causing substantial analysis error
    P2 = "P2"  # Moderate heuristic or coverage limitation
    P3 = "P3"  # Minor cosmetic or peripheral reporting discrepancy


class GapClassification(str, Enum):
    TRUE_CAPABILITY_GAP = "TRUE_CAPABILITY_GAP"
    EVIDENCE_LIMITATION = "EVIDENCE_LIMITATION"
    WEBSITE_DEFICIENCY = "WEBSITE_DEFICIENCY"
    REPORTING_DEFECT = "REPORTING_DEFECT"


class GapCategory(str, Enum):
    DETECTION_BLIND_SPOT = "DETECTION_BLIND_SPOT"
    EXTRACTION_BLIND_SPOT = "EXTRACTION_BLIND_SPOT"
    SEMANTIC_INTERPRETATION = "SEMANTIC_INTERPRETATION"
    SEARCH_INTENT = "SEARCH_INTENT"
    TOPIC_DIFFERENTIATION = "TOPIC_DIFFERENTIATION"
    ENTITY_CLAIM_GROUNDING = "ENTITY_CLAIM_GROUNDING"
    AI_GEO_INTERPRETATION = "AI_GEO_INTERPRETATION"
    MULTIMODAL_AGENT = "MULTIMODAL_AGENT"
    CROSS_SITE_COMPARISON = "CROSS_SITE_COMPARISON"
    EVIDENCE_PROVENANCE = "EVIDENCE_PROVENANCE"
    RECOMMENDATION_QUALITY = "RECOMMENDATION_QUALITY"


class CapabilityGapRecord(BaseModel):
    """Detailed record of a discovered RankIntel capability gap or evidence limitation."""
    gap_id: str
    category: GapCategory
    affected_engine: str
    title: str
    severity: GapSeverity
    classification: GapClassification
    confidence: float = 1.0
    observed_evidence: str
    why_current_output_insufficient: str
    supporting_sites: List[str] = Field(default_factory=list)
    expected_behavior: str
    recommended_future_direction: str
    epistemic_tier: str = "ANALYSIS"


class FalseGapExclusionRecord(BaseModel):
    """Candidate gap that was investigated and ruled out as a website deficiency, not an engine defect."""
    exclusion_id: str
    candidate_gap: str
    classification: GapClassification = GapClassification.WEBSITE_DEFICIENCY
    observed_evidence: str
    why_not_engine_defect: str
    affected_sites: List[str] = Field(default_factory=list)
    epistemic_tier: str = "FACT"


class CapabilityGapAnalysisReport(BaseModel):
    """Complete, self-contained RankIntel capability-gap discovery & engine evolution report."""
    analysis_version: str = "11.4"
    created_at: str
    total_sites_analyzed: int = 11
    target_domain: str = "sunrisetesting.vercel.app"
    total_gaps_cataloged: int = 0
    true_capability_gaps_count: int = 0
    evidence_limitations_count: int = 0
    false_gap_exclusions_count: int = 0
    priority_breakdown: Dict[str, int] = Field(default_factory=dict)
    engine_distribution: Dict[str, int] = Field(default_factory=dict)
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    gaps: List[CapabilityGapRecord] = Field(default_factory=list)
    false_gap_exclusions: List[FalseGapExclusionRecord] = Field(default_factory=list)
    executive_summary: str = ""
    recommendations_for_m11_5: List[str] = Field(default_factory=list)
    epistemic_separation: EpistemicSeparation = Field(default_factory=EpistemicSeparation)
    formula_invariance_verified: bool = True
    provenance_tags: List[Dict[str, Any]] = Field(default_factory=list)


