"""
MCP Cloud Engine — Cloud Intelligence via OpenSEO MCP (DataForSEO backend).
Performs silent fallback if MCP is unavailable or has no credits.
"""
from __future__ import annotations
import os
import requests
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from rankintel.models.schema import (
    CloudIntelligenceEvidence,
    KeywordIntelligence,
    BacklinkIntelligence,
    EngineResult
)

class McpEngine:
    """Queries OpenSEO MCP tools for live organic keywords, traffic, and backlink authority."""

    MCP_ENDPOINT = "https://app.openseo.so/mcp"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENSEO_API_KEY")

    def execute(self, url: str) -> EngineResult:
        """Run cloud intelligence pass with silent fallback."""
        domain = urlparse(url).netloc.replace("www.", "")
        cloud_data = self._query_openseo(domain, url)
        return EngineResult(
            engine_name="mcp_cloud",
            status="success" if cloud_data.available else "skipped",
            cloud_intelligence=cloud_data
        )

    def _query_openseo(self, domain: str, url: str) -> CloudIntelligenceEvidence:
        """Query OpenSEO endpoints. Catches all network/API exceptions silently."""
        evidence = CloudIntelligenceEvidence()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 1. domain_overview (Keywords & estimated traffic)
        try:
            resp = requests.post(
                f"{self.MCP_ENDPOINT}/tools/domain_overview",
                json={"domain": domain},
                headers=headers,
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                evidence.keywords = KeywordIntelligence(
                    source="openseo_mcp",
                    estimated_monthly_traffic=data.get("organic_traffic", data.get("traffic", 0)),
                    total_keywords=data.get("organic_keywords", data.get("keywords", 0)),
                    top_keywords=data.get("top_keywords", [])[:10],
                    keyword_gaps=data.get("keyword_gaps", [])
                )
                evidence.available = True
        except Exception as e:
            evidence.notes.append(f"OpenSEO domain_overview unavailable: {e}")

        # 2. backlink_analysis (Referring domains & authority)
        try:
            resp = requests.post(
                f"{self.MCP_ENDPOINT}/tools/backlink_analysis",
                json={"target": url},
                headers=headers,
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                evidence.backlinks = BacklinkIntelligence(
                    source="openseo_mcp",
                    referring_domains=data.get("referring_domains", 0),
                    total_backlinks=data.get("backlinks", 0),
                    domain_authority_score=data.get("domain_rank", data.get("authority_score", 0)),
                    top_anchors=data.get("top_anchors", [])[:5]
                )
                evidence.available = True
        except Exception as e:
            evidence.notes.append(f"OpenSEO backlink_analysis unavailable: {e}")

        return evidence
