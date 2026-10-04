"""
RankIntel Data Models for Multi-Engine Evidence & Synthesis.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, model_validator

class BotCategory(str, Enum):
    SEARCH_ENGINE = "search_engine"
    AI_SEARCH = "ai_search"
    AI_TRAINING = "ai_training"
    PLATFORM = "platform"

class BotAccessStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"

class BotMatrixEntry(BaseModel):
    bot_name: str
    category: str  # "Search Engine", "AI Search Agent", "AI Model Training", "Platform Bot"
    company_or_engine: str
    status: str  # "ALLOWED", "DISALLOWED"
    rule_source: str  # "explicit", "wildcard", "default_allow"
    business_impact: str
    matched_directive: Optional[str] = None
    line_number: Optional[int] = None
    raw_pattern: Optional[str] = None

class BotMatrixReport(BaseModel):
    url: str = ""
    robots_url: str = ""
    robots_found: bool = True
    total_bots_evaluated: int = 0
    search_allowed_count: int = 0
    ai_search_allowed_count: int = 0
    ai_training_blocked_count: int = 0
    entries: List[BotMatrixEntry] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class BotStatus(BaseModel):
    bot: str
    status: str  # ALLOWED, BLOCKED, MISSING, PARTIAL
    category: str  # search or training
    engine: str = ""
    role_or_purpose: str = ""
    via_wildcard: bool = False

class RobotsEvidence(BaseModel):
    found: bool = False
    robots_url: str = ""
    bot_access: Dict[str, BotStatus] = Field(default_factory=dict)
    sitemaps: List[str] = Field(default_factory=list)
    crawl_delay: Optional[int] = None
    discovered_urls: List[str] = Field(default_factory=list)
    engine_source: str = ""
    bot_matrix: Optional[BotMatrixReport] = None

class OnPageEvidence(BaseModel):
    url: str = ""
    status_code: int = 0
    response_time_sec: float = 0.0
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_desc_length: int = 0
    h1_count: int = 0
    h1_text: List[str] = Field(default_factory=list)
    h2_count: int = 0
    h2_text: List[str] = Field(default_factory=list)
    h3_count: int = 0
    h3_text: List[str] = Field(default_factory=list)
    total_images: int = 0
    images_with_alt: int = 0
    word_count: int = 0
    canonical_url: Optional[str] = None
    is_redirect: bool = False
    response_headers: Dict[str, str] = Field(default_factory=dict)
    internal_links: List[str] = Field(default_factory=list)
    external_links: List[str] = Field(default_factory=list)
    engine_source: str = ""

class SchemaEvidence(BaseModel):
    detected_types: List[str] = Field(default_factory=list)
    deprecated_types_detected: List[str] = Field(default_factory=list)
    blocks_count: int = 0
    is_injected_via_js: bool = False
    validation_issues: List[str] = Field(default_factory=list)
    sameas_urls: List[str] = Field(default_factory=list)
    has_organization: bool = False
    has_author: bool = False
    engine_source: str = ""

class GeoCitabilityMethod(BaseModel):
    name: str
    label: str
    detected: bool
    score: int
    max_score: int
    impact: str
    details: Dict[str, Any] = Field(default_factory=dict)

class GeoAeoEvidence(BaseModel):
    overall_citability_score: int = 0
    answer_first_ratio: float = 0.0
    passage_density_ratio: float = 0.0
    statistical_density_per_1000: float = 0.0
    outbound_citations_count: int = 0
    authoritative_citations_count: int = 0
    llms_txt_found: bool = False
    llms_txt_warnings: List[str] = Field(default_factory=list)
    llms_full_found: bool = False
    question_h2s: List[str] = Field(default_factory=list)
    methods: List[GeoCitabilityMethod] = Field(default_factory=list)
    engine_source: str = ""

class TrustLayerScore(BaseModel):
    name: str
    label: str
    score: int = 0
    max_score: int = 5
    signals_found: List[str] = Field(default_factory=list)
    signals_missing: List[str] = Field(default_factory=list)

class TrustStackResult(BaseModel):
    overall_score: int = 0  # 0-100 normalized
    raw_score: int = 0      # 0-25 sum of 5 layers
    grade: str = "F"        # A, B, C, D, F
    layers: Dict[str, TrustLayerScore] = Field(default_factory=dict)
    summary: str = ""

class PerformanceMetric(BaseModel):
    name: str
    value: float
    unit: str
    status: str  # GOOD, NEEDS_IMPROVEMENT, POOR
    threshold_good: float
    threshold_poor: float

class PerformanceEvidence(BaseModel):
    source: str = "local_probe"  # "pagespeed_crux_field", "pagespeed_lighthouse_lab", "local_probe"
    overall_performance_score: int = 0  # 0-100
    ttfb_ms: float = 0.0
    fcp_ms: Optional[float] = None
    lcp_ms: Optional[float] = None
    cls: Optional[float] = None
    inp_ms: Optional[float] = None
    metrics: List[PerformanceMetric] = Field(default_factory=list)
    passed_audit: bool = True
    notes: List[str] = Field(default_factory=list)

class SecurityStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class SecurityFindingCategory(str, Enum):
    SEO_PROBLEM = "seo_problem"
    SECURITY_VULNERABILITY = "security_vulnerability"
    BEST_PRACTICE = "best_practice"

class SecuritySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"

class SecurityFinding(BaseModel):
    code: str
    title: str
    category: SecurityFindingCategory
    severity: SecuritySeverity
    description: str
    recommendation: str
    header_name: Optional[str] = None
    header_value: Optional[str] = None

class TlsCertificateDetails(BaseModel):
    is_valid: bool = False
    issuer: Dict[str, str] = Field(default_factory=dict)
    subject: Dict[str, str] = Field(default_factory=dict)
    expires_at: Optional[str] = None
    days_until_expiration: Optional[int] = None
    protocol_version: Optional[str] = None
    cipher: Optional[str] = None
    error_message: Optional[str] = None
    handshake_status: SecurityStatus = SecurityStatus.UNKNOWN

class CookieSecurityDetails(BaseModel):
    name: str
    secure: bool = False
    httponly: bool = False
    samesite: Optional[str] = None
    issues: List[str] = Field(default_factory=list)

class SecurityEvidence(BaseModel):
    url: str = ""
    is_https: bool = True
    overall_status: SecurityStatus = SecurityStatus.UNKNOWN
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    headers_evaluated: Dict[str, str] = Field(default_factory=dict)
    hsts_present: bool = False
    hsts_include_subdomains: bool = False
    hsts_preload: bool = False
    hsts_max_age: Optional[int] = None
    csp_present: bool = False
    csp_directives: List[str] = Field(default_factory=list)
    x_frame_options: Optional[str] = None
    x_content_type_options: Optional[str] = None
    referrer_policy: Optional[str] = None
    permissions_policy_present: bool = False
    server_leakage: List[str] = Field(default_factory=list)
    mixed_content_resources: List[str] = Field(default_factory=list)
    tls_details: Optional[TlsCertificateDetails] = None
    cookies: List[CookieSecurityDetails] = Field(default_factory=list)
    findings: List[SecurityFinding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ImageFormatEvidence(BaseModel):
    declared_format: str = "UNKNOWN"     # Extracted from URL extension or type attribute
    observed_mime_type: str = "UNKNOWN"  # Populated only if image response was observed
    is_modern_format: bool = False       # True for webp, avif, svg

class ImageDetail(BaseModel):
    src: str
    alt: Optional[str] = None
    alt_status: str = "MISSING"          # "OPTIMAL", "MISSING", "EMPTY_DECORATIVE", "GENERIC_FILENAME"
    has_dimensions: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    is_responsive: bool = False          # Has srcset, sizes, or nested in <picture>
    is_lazy: bool = False
    is_fetchpriority_high: bool = False
    format_evidence: ImageFormatEvidence = Field(default_factory=ImageFormatEvidence)
    potential_layout_shift_risk: bool = False # Missing dimensions without inline aspect-ratio style
    potential_lcp_risk: bool = False     # Heuristic flag: early/above-fold image is lazy-loaded

class HtmlHeadEvidence(BaseModel):
    viewport_present: bool = False
    viewport_configuration: Optional[str] = None
    responsive_behavior: str = "UNKNOWN" # UNKNOWN unless verified via browser rendering
    lang_present: bool = False
    lang_code: Optional[str] = None
    charset_present: bool = False
    charset_declared: Optional[str] = None
    heading_hierarchy_valid: bool = True
    heading_skips: List[str] = Field(default_factory=list)
    insecure_resource_urls: List[str] = Field(default_factory=list)

class ImageSEOEvidence(BaseModel):
    total_images: int = 0
    images_with_alt: int = 0
    missing_alt_count: int = 0
    generic_alt_count: int = 0
    decorative_alt_count: int = 0
    missing_dimensions_count: int = 0
    modern_format_count: int = 0
    legacy_format_count: int = 0
    lazy_loaded_count: int = 0
    early_lazy_lcp_risks_count: int = 0
    images: List[ImageDetail] = Field(default_factory=list)
    head_audit: Optional[HtmlHeadEvidence] = None

class AccessibilitySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    SERIOUS = "SERIOUS"
    MODERATE = "MODERATE"
    MINOR = "MINOR"
    UNKNOWN = "UNKNOWN"

class WcagLevel(str, Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"
    UNKNOWN = "UNKNOWN"

class WcagStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class AccessibilityViolation(BaseModel):
    rule_id: str
    wcag_sc: str = ""
    level: WcagLevel = WcagLevel.UNKNOWN
    severity: AccessibilitySeverity = AccessibilitySeverity.UNKNOWN
    description: str
    help_url: str = ""
    selector: Optional[str] = None
    html_snippet: Optional[str] = None
    failure_summary: str = ""
    tier: str = "static" # "static" or "axe_rendered"

class AccessibilityEvidence(BaseModel):
    url: str = ""
    engine_source: str = "static_ast_auditor" 
    browser_evaluated: bool = False
    wcag_aa_status: WcagStatus = WcagStatus.UNKNOWN
    total_violations: int = 0
    critical_count: int = 0
    serious_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    rules_evaluated_count: int = 0
    rules_passed_count: int = 0
    violations: List[AccessibilityViolation] = Field(default_factory=list)
    visual_contrast_status: WcagStatus = WcagStatus.UNKNOWN
    touch_target_status: WcagStatus = WcagStatus.UNKNOWN
    recommendations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

class EvidenceProvenanceTag(BaseModel):
    """Tracks which engine produced a specific finding, with confidence rating."""
    finding: str
    source_file: str
    engine: str
    evidence_snippet: str = ""
    confidence: str = "high"  # high, medium, low
    confirmed_by: List[str] = Field(default_factory=list)
    contradicted_by: List[str] = Field(default_factory=list)

class KeywordIntelligence(BaseModel):
    """Keyword ranking and traffic data from cloud sources."""
    source: str = "openseo_mcp"
    estimated_monthly_traffic: int = 0
    total_keywords: int = 0
    top_keywords: List[Dict[str, Any]] = Field(default_factory=list)
    keyword_gaps: List[Dict[str, Any]] = Field(default_factory=list)

class BacklinkIntelligence(BaseModel):
    """Backlink authority data from cloud sources."""
    source: str = "openseo_mcp"
    referring_domains: int = 0
    total_backlinks: int = 0
    domain_authority_score: int = 0
    top_anchors: List[str] = Field(default_factory=list)

class CloudIntelligenceEvidence(BaseModel):
    """Aggregated cloud intelligence (keyword + backlink + AI visibility)."""
    available: bool = False
    keywords: Optional[KeywordIntelligence] = None
    backlinks: Optional[BacklinkIntelligence] = None
    ai_visibility_score: int = 0
    notes: List[str] = Field(default_factory=list)

class ContentExtractionMethod(str, Enum):
    SEMANTIC_MAIN = "SEMANTIC_MAIN"
    SEMANTIC_ARTICLE = "SEMANTIC_ARTICLE"
    ROLE_MAIN = "ROLE_MAIN"
    HEURISTIC_PRUNED_BODY = "HEURISTIC_PRUNED_BODY"
    RAW_BODY_FALLBACK = "RAW_BODY_FALLBACK"
    UNAVAILABLE = "UNAVAILABLE"

class WordCountTier(str, Enum):
    """Descriptive telemetry measurement buckets (configuration-dependent, not universal SEO value judgments)."""
    EMPTY = "EMPTY"             # 0 words
    VERY_LOW = "VERY_LOW"       # 1 - 99 words
    LOW = "LOW"                 # 100 - 199 words (Screaming Frog default low-content filter is <200)
    MODERATE = "MODERATE"       # 200 - 599 words
    SUBSTANTIVE = "SUBSTANTIVE" # 600+ words measurement bucket
    UNAVAILABLE = "UNAVAILABLE"

class TitleH1AlignmentStatus(str, Enum):
    STRONG_ALIGNMENT = "STRONG_ALIGNMENT"
    MODERATE_ALIGNMENT = "MODERATE_ALIGNMENT"
    WEAK_ALIGNMENT = "WEAK_ALIGNMENT"
    MISALIGNED = "MISALIGNED"
    UNAVAILABLE = "UNAVAILABLE"

class ThinContentEvidence(BaseModel):
    """Factual telemetry regarding main content density and placeholder copy."""
    word_count_tier: WordCountTier = WordCountTier.UNAVAILABLE
    has_substantive_content: bool = False
    is_empty_or_whitespace: bool = False
    placeholder_text_detected: bool = False
    placeholder_snippets: List[str] = Field(default_factory=list)
    boilerplate_dominated: bool = False
    facts: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class TitleH1RelationshipEvidence(BaseModel):
    """Observed relationship between Title, H1, and main content keywords."""
    title_text: Optional[str] = None
    h1_text: Optional[str] = None
    title_h1_exact_match: bool = False
    title_in_h1: bool = False
    h1_in_title: bool = False
    token_overlap_ratio: float = 0.0
    lead_content_keyword_ratio: float = 0.0
    full_content_keyword_ratio: float = 0.0
    alignment_status: TitleH1AlignmentStatus = TitleH1AlignmentStatus.UNAVAILABLE
    notes: List[str] = Field(default_factory=list)

class HeadingSectionDetail(BaseModel):
    heading_tag: str
    heading_text: str
    word_count: int

class HeadingStructureEvidence(BaseModel):
    """Observed heading hierarchy, sequence, and section distribution."""
    total_headings: int = 0
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    h5_count: int = 0
    h6_count: int = 0
    heading_hierarchy_valid: bool = True
    heading_skips: List[str] = Field(default_factory=list)
    multiple_h1_detected: bool = False
    h1_texts: List[str] = Field(default_factory=list)
    empty_headings_count: int = 0
    empty_headings: List[str] = Field(default_factory=list)
    empty_sections_count: int = 0
    average_words_per_section: float = 0.0
    sections: List[HeadingSectionDetail] = Field(default_factory=list)
    anomalies: List[str] = Field(default_factory=list)

class ContentEvidence(BaseModel):
    """Comprehensive single-page Content Intelligence evidence."""
    url: str = ""
    engine_source: str = "content_engine"
    extraction_method: ContentExtractionMethod = ContentExtractionMethod.UNAVAILABLE
    main_content_text_preview: str = ""
    main_content_word_count: int = 0
    main_content_char_count: int = 0
    total_body_word_count: int = 0
    content_to_boilerplate_ratio: float = 0.0
    paragraph_count: int = 0
    sentence_count: int = 0
    exact_content_hash: str = ""  # SHA-256 of normalized main-content text (exact duplicate main-content detection)
    html_hash: str = ""           # SHA-256 of normalized full body HTML (exact full-page HTML duplicate detection)
    simhash: str = ""             # 64-bit SimHash hex fingerprint of main content
    thin_content: ThinContentEvidence = Field(default_factory=ThinContentEvidence)
    title_h1_relationship: TitleH1RelationshipEvidence = Field(default_factory=TitleH1RelationshipEvidence)
    heading_structure: HeadingStructureEvidence = Field(default_factory=HeadingStructureEvidence)
    facts: List[str] = Field(default_factory=list)

class ExactDuplicateCluster(BaseModel):
    cluster_id: str
    content_hash: str
    word_count: int
    urls: List[str] = Field(default_factory=list)

class NearDuplicatePair(BaseModel):
    url_a: str
    url_b: str
    similarity_percentage: float
    hamming_distance: int
    method: str = "simhash_shingle_jaccard"

class RepeatedBoilerplateBlock(BaseModel):
    text_snippet: str
    word_count: int
    page_count: int
    pages: List[str] = Field(default_factory=list)

class SiteContentIntelligence(BaseModel):
    """Site-wide multi-page content analysis (duplicates, near-duplicates, boilerplate)."""
    total_pages_evaluated: int = 0
    exact_duplicate_clusters_count: int = 0
    exact_duplicate_clusters: List[ExactDuplicateCluster] = Field(default_factory=list)
    near_duplicate_pairs_count: int = 0
    near_duplicate_pairs: List[NearDuplicatePair] = Field(default_factory=list)
    repeated_boilerplate_blocks_count: int = 0
    repeated_boilerplate_blocks: List[RepeatedBoilerplateBlock] = Field(default_factory=list)
    thin_content_urls: List[str] = Field(default_factory=list)
    heading_skip_urls: List[str] = Field(default_factory=list)
    title_h1_mismatch_urls: List[str] = Field(default_factory=list)
    page_content_evidence: Dict[str, ContentEvidence] = Field(default_factory=dict)

class EvidenceNature(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNAVAILABLE = "UNAVAILABLE"

# ==============================================================================
# Phase 8.2 — Entity Intelligence Models
# ==============================================================================

class EntityType(str, Enum):
    ORGANIZATION = "ORGANIZATION"
    LOCAL_BUSINESS = "LOCAL_BUSINESS"
    PERSON = "PERSON"
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    PLACE = "PLACE"
    OTHER = "OTHER"

class EntitySource(str, Enum):
    JSON_LD = "JSON_LD"
    META_TAG = "META_TAG"
    VISIBLE_HTML = "VISIBLE_HTML"
    MICRODATA = "MICRODATA"
    UNAVAILABLE = "UNAVAILABLE"

class EntitySignalType(str, Enum):
    STRUCTURED_DATA_DECLARATION = "structured_data_declaration"
    BRAND_OR_SITE_NAME_SIGNAL = "brand_or_site_name_signal"
    CONTACT_SIGNAL = "contact_signal"
    COPYRIGHT_SIGNAL = "copyright_signal"
    AUTHOR_BYLINE_SIGNAL = "author_byline_signal"

class EntityAlignmentStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    DIVERGENT_IDENTITY_SUSPECTED = "DIVERGENT_IDENTITY_SUSPECTED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class EntityRelationshipType(str, Enum):
    ORGANIZATION_TO_WEBSITE = "organization_to_website"
    ORGANIZATION_TO_LOCATION = "organization_to_location"
    ORGANIZATION_TO_SOCIAL_PROFILE = "organization_to_social_profile"
    PRODUCT_TO_ORGANIZATION = "product_to_organization"
    SERVICE_TO_ORGANIZATION = "service_to_organization"
    PERSON_TO_ORGANIZATION = "person_to_organization"
    OTHER = "other"

class DetectedEntity(BaseModel):
    """Observable entity identified from structured data or visible page signals."""
    entity_type: EntityType = EntityType.OTHER
    name: str
    normalized_name: str = ""
    source: EntitySource = EntitySource.UNAVAILABLE
    signal_type: EntitySignalType = EntitySignalType.STRUCTURED_DATA_DECLARATION
    url: str = ""
    declared_url: Optional[str] = None
    structured_data_type: Optional[str] = None
    description: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    same_as: List[str] = Field(default_factory=list)
    identifiers: Dict[str, str] = Field(default_factory=dict)
    raw_context: Optional[str] = None
    confidence_nature: EvidenceNature = EvidenceNature.OBSERVED

class EntityRelationship(BaseModel):
    """Simple observable relationship between entities or entity and property."""
    subject_name: str
    subject_type: EntityType
    relation: EntityRelationshipType
    object_name: str
    object_type: str
    source: str = ""
    evidence_text: Optional[str] = None

class VisibleStructuredComparison(BaseModel):
    """Contextual comparison between structured data declarations and visible brand/text signals."""
    entity_type: EntityType
    attribute_name: str  # "name", "address", "telephone", etc.
    structured_value: Optional[str] = None
    visible_value: Optional[str] = None
    alignment_status: EntityAlignmentStatus = EntityAlignmentStatus.UNAVAILABLE
    notes: str = ""

class EntityEvidence(BaseModel):
    """Comprehensive single-page Entity Intelligence evidence."""
    url: str = ""
    engine_source: str = "entity_engine"
    total_entities_detected: int = 0
    detected_entities: List[DetectedEntity] = Field(default_factory=list)
    relationships: List[EntityRelationship] = Field(default_factory=list)
    structured_vs_visible: List[VisibleStructuredComparison] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)

class EntityInconsistency(BaseModel):
    """Observable cross-page attribute variation/conflict for an apparent entity."""
    entity_type: EntityType
    entity_name: str
    attribute: str  # "name", "address", "telephone", "url", "sameAs"
    conflicting_values: Dict[str, List[str]] = Field(default_factory=dict)  # value -> list of URLs
    details: str = ""

class PrimaryOrganizationCandidate(BaseModel):
    """Candidate primary organization identified by observable evidence (not definitive identity)."""
    candidate_name: Optional[str] = None
    selection_reasons: List[str] = Field(default_factory=list)
    evidence_sources: List[str] = Field(default_factory=list)
    confidence_nature: EvidenceNature = EvidenceNature.OBSERVED

class SiteEntityIntelligence(BaseModel):
    """Site-wide multi-page entity intelligence and consistency tracking."""
    total_pages_evaluated: int = 0
    total_entities_detected: int = 0
    unique_entities_count: int = 0
    primary_organization_candidate: Optional[PrimaryOrganizationCandidate] = None
    inconsistencies_count: int = 0
    inconsistencies: List[EntityInconsistency] = Field(default_factory=list)
    all_entities: List[DetectedEntity] = Field(default_factory=list)
    all_relationships: List[EntityRelationship] = Field(default_factory=list)
    page_entity_evidence: Dict[str, EntityEvidence] = Field(default_factory=dict)

class CrawlStatus(str, Enum):
    QUEUED = "QUEUED"
    FETCHED = "FETCHED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    REDIRECTED = "REDIRECTED"
    DUPLICATE = "DUPLICATE"

class CrawlabilityStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"

class IndexabilityStatus(str, Enum):
    INDEXABLE = "INDEXABLE"
    NOINDEX = "NOINDEX"
    REDIRECT = "REDIRECT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

class CanonicalizationSignal(str, Enum):
    SELF_REFERENCING = "SELF_REFERENCING"
    CANONICALIZED_ELSEWHERE = "CANONICALIZED_ELSEWHERE"
    CROSS_DOMAIN = "CROSS_DOMAIN"
    MISSING = "MISSING"
    INVALID_TARGET = "INVALID_TARGET"

class IndexConfirmationStatus(str, Enum):
    CONFIRMED_INDEXED = "CONFIRMED_INDEXED"
    CONFIRMED_NOT_INDEXED = "CONFIRMED_NOT_INDEXED"
    UNKNOWN = "UNKNOWN"

class SearchEligibilityRecord(BaseModel):
    url: str
    crawlability: CrawlabilityStatus = CrawlabilityStatus.UNKNOWN
    indexability: IndexabilityStatus = IndexabilityStatus.UNKNOWN
    canonicalization: CanonicalizationSignal = CanonicalizationSignal.MISSING
    confirmation: IndexConfirmationStatus = IndexConfirmationStatus.UNKNOWN
    canonical_target: Optional[str] = None
    http_status: int = 0
    meta_robots_directives: List[str] = Field(default_factory=list)
    x_robots_tag_directives: List[str] = Field(default_factory=list)
    in_sitemap: bool = False
    inbound_links_count: int = 0
    requires_js_to_render: bool = False
    evaluation_notes: List[str] = Field(default_factory=list)

class CrawlConfig(BaseModel):
    max_pages: int = Field(default=50, ge=1, le=500)
    max_depth: int = Field(default=3, ge=1, le=10)
    concurrency: int = Field(default=5, ge=1, le=20)
    crawl_delay: float = Field(default=0.1, ge=0.0, le=5.0)
    timeout_sec: float = Field(default=15.0, ge=1.0, le=60.0)
    respect_robots_txt: bool = True
    allowed_subdomains: bool = False
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_sec: float = Field(default=0.5, ge=0.0, le=10.0)
    strip_tracking_params: bool = True
    enable_sitemap_analysis: bool = False
    enable_browser_rendering: bool = False
    user_agent: str = "RankIntel/2.0 (+https://github.com/ZeroTrace7/RankIntel)"

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "timeout" in data and "timeout_sec" not in data:
                data["timeout_sec"] = data.pop("timeout")
            if "respect_robots" in data and "respect_robots_txt" not in data:
                data["respect_robots_txt"] = data.pop("respect_robots")
        return data

    @property
    def timeout(self) -> float:
        return self.timeout_sec

    @property
    def respect_robots(self) -> bool:
        return self.respect_robots_txt

class RedirectHop(BaseModel):
    url: str
    status_code: int
    location: str
    latency_ms: Optional[float] = None

class RedirectChainStatus(str, Enum):
    RESOLVED = "RESOLVED"
    MULTI_HOP = "MULTI_HOP"
    LOOP = "LOOP"
    BROKEN_TARGET = "BROKEN_TARGET"
    EXCEEDED_MAX_HOPS = "EXCEEDED_MAX_HOPS"
    MISSING_LOCATION = "MISSING_LOCATION"
    UNVERIFIED_TARGET = "UNVERIFIED_TARGET"

class RedirectChainRecord(BaseModel):
    initial_url: str
    final_url: str
    total_hops: int = 0
    hops: List[RedirectHop] = Field(default_factory=list)
    has_loop: bool = False
    status: RedirectChainStatus = RedirectChainStatus.RESOLVED
    total_latency_ms: Optional[float] = None
    notes: List[str] = Field(default_factory=list)

class CanonicalChainStatus(str, Enum):
    SELF_REFERENCING = "SELF_REFERENCING"
    RESOLVED = "RESOLVED"
    CHAIN = "CHAIN"
    LOOP = "LOOP"
    POINTS_TO_REDIRECT = "POINTS_TO_REDIRECT"
    POINTS_TO_DEAD_URL = "POINTS_TO_DEAD_URL"
    UNVERIFIED_TARGET = "UNVERIFIED_TARGET"
    MISSING = "MISSING"
    INVALID_TARGET = "INVALID_TARGET"

class CanonicalChainRecord(BaseModel):
    source_url: str
    declared_canonical: Optional[str] = None
    final_canonical: Optional[str] = None
    total_hops: int = 0
    has_loop: bool = False
    points_to_redirect: bool = False
    points_to_dead_url: bool = False
    status: CanonicalChainStatus = CanonicalChainStatus.RESOLVED
    hops: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

class HygieneAnomalyType(str, Enum):
    TRAILING_SLASH = "TRAILING_SLASH"
    PROTOCOL_HTTP_HTTPS = "PROTOCOL_HTTP_HTTPS"
    WWW_SUBDOMAIN = "WWW_SUBDOMAIN"
    PATH_CASING = "PATH_CASING"
    QUERY_PARAM_ORDER = "QUERY_PARAM_ORDER"
    TRACKING_PARAMETERS = "TRACKING_PARAMETERS"
    MULTIPLE_SLASHES = "MULTIPLE_SLASHES"

class HygieneEvidenceType(str, Enum):
    IDENTICAL_EXTRACTED_TEXT = "IDENTICAL_EXTRACTED_TEXT"
    ACTUAL_DUPLICATE_CONTENT = "IDENTICAL_EXTRACTED_TEXT"
    REDIRECT_EQUIVALENT = "REDIRECT_EQUIVALENT"
    CANONICAL_EQUIVALENT = "CANONICAL_EQUIVALENT"
    POTENTIAL_DUPLICATE_REPRESENTATION = "POTENTIAL_DUPLICATE_REPRESENTATION"
    DISTINCT_CONTENT_VARIANT = "DISTINCT_CONTENT_VARIANT"

class HygieneAnomaly(BaseModel):
    anomaly_type: HygieneAnomalyType
    primary_url: str
    duplicate_url: str
    recommendation: str
    evidence_type: HygieneEvidenceType = HygieneEvidenceType.POTENTIAL_DUPLICATE_REPRESENTATION
    evidence_notes: List[str] = Field(default_factory=list)

class CrawlRecord(BaseModel):
    url: str
    normalized_url: str
    identity_url: str
    crawl_status: CrawlStatus
    depth: int
    parent_url: Optional[str] = None
    discovery_source: str = "internal_link"  # seed, internal_link, sitemap
    status_code: int = 0
    content_type: str = ""
    response_bytes: int = 0
    fetch_time_sec: float = 0.0
    retry_count: int = 0
    failure_reason: Optional[str] = None
    raw_html: Optional[str] = None
    discovered_links: List[str] = Field(default_factory=list)
    response_headers: Dict[str, Any] = Field(default_factory=dict)
    redirect_url: Optional[str] = None
    retrieval_readiness: Optional[RetrievalReadinessEvidence] = None
    answerability: Optional[AnswerabilityEvidence] = None

class PageSummary(BaseModel):
    """Summary of a single crawled page for site-wide analysis."""
    url: str
    status_code: int = 200
    title: str = ""
    title_length: int = 0
    meta_desc_length: int = 0
    h1_count: int = 0
    has_canonical: bool = False
    word_count: int = 0
    schema_types: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)

class LinkClassification(str, Enum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    SPECIAL = "SPECIAL"  # mailto, tel, javascript, data, etc.

class NodeOrphanStatus(str, Enum):
    ROOT = "ROOT"
    CONNECTED = "CONNECTED"
    POTENTIAL_ORPHAN = "POTENTIAL_ORPHAN"

class NodeCrawlState(str, Enum):
    CRAWLED = "CRAWLED"
    DISCOVERED_UNCRAWLED = "DISCOVERED_UNCRAWLED"

class ReachabilityInGraph(str, Enum):
    REACHABLE_FROM_ROOT = "REACHABLE_FROM_ROOT"
    UNREACHABLE_IN_OBSERVED_GRAPH = "UNREACHABLE_IN_OBSERVED_GRAPH"

class LinkGraphNode(BaseModel):
    url: str
    identity_url: str
    crawl_state: NodeCrawlState = NodeCrawlState.CRAWLED
    orphan_status: NodeOrphanStatus = NodeOrphanStatus.CONNECTED
    reachability: ReachabilityInGraph = ReachabilityInGraph.REACHABLE_FROM_ROOT
    status_code: Optional[int] = None
    click_depth: Optional[int] = None           # Shortest path from root; None if unreachable in observed graph
    inbound_internal_count: int = 0             # Unique internal referring pages (excl. self)
    outbound_internal_count: int = 0            # Unique internal target pages (excl. self)
    total_inbound_links: int = 0                # Total observed inbound links (including duplicates)
    total_outbound_links: int = 0               # Total observed outbound links (including duplicates)
    self_links_count: int = 0                   # Observed self-referencing links
    external_outbound_count: int = 0            # Outgoing links to external domains
    internal_equity_score: float = 0.0          # Internal PageRank score (sums to ~1.0)
    equity_percentile: float = 0.0              # 0.0 - 100.0% relative rank in graph
    is_dead_end: bool = False                   # True if outbound_internal_count == 0

class LinkGraphEdge(BaseModel):
    source_url: str
    target_url: str
    link_count: int = 1

class InternalLinkGraphSummary(BaseModel):
    root_url: str
    total_nodes: int = 0
    crawled_nodes_count: int = 0
    discovered_uncrawled_count: int = 0
    total_internal_edges: int = 0
    total_external_links_found: int = 0
    strongly_connected_components: int = 0
    weakly_connected_components: int = 0
    max_click_depth: int = 0
    deep_pages_count: int = 0                   # Click depth > 3
    potential_orphan_count: int = 0
    unreachable_in_observed_graph_count: int = 0
    dead_ends_count: int = 0
    nodes: Dict[str, LinkGraphNode] = Field(default_factory=dict)
    potential_orphans: List[str] = Field(default_factory=list)
    unreachable_in_observed_graph: List[str] = Field(default_factory=list)
    deep_pages: List[str] = Field(default_factory=list)
    dead_ends: List[str] = Field(default_factory=list)
    top_equity_pages: List[str] = Field(default_factory=list)
    lowest_equity_pages: List[str] = Field(default_factory=list)

# ==============================================================================
# Phase 8.3 — Internal-Link Intelligence Models
# ==============================================================================

class DiscoveredLinkItem(BaseModel):
    """Individual link extracted from page DOM with attributes and anchor text."""
    source_url: str
    target_url: str
    target_identity_url: str
    anchor_text: str = ""
    is_empty_anchor: bool = False
    is_image_link: bool = False
    image_alt: Optional[str] = None
    rel_attributes: List[str] = Field(default_factory=list)
    is_nofollow: bool = False
    is_sponsored: bool = False
    is_ugc: bool = False
    target_attribute: Optional[str] = None
    link_classification: LinkClassification = LinkClassification.INTERNAL

class GenericAnchorOccurrence(BaseModel):
    """Occurrence of generic or non-descriptive anchor text."""
    anchor_text: str
    target_url: str
    count: int = 1

class AnchorAmbiguityFinding(BaseModel):
    """Identical anchor text pointing to multiple distinct internal destinations."""
    anchor_text: str
    target_urls: List[str] = Field(default_factory=list)
    source_pages: List[str] = Field(default_factory=list)
    total_occurrences: int = 0
    observation: str = ""

class BrokenInternalLinkItem(BaseModel):
    """Internal link pointing to a failed or HTTP 4xx/5xx destination observed in crawl records."""
    source_url: str
    target_url: str
    anchor_text: str = ""
    status_code: Optional[int] = None
    failure_reason: Optional[str] = None

class LinkStructuralFindingType(str, Enum):
    NO_DISCOVERED_INCOMING_LINKS = "NO_DISCOVERED_INCOMING_LINKS"
    LIMITED_CONNECTIVITY = "LIMITED_CONNECTIVITY"
    ZERO_OUTLINKS = "ZERO_OUTLINKS"
    DEEP_CLICK_DEPTH = "DEEP_CLICK_DEPTH"
    BROKEN_TARGET = "BROKEN_TARGET"
    GENERIC_ANCHOR_USAGE = "GENERIC_ANCHOR_USAGE"
    AMBIGUOUS_ANCHOR = "AMBIGUOUS_ANCHOR"

class LinkStructuralFinding(BaseModel):
    """Evidence-backed structural finding or opportunity."""
    finding_type: LinkStructuralFindingType
    affected_url: str
    evidence: str
    observation: str
    recommendation: str

class LinkConcentrationTelemetry(BaseModel):
    """Link distribution and equity concentration telemetry."""
    total_internal_links: int = 0
    unique_internal_edges: int = 0
    top_linked_pages: List[Tuple[str, int]] = Field(default_factory=list)
    top_5_concentration_pct: float = 0.0

class SiteAnchorIntelligence(BaseModel):
    """Site-wide anchor text statistics and anomalies."""
    total_anchors_observed: int = 0
    unique_anchor_texts_count: int = 0
    empty_anchors_count: int = 0
    empty_anchor_sources: List[str] = Field(default_factory=list)
    generic_anchors_count: int = 0
    generic_anchor_occurrences: List[GenericAnchorOccurrence] = Field(default_factory=list)
    conflicting_anchors_count: int = 0
    conflicting_anchors: List[AnchorAmbiguityFinding] = Field(default_factory=list)
    top_anchor_texts: List[Tuple[str, int]] = Field(default_factory=list)

class InternalLinkEvidence(BaseModel):
    """Single-page internal link evidence."""
    url: str = ""
    status: EvidenceNature = EvidenceNature.OBSERVED
    total_links_found: int = 0
    internal_links_count: int = 0
    external_links_count: int = 0
    special_links_count: int = 0
    unique_internal_outlinks_count: int = 0
    unique_external_outlinks_count: int = 0
    nofollow_links_count: int = 0
    empty_anchor_count: int = 0
    generic_anchor_count: int = 0
    generic_anchors: List[GenericAnchorOccurrence] = Field(default_factory=list)
    sample_internal_links: List[DiscoveredLinkItem] = Field(default_factory=list)
    sample_external_links: List[DiscoveredLinkItem] = Field(default_factory=list)
    crawl_depth: Optional[int] = None
    inbound_internal_count: Optional[int] = None
    facts: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)

class OutlinkDiscoveryStatus(str, Enum):
    NO_DISCOVERED_OUTLINKS = "NO_DISCOVERED_OUTLINKS"
    HAS_DISCOVERED_OUTLINKS = "HAS_DISCOVERED_OUTLINKS"
    UNVERIFIED = "UNVERIFIED"

class PageLinkAnalysisRecord(BaseModel):
    """Normalized observable link data per page for benchmarking & link analysis comparison.
    Aligned with overlapping observable dimensions commonly benchmarked in link-analysis audits:
    crawl_depth, inlinks_count, unique_inlinks_count, outlinks_count, unique_outlinks_count,
    outlink_discovery_status, sample_inlink_sources, sample_outlink_targets, sample_inlink_anchors.
    Preserves strict partial-crawl semantics (NO_DISCOVERED_OUTLINKS vs HAS_DISCOVERED_OUTLINKS vs UNVERIFIED).
    """
    url: str
    crawl_depth: Optional[int] = None
    inlinks_count: int = 0
    unique_inlinks_count: int = 0
    outlinks_count: int = 0
    unique_outlinks_count: int = 0
    outlink_discovery_status: OutlinkDiscoveryStatus = OutlinkDiscoveryStatus.UNVERIFIED
    sample_inlink_sources: List[str] = Field(default_factory=list)
    sample_outlink_targets: List[str] = Field(default_factory=list)
    sample_inlink_anchors: List[str] = Field(default_factory=list)

class SiteInternalLinkIntelligence(BaseModel):
    """Site-wide multi-page internal link intelligence."""
    total_pages_evaluated: int = 0
    total_internal_links_discovered: int = 0
    total_unique_internal_edges: int = 0
    pages_with_zero_inlinks: List[str] = Field(default_factory=list)
    pages_with_weak_inlinks: List[str] = Field(default_factory=list)
    dead_end_pages: List[str] = Field(default_factory=list)
    deep_pages: List[str] = Field(default_factory=list)
    broken_internal_links_count: int = 0
    broken_internal_links: List[BrokenInternalLinkItem] = Field(default_factory=list)
    anchor_intelligence: SiteAnchorIntelligence = Field(default_factory=SiteAnchorIntelligence)
    link_concentration: LinkConcentrationTelemetry = Field(default_factory=LinkConcentrationTelemetry)
    structural_findings: List[LinkStructuralFinding] = Field(default_factory=list)
    inlink_sources_by_page: Dict[str, List[str]] = Field(default_factory=dict)
    outlink_targets_by_page: Dict[str, List[str]] = Field(default_factory=dict)
    inlink_counts_by_page: Dict[str, int] = Field(default_factory=dict)
    outlink_counts_by_page: Dict[str, int] = Field(default_factory=dict)
    crawl_depth_by_page: Dict[str, Optional[int]] = Field(default_factory=dict)
    page_internal_link_evidence: Dict[str, InternalLinkEvidence] = Field(default_factory=dict)
    page_link_records: Dict[str, PageLinkAnalysisRecord] = Field(default_factory=dict)


class SitemapFormat(str, Enum):
    URLSET = "URLSET"
    SITEMAPINDEX = "SITEMAPINDEX"
    MALFORMED = "MALFORMED"
    HTML_ERROR_PAGE = "HTML_ERROR_PAGE"
    UNKNOWN = "UNKNOWN"

class SitemapFetchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    HTTP_ERROR = "HTTP_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    MALFORMED_CONTENT = "MALFORMED_CONTENT"
    LOOP_DETECTED = "LOOP_DETECTED"
    MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED"
    MAX_SIZE_EXCEEDED = "MAX_SIZE_EXCEEDED"
    BLOCKED_BY_ROBOTS = "BLOCKED_BY_ROBOTS"

class SitemapDocumentRecord(BaseModel):
    url: str
    status: SitemapFetchStatus
    format: SitemapFormat = SitemapFormat.UNKNOWN
    status_code: Optional[int] = None
    fetch_time_sec: float = 0.0
    urls_found_count: int = 0
    child_sitemaps_count: int = 0
    child_sitemaps: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    depth: int = 0

class SitemapUrlRecord(BaseModel):
    loc: str
    identity_url: str
    source_sitemap: str
    lastmod: Optional[str] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None

class CrossSignalConflictType(str, Enum):
    SITEMAP_ROBOTS_BLOCKED = "SITEMAP_ROBOTS_BLOCKED"
    SITEMAP_NOINDEX_CONFLICT = "SITEMAP_NOINDEX_CONFLICT"
    SITEMAP_REDIRECT_CONFLICT = "SITEMAP_REDIRECT_CONFLICT"
    SITEMAP_ERROR_CONFLICT = "SITEMAP_ERROR_CONFLICT"
    SITEMAP_CANONICAL_ELSEWHERE = "SITEMAP_CANONICAL_ELSEWHERE"
    CANONICAL_TARGET_REDIRECT = "CANONICAL_TARGET_REDIRECT"
    CANONICAL_TARGET_DEAD = "CANONICAL_TARGET_DEAD"
    SITEMAP_ORPHAN_CANDIDATE = "SITEMAP_ORPHAN_CANDIDATE"
    SITEMAP_URL_UNCRAWLED = "SITEMAP_URL_UNCRAWLED"
    INTERNAL_URL_NOT_IN_SITEMAP = "INTERNAL_URL_NOT_IN_SITEMAP"

class CrossSignalConflictSeverity(str, Enum):
    """RankIntel diagnostic investigation priority (not an industry-standard penalty)."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class CrossSignalConflictRecord(BaseModel):
    url: str
    conflict_type: CrossSignalConflictType
    severity: CrossSignalConflictSeverity
    signal_a_source: str
    signal_a_state: str
    signal_b_source: str
    signal_b_state: str
    evidence_nature: EvidenceNature = EvidenceNature.OBSERVED
    summary: str
    recommended_reconciliation: str

