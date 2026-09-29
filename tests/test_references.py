"""
Unit tests for RankIntel references and bot classifications.
"""
from rankintel.references.ai_crawlers import AI_SEARCH_BOTS, AI_TRAINING_BOTS
from rankintel.references.quality_gates import WORD_COUNT_MINIMUMS, META_LENGTH_BOUNDS

def test_ai_bots_distinction():
    # Critical rule: OAI-SearchBot is in search bots, GPTBot is in training bots
    assert "OAI-SearchBot" in AI_SEARCH_BOTS
    assert "GPTBot" in AI_TRAINING_BOTS
    assert "Googlebot" in AI_SEARCH_BOTS
    assert "Google-Extended" in AI_TRAINING_BOTS
    assert "Claude-SearchBot" in AI_SEARCH_BOTS
    assert "ClaudeBot" in AI_TRAINING_BOTS

def test_meta_bounds():
    assert META_LENGTH_BOUNDS["title_optimal_min"] == 50
    assert META_LENGTH_BOUNDS["title_optimal_max"] == 60
    assert META_LENGTH_BOUNDS["desc_optimal_min"] == 140
    assert META_LENGTH_BOUNDS["desc_optimal_max"] == 160
