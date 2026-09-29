"""
RankIntel Data Models for Multi-Engine Evidence & Synthesis.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

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
    engine_source: str = ""

class SchemaEvidence(BaseModel):
    detected_types: List[str] = Field(default_factory=list)
    deprecated_types_detected: List[str] = Field(default_factory=list)
    blocks_count: int = 0
    is_injected_via_js: bool = False
    validation_issues: List[str] = Field(default_factory=list)
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

class EngineResult(BaseModel):
    engine_name: str
    status: str = "success"  # success, error, skipped
    execution_time_sec: float = 0.0
    error_message: Optional[str] = None
    on_page: Optional[OnPageEvidence] = None
    robots: Optional[RobotsEvidence] = None
    schema_data: Optional[SchemaEvidence] = None
    geo_aeo: Optional[GeoAeoEvidence] = None

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
    engines_executed: List[str] = Field(default_factory=list)
    conflicts_detected: List[ConflictFinding] = Field(default_factory=list)
    prioritized_actions: List[PrioritizedAction] = Field(default_factory=list)
    
    # Unified reconciled states
    unified_on_page: OnPageEvidence = Field(default_factory=OnPageEvidence)
    unified_robots: RobotsEvidence = Field(default_factory=RobotsEvidence)
    unified_schema: SchemaEvidence = Field(default_factory=SchemaEvidence)
    unified_geo: GeoAeoEvidence = Field(default_factory=GeoAeoEvidence)
    
    # Generated fixes
    fixes: Dict[str, str] = Field(default_factory=dict)