class SitemapReconciliationSummary(BaseModel):
    total_sitemaps_discovered: int = 0
    total_sitemaps_parsed: int = 0
    total_sitemap_urls_discovered: int = 0
    total_unique_sitemap_urls: int = 0
    crawled_sitemap_urls_count: int = 0
    uncrawled_sitemap_urls_count: int = 0
    internal_urls_missing_from_sitemap_count: int = 0
    conflicts_count_by_type: Dict[str, int] = Field(default_factory=dict)
    conflicts_count_by_severity: Dict[str, int] = Field(default_factory=dict)
    sitemap_documents: List[SitemapDocumentRecord] = Field(default_factory=list)
    sitemap_urls: Dict[str, SitemapUrlRecord] = Field(default_factory=dict)
    conflicts: List[CrossSignalConflictRecord] = Field(default_factory=list)
    uncrawled_sitemap_urls: List[str] = Field(default_factory=list)
    internal_urls_missing_from_sitemap: List[str] = Field(default_factory=list)

# ==============================================================================
# Phase 9.1 - Search Signal Intelligence Models (Layer A: On-Site Evidenced Signals)
# ==============================================================================

class SearchSignalStatementType(str, Enum):
    FACT = "FACT"
    ANALYSIS = "ANALYSIS"

class SearchSignalConfidence(str, Enum):
    DIRECT = "DIRECT"        # Directly observed in primary structural elements (Title, H1, Meta, Schema, Entity)
    SUPPORTED = "SUPPORTED"  # Observed across multiple structural locations or repeated in main editorial content
    WEAK = "WEAK"            # Isolated peripheral mention (e.g. single occurrence in URL or alt text only)

