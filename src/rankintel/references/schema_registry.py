"""
Schema.org Types, Active Rich Results & Deprecation Registry.
"""

ACTIVE_RICH_RESULT_SCHEMAS = {
    "Organization": "Foundational entity identity, brand disambiguation, social profiles",
    "Product": "E-commerce product offers, prices, availability, ratings",
    "Article": "News and blog editorial content",
    "NewsArticle": "Time-sensitive journalistic reporting",
    "LocalBusiness": "Geographical address, telephone, hours, coordinates",
    "ProfessionalService": "Consulting and business services",
    "SoftwareApplication": "Software, apps, download links, pricing",
    "WebSite": "Sitelinks searchbox and root navigation",
    "BreadcrumbList": "Hierarchical URL structure in search results",
    "VideoObject": "Video carousel, timestamps, thumbnail markup",
    "ProfilePage": "Creator, author, or team member canonical identity"
}

DEPRECATED_OR_RESTRICTED_SCHEMAS = {
    "FAQPage": "Retired for general search results (May 2026). Kept only for authoritative health/government sites.",
    "HowTo": "Deprecated in September 2023 for desktop, fully retired for rich results.",
    "SpecialAnnouncement": "Deprecated post-COVID emergency declarations.",
    "VehicleListing": "Deprecated June 2025 in favor of unified Product markup."
}
