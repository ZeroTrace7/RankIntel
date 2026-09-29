"""
AI Crawler Classification Registry.

Distinguishes between:
1. AI Search & Citation Bots (Essential for GEO / AI Overview visibility)
2. AI Foundation Training Bots (Optional model pre-training scrapers)
"""

# AI Search & Citation Bots (Allowing these drives generative citations & links)
AI_SEARCH_BOTS = {
    "OAI-SearchBot": {
        "engine": "ChatGPT Search",
        "role": "Search indexer & live web citation retriever (NOT GPTBot)",
        "priority": "CRITICAL"
    },
    "Googlebot": {
        "engine": "Google Search & AI Overviews",
        "role": "Primary web indexer driving Google SGE/AI Overviews",
        "priority": "CRITICAL"
    },
    "PerplexityBot": {
        "engine": "Perplexity AI",
        "role": "Live answer engine citation crawler",
        "priority": "HIGH"
    },
    "Claude-SearchBot": {
        "engine": "Claude Search",
        "role": "Anthropic search indexer (NOT ClaudeBot)",
        "priority": "HIGH"
    },
    "Applebot": {
        "engine": "Apple Intelligence & Siri",
        "role": "Apple Intelligence search & Safari citations",
        "priority": "MEDIUM"
    },
    "Bingbot": {
        "engine": "Microsoft Copilot & Bing",
        "role": "Microsoft AI search indexer",
        "priority": "CRITICAL"
    }
}

# AI Model Training Bots (Blocking these protects copyright/IP without losing search rankings)
AI_TRAINING_BOTS = {
    "GPTBot": {
        "company": "OpenAI",
        "purpose": "Model training data collection (ChatGPT base models)"
    },
    "ClaudeBot": {
        "company": "Anthropic",
        "purpose": "Model training data collection (Claude base models)"
    },
    "Google-Extended": {
        "company": "Google",
        "purpose": "Gemini & Vertex AI model training (Separate from Googlebot)"
    },
    "Applebot-Extended": {
        "company": "Apple",
        "purpose": "Apple Foundation model training"
    },
    "CCBot": {
        "company": "Common Crawl",
        "purpose": "Open web dataset scraped for AI foundation training"
    },
    "FacebookBot": {
        "company": "Meta",
        "purpose": "Llama & Meta AI model training"
    },
    "cohere-ai": {
        "company": "Cohere",
        "purpose": "Enterprise LLM training"
    },
    "Bytespider": {
        "company": "ByteDance",
        "purpose": "ByteDance AI training"
    }
}