class SearchSignalLocation(str, Enum):
    TITLE = "TITLE"
    META_DESCRIPTION = "META_DESCRIPTION"
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"
    MAIN_CONTENT = "MAIN_CONTENT"
    URL_PATH = "URL_PATH"
    IMAGE_ALT = "IMAGE_ALT"
    STRUCTURED_DATA = "STRUCTURED_DATA"
    ENTITY = "ENTITY"

class SearchSignalOccurrence(BaseModel):
    location: SearchSignalLocation
    raw_text: str
    count: int = 1
    attribute_or_tag: Optional[str] = None

class SearchSignalItem(BaseModel):
    term: str
    raw_term: str
    signal_type: SearchSignalStatementType = SearchSignalStatementType.FACT
    category: str
    locations: List[SearchSignalLocation] = Field(default_factory=list)
    occurrences: List[SearchSignalOccurrence] = Field(default_factory=list)
    total_occurrences: int = 1
    prominence_locations: List[str] = Field(default_factory=list)
    is_entity: bool = False
    entity_type: Optional[str] = None
    confidence: SearchSignalConfidence = SearchSignalConfidence.SUPPORTED
    provenance: str = "search_signal_engine"

class SearchSignalEvidence(BaseModel):
    """Comprehensive single-page Search Signal Intelligence evidence (Layer A)."""
    url: str = ""
    engine_source: str = "search_signal_engine"
    status: str = "success"
    total_signals_detected: int = 0
    unique_terms_count: int = 0
    signals: List[SearchSignalItem] = Field(default_factory=list)
    title_terms: List[str] = Field(default_factory=list)
    meta_description_terms: List[str] = Field(default_factory=list)
    heading_terms: List[str] = Field(default_factory=list)
    main_content_top_terms: List[Dict[str, Any]] = Field(default_factory=list)
    entity_terms: List[Dict[str, Any]] = Field(default_factory=list)
    url_path_terms: List[str] = Field(default_factory=list)
    image_alt_terms: List[str] = Field(default_factory=list)
    structured_data_terms: List[str] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class RecurringConceptItem(BaseModel):
    """Site-wide recurring concept observed across crawled pages."""
    concept: str
    normalized_concept: str
    pages_count: int = 0
    page_urls: List[str] = Field(default_factory=list)
    prominent_pages: List[str] = Field(default_factory=list)
    total_occurrences: int = 0
    observed_locations: List[str] = Field(default_factory=list)
    is_entity: bool = False
    entity_type: Optional[str] = None
    signal_nature: SearchSignalStatementType = SearchSignalStatementType.ANALYSIS

