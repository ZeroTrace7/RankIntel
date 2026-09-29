"""
Content Quality, Doorway Thresholds & Meta Rules.
Grounded in Google Quality Guidelines and verified SEO practice.
"""

WORD_COUNT_MINIMUMS = {
    "homepage": 500,
    "service_page": 800,
    "location_page": 600,
    "blog_article": 1200,
    "product_page": 350
}

META_LENGTH_BOUNDS = {
    "title_min": 30,
    "title_max": 65,
    "title_optimal_min": 50,
    "title_optimal_max": 60,
    "desc_min": 110,
    "desc_max": 165,
    "desc_optimal_min": 140,
    "desc_optimal_max": 160
}

HEADING_HIERARCHY_RULES = {
    "max_h1": 1,
    "min_h1": 1,
    "require_h2": True,
    "require_logical_order": True
}
