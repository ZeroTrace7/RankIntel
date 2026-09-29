"""
RankIntel Reference Knowledge System.
"""
from rankintel.references.ai_crawlers import AI_SEARCH_BOTS, AI_TRAINING_BOTS
from rankintel.references.cwv_thresholds import CWV_THRESHOLDS
from rankintel.references.schema_registry import ACTIVE_RICH_RESULT_SCHEMAS, DEPRECATED_OR_RESTRICTED_SCHEMAS
from rankintel.references.quality_gates import WORD_COUNT_MINIMUMS, META_LENGTH_BOUNDS, HEADING_HIERARCHY_RULES

__all__ = [
    "AI_SEARCH_BOTS",
    "AI_TRAINING_BOTS",
    "CWV_THRESHOLDS",
    "ACTIVE_RICH_RESULT_SCHEMAS",
    "DEPRECATED_OR_RESTRICTED_SCHEMAS",
    "WORD_COUNT_MINIMUMS",
    "META_LENGTH_BOUNDS",
    "HEADING_HIERARCHY_RULES",
]