class SiteSearchSignalIntelligence(BaseModel):
    """Site-wide search signal intelligence aggregating recurring evidenced concepts."""
    total_pages_evaluated: int = 0
    total_unique_concepts: int = 0
    recurring_concepts_count: int = 0
    recurring_concepts: List[RecurringConceptItem] = Field(default_factory=list)
    site_top_evidenced_terms: List[Dict[str, Any]] = Field(default_factory=list)
    page_signal_evidence: Dict[str, SearchSignalEvidence] = Field(default_factory=dict)
    terminology_nature: str = "OBSERVED_WEBSITE_TERMINOLOGY"
    external_query_data_status: str = "NOT_AVAILABLE_LAYER_A"
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

# ==============================================================================
# Phase 9.2 - Keyword & Topic Intelligence Models (Layer A: On-Site Concept Grouping)
# ==============================================================================

class TopicMembershipType(str, Enum):
    EXACT = "EXACT"
    PHRASE_CONTAINMENT = "PHRASE_CONTAINMENT"
    TOKEN_OVERLAP = "TOKEN_OVERLAP"
    STRUCTURAL_CO_OCCURRENCE = "STRUCTURAL_CO_OCCURRENCE"
    ENTITY_MEMBER = "ENTITY_MEMBER"

class TopicRelationshipType(str, Enum):
    LEXICAL_OVERLAP = "LEXICAL_OVERLAP"
    CO_OCCURRENCE = "CO_OCCURRENCE"
    SHARED_ENTITY = "SHARED_ENTITY"
    SUBTOPIC_OF = "SUBTOPIC_OF"

