"""
Configuration options for XML Sitemap Ingestion and Traversal.
"""
from __future__ import annotations
from pydantic import BaseModel, Field

class SitemapConfig(BaseModel):
    """Execution boundaries and safety limits for sitemap fetching and parsing."""
    max_sitemaps: int = Field(default=50, ge=1, le=500)
    max_urls: int = Field(default=50000, ge=1, le=500000)
    max_depth: int = Field(default=3, ge=0, le=10)
    max_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)  # 10 MB limit
    timeout_sec: float = Field(default=15.0, ge=1.0, le=60.0)
    user_agent: str = "RankIntel/2.0 (+https://github.com/ZeroTrace7/RankIntel)"
    respect_robots_txt: bool = True
    fallback_to_standard_paths: bool = True
