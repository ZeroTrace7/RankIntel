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

# Master Taxonomy for Bot Access Matrix (RFC 9309 Triangulation)
MASTER_BOT_REGISTRY = {
    # 1. Search Engine Crawlers
    "Googlebot": {
        "category": "search_engine",
        "category_label": "Search Engine",
        "company": "Google",
        "engine": "Google Search & AI Overviews",
        "priority": "CRITICAL",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed in Google Search & AI Overviews",
        "disallowed_impact": "⚠️ De-indexed from Google Search (Catastrophic Traffic Loss)"
    },
    "Bingbot": {
        "category": "search_engine",
        "category_label": "Search Engine",
        "company": "Microsoft",
        "engine": "Microsoft Bing & Copilot",
        "priority": "CRITICAL",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed in Bing Search & Microsoft Copilot",
        "disallowed_impact": "⚠️ De-indexed from Bing & Microsoft Copilot"
    },
    "Slurp": {
        "category": "search_engine",
        "category_label": "Search Engine",
        "company": "Yahoo",
        "engine": "Yahoo Search",
        "priority": "MEDIUM",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed in Yahoo Search Network",
        "disallowed_impact": "De-indexed from Yahoo Search Network"
    },
    "DuckDuckBot": {
        "category": "search_engine",
        "category_label": "Search Engine",
        "company": "DuckDuckGo",
        "engine": "DuckDuckGo Search",
        "priority": "MEDIUM",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed in DuckDuckGo Search",
        "disallowed_impact": "De-indexed from DuckDuckGo Search"
    },
    "YandexBot": {
        "category": "search_engine",
        "category_label": "Search Engine",
        "company": "Yandex",
        "engine": "Yandex Search",
        "priority": "MEDIUM",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed in Yandex Search",
        "disallowed_impact": "De-indexed from Yandex Search"
    },
    "Baiduspider": {
        "category": "search_engine",
        "category_label": "Search Engine",
        "company": "Baidu",
        "engine": "Baidu Search",
        "priority": "LOW",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed in Baidu Search",
        "disallowed_impact": "De-indexed from Baidu Search"
    },

    # 2. AI Search Agents (Send Clicks & Direct Grounded Citations)
    "OAI-SearchBot": {
        "category": "ai_search",
        "category_label": "AI Search Agent",
        "company": "OpenAI",
        "engine": "ChatGPT Search",
        "priority": "CRITICAL",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Eligible for ChatGPT Search links & live citations",
        "disallowed_impact": "⚠️ Excluded from ChatGPT Search results & citations"
    },
    "PerplexityBot": {
        "category": "ai_search",
        "category_label": "AI Search Agent",
        "company": "Perplexity AI",
        "engine": "Perplexity AI",
        "priority": "HIGH",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Eligible for Perplexity citations & referral clicks",
        "disallowed_impact": "⚠️ Excluded from Perplexity citations & referral traffic"
    },
    "Claude-SearchBot": {
        "category": "ai_search",
        "category_label": "AI Search Agent",
        "company": "Anthropic",
        "engine": "Claude Search",
        "priority": "HIGH",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Eligible for Claude live search & citation retrieval",
        "disallowed_impact": "Excluded from Claude Search citations"
    },

    # 3. AI User-Initiated Fetchers (Real-Time On-Demand Retrieval)
    "ChatGPT-User": {
        "category": "user_fetch",
        "category_label": "User-Initiated Fetcher",
        "company": "OpenAI",
        "engine": "ChatGPT Live Browsing",
        "priority": "HIGH",
        "purpose": "user_fetch",
        "honors_robots_txt": True,
        "allowed_impact": "Permits real-time page retrieval when requested by ChatGPT users",
        "disallowed_impact": "Prevents on-demand live browsing retrieval by ChatGPT users"
    },
    "Claude-User": {
        "category": "user_fetch",
        "category_label": "User-Initiated Fetcher",
        "company": "Anthropic",
        "engine": "Claude Live Browsing",
        "priority": "HIGH",
        "purpose": "user_fetch",
        "honors_robots_txt": True,
        "allowed_impact": "Permits real-time page retrieval when requested by Claude users",
        "disallowed_impact": "Prevents on-demand live browsing retrieval by Claude users"
    },
    "Perplexity-User": {
        "category": "user_fetch",
        "category_label": "User-Initiated Fetcher",
        "company": "Perplexity AI",
        "engine": "Perplexity Live Actions",
        "priority": "HIGH",
        "purpose": "user_fetch",
        "honors_robots_txt": False,  # Official Perplexity docs: generally ignores robots.txt as user action
        "allowed_impact": "Permits real-time user-driven fetching in Perplexity answers",
        "disallowed_impact": "User-triggered fetcher; official Perplexity docs indicate it generally bypasses robots.txt"
    },

    # 4. AI Model Training Crawlers (Bulk Scrapers — IP & Copyright Protection)
    "GPTBot": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "OpenAI",
        "engine": "OpenAI Foundation Models",
        "priority": "HIGH",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Content scraped for OpenAI foundation model training",
        "disallowed_impact": "🛡️ Protected from OpenAI model training scraping"
    },
    "ClaudeBot": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Anthropic",
        "engine": "Anthropic Claude Models",
        "priority": "HIGH",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Content scraped for Anthropic foundation model training",
        "disallowed_impact": "🛡️ Protected from Anthropic Claude training scraping"
    },
    "Google-Extended": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Google",
        "engine": "Google Gemini & Vertex AI",
        "priority": "HIGH",
        "purpose": "ai_training",
        "is_control_token_only": True,
        "honors_robots_txt": True,
        "allowed_impact": "Content harvested for Google Gemini training (Search unaffected)",
        "disallowed_impact": "🛡️ Protected from Google Gemini training (Search unaffected)"
    },
    "Applebot-Extended": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Apple",
        "engine": "Apple Foundation Models",
        "priority": "MEDIUM",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Content collected for Apple AI model training",
        "disallowed_impact": "🛡️ Protected from Apple Foundation training"
    },
    "CCBot": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Common Crawl",
        "engine": "Common Crawl Training Corpus",
        "priority": "MEDIUM",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Scraped into public LLM training datasets",
        "disallowed_impact": "🛡️ Protected from Common Crawl dataset ingestion"
    },
    "Bytespider": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "ByteDance",
        "engine": "ByteDance AI Models",
        "priority": "MEDIUM",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Scraped by ByteDance AI crawlers",
        "disallowed_impact": "🛡️ Protected from ByteDance data scraping"
    },
    "FacebookBot": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Meta",
        "engine": "Meta Llama & AI Models",
        "priority": "MEDIUM",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Scraped for Meta Llama model training",
        "disallowed_impact": "🛡️ Protected from Meta AI model scraping"
    },
    "cohere-ai": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Cohere",
        "engine": "Cohere Enterprise LLMs",
        "priority": "LOW",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Scraped for Cohere LLM training",
        "disallowed_impact": "🛡️ Protected from Cohere training ingestion"
    },
    "anthropic-ai": {
        "category": "ai_training",
        "category_label": "AI Model Training",
        "company": "Anthropic",
        "engine": "Anthropic Web Harvester",
        "priority": "LOW",
        "purpose": "ai_training",
        "honors_robots_txt": True,
        "allowed_impact": "Scraped by Anthropic legacy scrapers",
        "disallowed_impact": "🛡️ Protected from Anthropic legacy crawlers"
    },

    # 5. Platform Bots
    "Applebot": {
        "category": "platform",
        "category_label": "Platform Bot",
        "company": "Apple",
        "engine": "Apple Intelligence, Siri & Spotlight",
        "priority": "HIGH",
        "purpose": "search_index",
        "honors_robots_txt": True,
        "allowed_impact": "Indexed for Apple Intelligence, Siri & Safari citations",
        "disallowed_impact": "⚠️ Blocked from Apple Intelligence & Siri integration"
    }
}

# Core 12 bots prioritized for M10.1 AI Access & Retrieval Readiness
CORE_RETRIEVAL_BOTS = [
    "Googlebot",
    "Google-Extended",
    "OAI-SearchBot",
    "GPTBot",
    "ChatGPT-User",
    "Claude-SearchBot",
    "ClaudeBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
    "Bingbot",
    "Applebot",
]