class TopicTermMembership(BaseModel):
    """Association between an observed term and a derived concept topic."""
    term: str
    normalized_term: str
    membership_type: TopicMembershipType = TopicMembershipType.EXACT
    occurrences_count: int = 1
    structural_locations: List[str] = Field(default_factory=list)
    confidence: str = "SUPPORTED"
    provenance: str = "search_signal_engine"

class TopicRelationship(BaseModel):
    """Deterministic relationship between two derived concept topics."""
    topic_a: str
    topic_b: str
    relationship_type: TopicRelationshipType = TopicRelationshipType.LEXICAL_OVERLAP
    evidence_nature: str = "ANALYSIS"
    co_occurrence_pages_count: int = 0
    supporting_evidence: List[str] = Field(default_factory=list)

class TopicEvidence(BaseModel):
    """Deterministic derived concept topic supported by observable on-site terms and telemetry."""
    topic_name: str
    normalized_name: str
    topic_nature: str = "DERIVED_CONCEPT_GROUP"
    evidence_nature: str = "ANALYSIS"
    supporting_terms: List[TopicTermMembership] = Field(default_factory=list)
    pages_count: int = 1
    page_urls: List[str] = Field(default_factory=list)
    occurrences_count: int = 0
    structural_presence_count: int = 0
    title_or_h1_presence: bool = False
    observed_locations: List[str] = Field(default_factory=list)
    associated_entities: List[str] = Field(default_factory=list)
    provenance: str = "topic_intelligence_engine"

