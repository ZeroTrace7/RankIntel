"""
RankIntel Data Models for Multi-Engine Evidence & Synthesis.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator

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

class SiteCrawlResult(BaseModel):
    """Aggregated multi-page crawl intelligence."""
    pages_crawled: int = 0
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
