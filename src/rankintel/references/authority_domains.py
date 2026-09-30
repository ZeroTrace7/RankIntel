"""
Authoritative Domain Reference — Single source of truth.

Imported by GeoOptimizerAdapter and TrustEvaluator.
Previously maintained as two separate, unsynchronized lists.
"""

AUTHORITATIVE_TLDS = {".edu", ".gov", ".org", ".nic.in", ".gov.in"}

AUTHORITATIVE_DOMAINS = {
    "wikipedia.org",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "scholar.google.com",
    "nature.com",
    "sciencedirect.com",
    "arxiv.org",
    "who.int",
    "cdc.gov",
    "doi.org",
    "ieee.org",
    "acm.org",
    "wikidata.org",
    "bis.gov.in",
    "iso.org",
}

SOCIAL_DOMAINS = [
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "github.com",
    "pinterest.com",
    "reddit.com",
]