class PageTopicIntelligence(BaseModel):
    """Page-level Topic Intelligence containing derived concepts, memberships, and relationships."""
    url: str = ""
    engine_source: str = "topic_intelligence_engine"
    status: str = "success"  # success, error, skipped, unavailable
    error_message: Optional[str] = None
    total_topics_derived: int = 0
    total_terms_mapped: int = 0
    topics: List[TopicEvidence] = Field(default_factory=list)
    relationships: List[TopicRelationship] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class SiteTopicIntelligence(BaseModel):
    """Site-wide Topic Intelligence aggregating recurring observed concepts across crawled pages."""
    status: str = "success"  # success, error, partial
    error_message: Optional[str] = None
    total_pages_evaluated: int = 0
    is_partial_crawl: bool = False
    completeness_disclaimer: str = ""
    total_topics_count: int = 0
    recurring_topics_count: int = 0
    topics: List[TopicEvidence] = Field(default_factory=list)
    relationships: List[TopicRelationship] = Field(default_factory=list)
    page_topic_intelligence: Dict[str, PageTopicIntelligence] = Field(default_factory=dict)
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

# ==============================================================================
# Phase 9.3 - Query-Page Mapping Models (Layer A: On-Site Concept to Page Mapping)
# ==============================================================================

class QueryPageEvidence(BaseModel):
    """Deterministic single-page mapping for an observed on-site concept or evidenced topic."""
    concept: str
    normalized_concept: str
    concept_nature: str = "OBSERVED_CONCEPT"  # "OBSERVED_CONCEPT" or "EVIDENCED_TOPIC"
    url: str = ""
    evidence_strength: SearchSignalConfidence = SearchSignalConfidence.SUPPORTED  # DIRECT, SUPPORTED, WEAK
    evidence_locations: List[str] = Field(default_factory=list)  # TITLE, H1, H2, H3, MAIN_CONTENT, URL_PATH, STRUCTURED_DATA, ENTITY
    occurrences_count: int = 1
    has_title_or_h1: bool = False
    is_exact_term_match: bool = False
    is_topic_membership: bool = False
    associated_entities: List[str] = Field(default_factory=list)
    structured_data_types: List[str] = Field(default_factory=list)
    url_path_match: bool = False
    supporting_snippets: List[str] = Field(default_factory=list)  # Bounded to max 5 snippets
    provenance: str = "query_page_mapping_engine"

class PageQueryEvidence(BaseModel):
    """Aggregated deterministic concept-to-page mappings for a single crawled page."""
    url: str = ""
    engine_source: str = "query_page_mapping_engine"
    status: str = "success"  # success, error, skipped
    error_message: Optional[str] = None
    total_concepts_mapped: int = 0
    direct_concepts_count: int = 0
    supported_concepts_count: int = 0
    weak_concepts_count: int = 0
    mapped_concepts: List[QueryPageEvidence] = Field(default_factory=list)
    primary_concepts: List[str] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class QueryPageRelationship(BaseModel):
    """Deterministic inverse mapping from an observed concept to its supporting crawled pages."""
    concept: str
    normalized_concept: str
    concept_nature: str = "OBSERVED_CONCEPT"
    pages_count: int = 0
    page_urls: List[str] = Field(default_factory=list)
    direct_pages: List[str] = Field(default_factory=list)
    supported_pages: List[str] = Field(default_factory=list)
    weak_pages: List[str] = Field(default_factory=list)
    evidence_locations: List[str] = Field(default_factory=list)
    total_occurrences: int = 0
    title_or_h1_pages: List[str] = Field(default_factory=list)
    associated_entities: List[str] = Field(default_factory=list)
    supporting_pages: List[QueryPageEvidence] = Field(default_factory=list)  # Bounded to top 10 pages
    overlap_status: Optional[str] = None  # "POTENTIAL_MULTI_PAGE_TOPIC_OVERLAP" if >=2 strong pages
    overlap_rationale: Optional[str] = None
    provenance: str = "query_page_mapping_engine"

class SiteQueryPageIntelligence(BaseModel):
    """Site-wide query-page intelligence aggregating concept-to-page and page-to-concept mappings."""
    status: str = "success"  # success, error, partial
    error_message: Optional[str] = None
    total_pages_evaluated: int = 0
    is_partial_crawl: bool = False
    completeness_disclaimer: str = ""
    total_concepts_mapped: int = 0
    multi_page_overlap_count: int = 0
    concept_relationships: List[QueryPageRelationship] = Field(default_factory=list)
    page_query_evidence: Dict[str, PageQueryEvidence] = Field(default_factory=dict)
    overlaps: List[QueryPageRelationship] = Field(default_factory=list)
    terminology_nature: str = "OBSERVED_WEBSITE_EVIDENCE"
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

# ==============================================================================
# Phase 9.4 - Search Intent & Topic Coverage Models (Layer A: On-Site Intent Signals)
# ==============================================================================

class SearchIntentCategory(str, Enum):
    INFORMATIONAL = "informational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"
    LOCAL = "local"
    MIXED = "mixed"
    UNSPECIFIED = "unspecified"

class IntentEvidenceItem(BaseModel):
    """Observable structural or textual evidence item supporting an intent hypothesis."""
    intent_category: SearchIntentCategory
    signal_type: str  # e.g. "EXPLANATORY_HEADING", "FAQ_STRUCTURE", "PRICING_TABLE", "CALL_TO_ACTION", "TRANSACTION_FORM", "POSTAL_ADDRESS", "LOCAL_PHONE"
    evidence_term: str
    evidence_location: str  # e.g. "TITLE", "H1", "H2", "H3", "CTA_ELEMENT", "SCHEMA", "URL_PATH", "BODY_CONTENT", "FOOTER"
    supporting_snippet: str
    confidence: SearchSignalConfidence = SearchSignalConfidence.SUPPORTED
    provenance: str = "search_intent_engine"

class PageIntentEvidence(BaseModel):
    """Inferred search intent signals supported by observable on-site single-page content."""
    url: str = ""
    engine_source: str = "search_intent_engine"
    status: str = "success"  # success, error, skipped
    error_message: Optional[str] = None
    primary_observed_intent_signal: SearchIntentCategory = SearchIntentCategory.UNSPECIFIED
    secondary_observed_intent_signals: List[SearchIntentCategory] = Field(default_factory=list)
    intent_counts: Dict[str, int] = Field(default_factory=dict)
    evidence_items: List[IntentEvidenceItem] = Field(default_factory=list)
    associated_topics: List[str] = Field(default_factory=list)
    corroboration_notes: List[str] = Field(default_factory=list)
    terminology_nature: str = "INFERRED_FROM_ON_SITE_EVIDENCE"
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class TopicCoverageEvidence(BaseModel):
    """Deterministic topic coverage aggregated across crawled pages with intent alignment."""
    topic_name: str
    normalized_name: str
    coverage_nature: str = "OBSERVED_TOPIC_COVERAGE"
    pages_count: int = 0
    page_urls: List[str] = Field(default_factory=list)
    primary_pages: List[str] = Field(default_factory=list)
    intent_breakdown: Dict[str, int] = Field(default_factory=dict)
    observed_dominant_intent: SearchIntentCategory = SearchIntentCategory.UNSPECIFIED
    associated_entities: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    provenance: str = "site_topic_coverage_analyzer"

class SiteTopicCoverageIntelligence(BaseModel):
    """Site-wide topic coverage intelligence across crawled pages."""
    status: str = "success"  # success, error, partial
    error_message: Optional[str] = None
    total_pages_evaluated: int = 0
    is_partial_crawl: bool = False
    completeness_disclaimer: str = ""
    total_topics_covered: int = 0
    covered_topics: List[TopicCoverageEvidence] = Field(default_factory=list)
    intent_distribution: Dict[str, int] = Field(default_factory=dict)
    page_intent_evidence: Dict[str, PageIntentEvidence] = Field(default_factory=dict)
    multi_intent_topics: List[str] = Field(default_factory=list)
    terminology_nature: str = "OBSERVED_WEBSITE_EVIDENCE"
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

# ==============================================================================
# Phase 9.5 - Cannibalization & Search Gaps Models (Layer A: On-Site Overlap & Gap Intelligence)
# ==============================================================================

class CannibalizationSignalType(str, Enum):
    POTENTIAL_CANNIBALIZATION_SIGNAL = "POTENTIAL_CANNIBALIZATION_SIGNAL"
    OBSERVED_TOPIC_OVERLAP = "OBSERVED_TOPIC_OVERLAP"
    OBSERVED_INTENT_OVERLAP = "OBSERVED_INTENT_OVERLAP"

class TopicGapType(str, Enum):
    OBSERVED_TOPIC_GAP = "OBSERVED_TOPIC_GAP"
    CONTENT_DEPTH_ASYMMETRY = "CONTENT_DEPTH_ASYMMETRY"
    STRUCTURAL_HEADING_GAP = "STRUCTURAL_HEADING_GAP"

class PotentialCannibalizationItem(BaseModel):
    """Observable on-site multi-page competition signal supported by multiple independent evidence dimensions."""
    topic: str
    normalized_topic: str
    competing_urls: List[str] = Field(default_factory=list)  # >= 2 pages
    signal_type: CannibalizationSignalType = CannibalizationSignalType.POTENTIAL_CANNIBALIZATION_SIGNAL
    evidence_strength: SearchSignalConfidence = SearchSignalConfidence.SUPPORTED
    shared_intent: SearchIntentCategory = SearchIntentCategory.UNSPECIFIED
    title_overlap_ratio: float = 0.0
    h1_overlap_ratio: float = 0.0
    shared_concepts: List[str] = Field(default_factory=list)  # Bounded to max 8
    title_h1_snippets: Dict[str, str] = Field(default_factory=dict)  # url -> title/H1 summary
    rationale: str = ""
    recommendation: str = ""  # Explicitly includes REQUIRES_EXTERNAL_SEARCH_VALIDATION
    provenance: str = "cannibalization_analyzer"

