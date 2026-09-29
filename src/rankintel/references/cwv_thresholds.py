"""
Core Web Vitals Thresholds & Metrics.
Verified against web.dev and Google Search Central specifications.
"""

# Core Web Vitals standards (75th percentile of real users)
CWV_THRESHOLDS = {
    "LCP": {
        "metric": "Largest Contentful Paint",
        "good": 2.5,
        "needs_improvement": 4.0,
        "unit": "s",
        "weight": 0.40,
        "description": "Measures perceived loading speed. Marks point where main page content is likely loaded."
    },
    "INP": {
        "metric": "Interaction to Next Paint",
        "good": 200,
        "needs_improvement": 500,
        "unit": "ms",
        "weight": 0.35,
        "description": "Replaced FID in March 2024. Measures overall page responsiveness to user interactions."
    },
    "CLS": {
        "metric": "Cumulative Layout Shift",
        "good": 0.1,
        "needs_improvement": 0.25,
        "unit": "score",
        "weight": 0.25,
        "description": "Measures visual stability. Prevents unexpected content shifts during reading/clicking."
    },
    "TTFB": {
        "metric": "Time to First Byte",
        "good": 0.8,
        "needs_improvement": 1.8,
        "unit": "s",
        "weight": 0.15,
        "description": "Server responsiveness latency before initial byte is received."
    }
}
