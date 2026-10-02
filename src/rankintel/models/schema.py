"""
RankIntel Data Models for Multi-Engine Evidence & Synthesis.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
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

class CookieSecurityDetails(BaseModel):
    name: str
    secure: bool = False
    httponly: bool = False
    samesite: Optional[str] = None
    issues: List[str] = Field(default_factory=list)

class SecurityEvidence(BaseModel):
    url: str = ""
    is_https: bool = True
    score: int = 100
    grade: str = "A"
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

class ImageFindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class ImageFinding(BaseModel):
    code: str
    severity: ImageFindingSeverity
    src: str
    description: str
    recommendation: str

class ImageDetail(BaseModel):
    src: str
    alt: Optional[str] = None
    has_alt: bool = False
    is_decorative: bool = False
    alt_quality: str = "good"  # "good", "missing", "generic", "decorative"
    width: Optional[int] = None
    height: Optional[int] = None
    has_dimensions: bool = False
    format: str = ""
    is_modern_format: bool = False
    loading: Optional[str] = None
    fetchpriority: Optional[str] = None
    has_srcset: bool = False
    is_in_picture_tag: bool = False
    filename: str = ""
    is_descriptive_filename: bool = True
    issues: List[str] = Field(default_factory=list)

class ImageSeoEvidence(BaseModel):
    total_images: int = 0
    images_with_alt: int = 0
    decorative_images: int = 0
    images_with_dimensions: int = 0
    modern_format_count: int = 0
    lazy_loaded_count: int = 0
    hero_or_lcp_candidate: Optional[str] = None
    score: int = 100
    grade: str = "A"
    images: List[ImageDetail] = Field(default_factory=list)
    findings: List[ImageFinding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

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

class EvidenceNature(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNAVAILABLE = "UNAVAILABLE"

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
    image_seo: Optional[ImageSeoEvidence] = None
    cloud_intelligence: Optional[CloudIntelligenceEvidence] = None
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
    unified_image_seo: ImageSeoEvidence = Field(default_factory=ImageSeoEvidence)
    cloud_intelligence: CloudIntelligenceEvidence = Field(default_factory=CloudIntelligenceEvidence)
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