class ObservableTopicGapItem(BaseModel):
    """Deterministic on-site coverage or structural asymmetry between related pages or topics."""
    topic: str
    normalized_topic: str
    source_url: str = ""
    related_url: str = ""
    gap_type: TopicGapType = TopicGapType.OBSERVED_TOPIC_GAP
    covered_concepts: List[str] = Field(default_factory=list)  # Bounded to max 6
    missing_concepts: List[str] = Field(default_factory=list)  # Bounded to max 6
    gap_nature: str = "OBSERVED_TOPIC_GAP"
    rationale: str = ""
    recommendation: str = ""  # Explicitly includes REQUIRES_EXTERNAL_SEARCH_VALIDATION
    provenance: str = "search_gap_analyzer"

class PageCannibalizationEvidence(BaseModel):
    """Observable cannibalization signals and topic gaps relevant to a single page."""
    url: str = ""
    engine_source: str = "cannibalization_analyzer"
    status: str = "success"  # success, error, skipped
    error_message: Optional[str] = None
    potential_signals: List[PotentialCannibalizationItem] = Field(default_factory=list)
    observable_gaps: List[ObservableTopicGapItem] = Field(default_factory=list)
    terminology_nature: str = "OBSERVED_WEBSITE_EVIDENCE"
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class SiteCannibalizationIntelligence(BaseModel):
    """Site-wide cannibalization and search gap intelligence across crawled pages."""
    status: str = "success"  # success, error, partial
    error_message: Optional[str] = None
    total_pages_evaluated: int = 0
    is_partial_crawl: bool = False
    completeness_disclaimer: str = ""
    potential_cannibalization_signals: List[PotentialCannibalizationItem] = Field(default_factory=list)
    observable_topic_gaps: List[ObservableTopicGapItem] = Field(default_factory=list)
    competing_topics_count: int = 0
    total_gaps_identified: int = 0
    terminology_nature: str = "OBSERVED_WEBSITE_EVIDENCE"
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    @property
    def potential_signals(self) -> List[PotentialCannibalizationItem]:
        return self.potential_cannibalization_signals

# ==============================================================================
# Phase 10.1 — AI Access & Retrieval Readiness Models
# ==============================================================================

class RetrievalReadinessStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class BotPurpose(str, Enum):
    SEARCH_INDEX = "search_index"
    AI_TRAINING = "ai_training"
    USER_FETCH = "user_fetch"
    RESEARCH_PREVIEW = "research_preview"

class SnippetControlStatus(str, Enum):
    ALLOWED = "ALLOWED"
    NOSNIPPET = "NOSNIPPET"
    MAX_SNIPPET = "MAX_SNIPPET"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class SnippetControlEvidence(BaseModel):
    status: SnippetControlStatus = SnippetControlStatus.ALLOWED
    has_nosnippet: bool = False
    nosnippet_sources: List[str] = Field(default_factory=list)
    max_snippet: Optional[int] = None
    max_snippet_source: Optional[str] = None
    max_image_preview: Optional[str] = None
    max_video_preview: Optional[int] = None
    has_data_nosnippet: bool = False
    data_nosnippet_count: int = 0
    data_nosnippet_sample_selectors: List[str] = Field(default_factory=list)

class IndexabilityInteractionEvidence(BaseModel):
    indexability_status: IndexabilityStatus = IndexabilityStatus.INDEXABLE
    has_noindex: bool = False
    noindex_sources: List[str] = Field(default_factory=list)
    has_nofollow: bool = False
    canonical_url: Optional[str] = None
    canonical_signal: str = "MISSING"
    canonical_conflict: bool = False
    interaction_summary: str = ""

class ContentAvailabilityEvidence(BaseModel):
    raw_html_available: bool = False
    rendered_html_available: bool = False
    raw_word_count: int = 0
    rendered_word_count: int = 0
    word_count_delta: int = 0
    significant_content_difference: bool = False
    js_rendering_impact: str = ""

class WafChallengeEvidence(BaseModel):
    is_blocked: bool = False
    status_code: int = 0
    status: RetrievalReadinessStatus = RetrievalReadinessStatus.ALLOWED
    barrier_type: Optional[str] = None
    waf_or_challenge_detected: bool = False
    waf_provider: Optional[str] = None
    challenge_detected: bool = False
    challenge_indicators: List[str] = Field(default_factory=list)

class BotRetrievalAccessRecord(BaseModel):
    bot_name: str
    company: str
    purpose: BotPurpose
    category_label: str
    robots_access: RetrievalReadinessStatus = RetrievalReadinessStatus.UNKNOWN
    indexability: IndexabilityStatus = IndexabilityStatus.UNKNOWN
    snippet_control: SnippetControlStatus = SnippetControlStatus.NOT_APPLICABLE
    waf_network_status: RetrievalReadinessStatus = RetrievalReadinessStatus.ALLOWED
    effective_status: RetrievalReadinessStatus = RetrievalReadinessStatus.UNKNOWN
    rule_source: str = "unknown"
    matched_directive: Optional[str] = None
    line_number: Optional[int] = None
    raw_pattern: Optional[str] = None
    notes: List[str] = Field(default_factory=list)

class RetrievalReadinessEvidence(BaseModel):
    url: str = ""
    engine_source: str = "retrieval_readiness_engine"
    http_status: int = 0
    content_availability: ContentAvailabilityEvidence = Field(default_factory=ContentAvailabilityEvidence)
    waf_challenge: WafChallengeEvidence = Field(default_factory=WafChallengeEvidence)
    snippet_controls: SnippetControlEvidence = Field(default_factory=SnippetControlEvidence)
    indexability_interaction: IndexabilityInteractionEvidence = Field(default_factory=IndexabilityInteractionEvidence)
    bot_access_records: Dict[str, BotRetrievalAccessRecord] = Field(default_factory=dict)
    total_bots_evaluated: int = 0
    search_index_allowed_count: int = 0
    ai_training_allowed_count: int = 0
    user_fetch_allowed_count: int = 0
    blocked_by_waf_count: int = 0
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class SiteRetrievalReadinessIntelligence(BaseModel):
    status: str = "success"
    total_pages_evaluated: int = 0
    is_partial_crawl: bool = False
    completeness_disclaimer: str = ""
    pages_with_waf_challenge: List[str] = Field(default_factory=list)
    pages_requiring_js: List[str] = Field(default_factory=list)
    pages_with_nosnippet: List[str] = Field(default_factory=list)
    pages_with_data_nosnippet: List[str] = Field(default_factory=list)
    pages_with_noindex: List[str] = Field(default_factory=list)
    pages_with_canonical_conflicts: List[str] = Field(default_factory=list)
    bot_disallowed_counts: Dict[str, int] = Field(default_factory=dict)
    page_readiness_evidence: Dict[str, RetrievalReadinessEvidence] = Field(default_factory=dict)
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class AnswerableUnitType(str, Enum):
    DEFINITION = "DEFINITION"
    DIRECT_ANSWER = "DIRECT_ANSWER"
    SERVICE_DESCRIPTION = "SERVICE_DESCRIPTION"
    PROCEDURE_STEPS = "PROCEDURE_STEPS"
    SPECIFICATION = "SPECIFICATION"
    REQUIREMENTS_ELIGIBILITY = "REQUIREMENTS_ELIGIBILITY"
    FAQ = "FAQ"
    LIST = "LIST"
    TABLE = "TABLE"
    COMPARISON = "COMPARISON"
    LOCATION_CONTACT = "LOCATION_CONTACT"
    DATE_POLICY = "DATE_POLICY"
    FACTUAL_STATEMENT = "FACTUAL_STATEMENT"
    EXAMPLE = "EXAMPLE"

class ClarityStatus(str, Enum):
    OBSERVED = "OBSERVED"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"

class TopicExplanationStatus(str, Enum):
    EXPLAINED = "EXPLAINED"
    MENTIONED_ONLY = "MENTIONED_ONLY"
    UNSUPPORTED_HEADING = "UNSUPPORTED_HEADING"
    ABSENT = "ABSENT"

class AnswerableInformationUnit(BaseModel):
    unit_id: str
    unit_type: AnswerableUnitType
    secondary_types: List[AnswerableUnitType] = Field(default_factory=list)
    topic: Optional[str] = None
    section_heading: Optional[str] = None
    heading_level: Optional[str] = None
    snippet: str
    content_location: str
    structural_type: str
    supporting_context: Optional[str] = None
    is_explicit: bool = True
    source: str = "raw_html"
    extraction_method: str = "dom_structure"
    bounded_evidence: str = ""
    confidence: str = "high"

class InformationClarityAssessment(BaseModel):
    heading_content_relationship: ClarityStatus = ClarityStatus.UNAVAILABLE
    heading_content_notes: List[str] = Field(default_factory=list)
    question_answer_patterns: ClarityStatus = ClarityStatus.UNAVAILABLE
    question_answer_notes: List[str] = Field(default_factory=list)
    definition_patterns: ClarityStatus = ClarityStatus.UNAVAILABLE
    definition_notes: List[str] = Field(default_factory=list)
    step_list_structure: ClarityStatus = ClarityStatus.UNAVAILABLE
    step_list_notes: List[str] = Field(default_factory=list)
    table_availability: ClarityStatus = ClarityStatus.UNAVAILABLE
    table_notes: List[str] = Field(default_factory=list)
    unsupported_concepts: List[str] = Field(default_factory=list)
    buried_facts: List[str] = Field(default_factory=list)
    obscured_or_fragmented_items: List[str] = Field(default_factory=list)

class TopicAnswerabilityLink(BaseModel):
    topic_name: str
    status: TopicExplanationStatus = TopicExplanationStatus.MENTIONED_ONLY
    section_heading: Optional[str] = None
    associated_unit_ids: List[str] = Field(default_factory=list)
    unit_types: List[AnswerableUnitType] = Field(default_factory=list)
    explanation_snippet: Optional[str] = None
    is_explicit: bool = False
    evidence_notes: List[str] = Field(default_factory=list)

class AnswerabilityEvidence(BaseModel):
    url: str = ""
    engine_source: str = "answerability_engine"
    total_units_detected: int = 0
    units_by_type: Dict[str, int] = Field(default_factory=dict)
    units: List[AnswerableInformationUnit] = Field(default_factory=list)
    clarity_assessment: InformationClarityAssessment = Field(default_factory=InformationClarityAssessment)
    topic_links: List[TopicAnswerabilityLink] = Field(default_factory=list)
    explained_topics_count: int = 0
    mentioned_only_topics_count: int = 0
    unsupported_heading_topics_count: int = 0
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class SiteAnswerabilityIntelligence(BaseModel):
    status: str = "success"
    total_pages_evaluated: int = 0
    is_partial_crawl: bool = False
    completeness_disclaimer: str = ""
    total_site_units_detected: int = 0
    site_units_by_type: Dict[str, int] = Field(default_factory=dict)
    pages_with_faq: List[str] = Field(default_factory=list)
    pages_with_definitions: List[str] = Field(default_factory=list)
    pages_with_steps: List[str] = Field(default_factory=list)
    pages_with_tables: List[str] = Field(default_factory=list)
    pages_with_unsupported_concepts: List[str] = Field(default_factory=list)
    page_answerability_evidence: Dict[str, AnswerabilityEvidence] = Field(default_factory=dict)
    facts: List[str] = Field(default_factory=list)
    analyses: List[str] = Field(default_factory=list)

class SiteCrawlResult(BaseModel):
    """Aggregated multi-page crawl intelligence."""
    completeness_status: str = "CRAWL_COMPLETE"
    pages_crawled: int = 0
    pages_discovered: int = 0
    pages_queued: int = 0
    pages_blocked: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    pages_non_html: int = 0
    pages_duplicate: int = 0
    remaining_frontier: int = 0
    sitemap_only_urls: int = 0
    rendered_only_urls: int = 0
    navigation_only_urls: int = 0
    
    pages_with_issues: int = 0
    crawl_depth: int = 2
    crawl_duration_sec: float = 0.0
    status_counts: Dict[str, int] = Field(default_factory=dict)
    crawl_records: List[CrawlRecord] = Field(default_factory=list)
    pages: List[PageSummary] = Field(default_factory=list)
    site_wide_issues: List[str] = Field(default_factory=list)
    orphan_pages: List[str] = Field(default_factory=list)
    broken_links: List[str] = Field(default_factory=list)
    duplicate_titles: List[str] = Field(default_factory=list)
    missing_h1_pages: List[str] = Field(default_factory=list)
    thin_content_pages: List[str] = Field(default_factory=list)
    pages_without_meta_desc: List[str] = Field(default_factory=list)
    search_eligibility: Dict[str, SearchEligibilityRecord] = Field(default_factory=dict)
    redirect_chains: Dict[str, RedirectChainRecord] = Field(default_factory=dict)
    canonical_chains: Dict[str, CanonicalChainRecord] = Field(default_factory=dict)
    hygiene_anomalies: List[HygieneAnomaly] = Field(default_factory=list)
    link_graph: Optional[InternalLinkGraphSummary] = None
    sitemap_reconciliation: Optional[SitemapReconciliationSummary] = None
    bot_matrix: Optional[BotMatrixReport] = None
    content_intelligence: Optional[SiteContentIntelligence] = None
    entity_intelligence: Optional[SiteEntityIntelligence] = None
    internal_link_intelligence: Optional[SiteInternalLinkIntelligence] = None
    search_signal_intelligence: Optional[SiteSearchSignalIntelligence] = None
    topic_intelligence: Optional[SiteTopicIntelligence] = None
    query_page_intelligence: Optional[SiteQueryPageIntelligence] = None
    topic_coverage_intelligence: Optional[SiteTopicCoverageIntelligence] = None
    cannibalization_intelligence: Optional[SiteCannibalizationIntelligence] = None
    retrieval_readiness_intelligence: Optional[SiteRetrievalReadinessIntelligence] = None
    answerability_intelligence: Optional[SiteAnswerabilityIntelligence] = None

class EngineResult(BaseModel):
    engine_name: str
    status: str = "success"  # success, error, skipped
    execution_time_sec: float = 0.0
    error_message: Optional[str] = None
    on_page: Optional[OnPageEvidence] = None
    robots: Optional[RobotsEvidence] = None
    schema_data: Optional[SchemaEvidence] = None
    geo_aeo: Optional[GeoAeoEvidence] = None
    trust_stack: Optional[TrustStackResult] = None
    performance: Optional[PerformanceEvidence] = None
    security: Optional[SecurityEvidence] = None
    image_seo: Optional[ImageSEOEvidence] = None
    accessibility: Optional[AccessibilityEvidence] = None
    content: Optional[ContentEvidence] = None
    entity: Optional[EntityEvidence] = None
    internal_link: Optional[InternalLinkEvidence] = None
    search_signal: Optional[SearchSignalEvidence] = None
    topic_intelligence: Optional[PageTopicIntelligence] = None
    query_page: Optional[PageQueryEvidence] = None
    search_intent: Optional[PageIntentEvidence] = None
    cannibalization: Optional[PageCannibalizationEvidence] = None
    cloud_intelligence: Optional[CloudIntelligenceEvidence] = None
    retrieval_readiness: Optional[RetrievalReadinessEvidence] = None
    answerability: Optional[AnswerabilityEvidence] = None
    raw_html: Optional[str] = None  # Post-JS rendered HTML from crawl4ai; used by TrustEvaluator and GeoEngine

class ConflictFinding(BaseModel):
    category: str
    feature: str
    description: str
    engine_a_finding: str
    engine_b_finding: str
    interpretation: str
    severity: str  # HIGH, MEDIUM, LOW

class PrioritizedAction(BaseModel):
    level: str  # CRITICAL, HIGH, MEDIUM, GEO_WIN
    title: str
    finding: str
    rationale: str
    engine_confidence: str
    fix_snippet: Optional[str] = None

class SynthesisReport(BaseModel):
    url: str
    domain: str
    timestamp: str
    overall_health_score: int = 0
    geo_readiness_score: int = 0
    technical_health_score: int = 0
    trust_score: int = 0
    performance_score: int = 0
    security_score: int = 0
    image_seo_score: int = 0
    accessibility_score: int = 0
    keyword_score: int = 0
    site_health_score: int = 0
    score_formula_mode: str = "4_engine"  # "3_engine", "4_engine", "5_engine"
    engines_executed: List[str] = Field(default_factory=list)
    conflicts_detected: List[ConflictFinding] = Field(default_factory=list)
    prioritized_actions: List[PrioritizedAction] = Field(default_factory=list)
    provenance: List[EvidenceProvenanceTag] = Field(default_factory=list)
    
    # Unified reconciled states
    unified_on_page: OnPageEvidence = Field(default_factory=OnPageEvidence)
    unified_robots: RobotsEvidence = Field(default_factory=RobotsEvidence)
    unified_schema: SchemaEvidence = Field(default_factory=SchemaEvidence)
    unified_geo: GeoAeoEvidence = Field(default_factory=GeoAeoEvidence)
    unified_trust: TrustStackResult = Field(default_factory=TrustStackResult)
    unified_performance: PerformanceEvidence = Field(default_factory=PerformanceEvidence)
    unified_security: SecurityEvidence = Field(default_factory=SecurityEvidence)
    unified_image_seo: ImageSEOEvidence = Field(default_factory=ImageSEOEvidence)
    unified_accessibility: AccessibilityEvidence = Field(default_factory=AccessibilityEvidence)
    unified_content: ContentEvidence = Field(default_factory=ContentEvidence)
    unified_entity: EntityEvidence = Field(default_factory=EntityEvidence)
    unified_internal_link: InternalLinkEvidence = Field(default_factory=InternalLinkEvidence)
    unified_search_signal: SearchSignalEvidence = Field(default_factory=SearchSignalEvidence)
    unified_topic: PageTopicIntelligence = Field(default_factory=PageTopicIntelligence)
    unified_query_page: PageQueryEvidence = Field(default_factory=PageQueryEvidence)
    unified_search_intent: PageIntentEvidence = Field(default_factory=PageIntentEvidence)
    unified_cannibalization: PageCannibalizationEvidence = Field(default_factory=PageCannibalizationEvidence)
    cloud_intelligence: CloudIntelligenceEvidence = Field(default_factory=CloudIntelligenceEvidence)
    unified_retrieval_readiness: Optional[RetrievalReadinessEvidence] = None
    unified_answerability: Optional[AnswerabilityEvidence] = None
    site_crawl: Optional[SiteCrawlResult] = None
    
    # Generated fixes
    fixes: Dict[str, str] = Field(default_factory=dict)

class GapAction(BaseModel):
    category: str
    title: str
    rationale: str
    impact_points: int
    priority: str  # HIGH, MEDIUM, LOW
    winning_advantage: str
    remediation_suggestion: str

class GapDelta(BaseModel):
    category: str
    target_a_val: Any
    target_b_val: Any
    winner: str  # url1, url2, or TIE
    impact: str

class ComparisonReport(BaseModel):
    target_a_url: str
    target_b_url: str
    timestamp: str
    target_a_report: SynthesisReport
    target_b_report: SynthesisReport
    winner_url: str
    score_gap: int
    category_deltas: List[GapDelta] = Field(default_factory=list)
    action_plan: List[GapAction] = Field(default_factory=list)
