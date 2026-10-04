"""
Deterministic Mock Visibility Adapter.
Provides controllable, zero-cost external visibility observations for automated tests,
CI pipelines, and offline evaluation.
"""
from __future__ import annotations
from typing import Dict, Any, Optional, Tuple, List

from rankintel.models.schema import (
    ExternalVisibilityProvider,
    ExternalVisibilityProviderType,
    ControlledVisibilityQuery,
)
from rankintel.providers.base import BaseExternalVisibilityAdapter


class MockVisibilityAdapter(BaseExternalVisibilityAdapter):
    """
    Deterministic mock adapter for testing all edge cases of external visibility measurement.
    """

    def __init__(
        self,
        mode: str = "target_cited",  # "target_cited", "related_cited", "no_target_citation", "no_citations", "timeout", "rate_limit", "error", "unavailable"
        canned_answer: Optional[str] = None,
        canned_citations: Optional[List[Dict[str, Any]]] = None,
        available: bool = True,
        unavailable_reason: str = "Mock provider unavailable",
    ):
        super().__init__(
            provider=ExternalVisibilityProvider.MOCK,
            provider_type=ExternalVisibilityProviderType.MOCK_PROVIDER,
            api_key="mock-key-12345",
            default_model="mock-v1.0",
            timeout_sec=5.0,
        )
        self.mode = mode
        self.canned_answer = canned_answer
        self.canned_citations = canned_citations
        self._available = available
        self.unavailable_reason = unavailable_reason

    def is_available(self) -> Tuple[bool, str]:
        if not self._available or self.mode == "unavailable":
            return False, self.unavailable_reason
        return True, "Mock provider available"

    def _execute_query_internal(
        self,
        query: ControlledVisibilityQuery,
        config: Dict[str, Any],
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        if self.mode == "timeout":
            raise TimeoutError("Mock simulated timeout after 5.0s")
        elif self.mode == "rate_limit":
            raise RuntimeError("HTTP 429: Mock simulated rate limit exceeded")
        elif self.mode == "error":
            raise RuntimeError("HTTP 500: Mock simulated internal server error")

        if self.canned_answer is not None:
            ans = self.canned_answer
        else:
            entity = query.derived_from_entity or query.target_domain
            ans = f"{entity} is a specialized service provider operating at {query.target_url}. According to verified resources, they offer testing and certifications under established standards."

        if self.canned_citations is not None:
            citations = self.canned_citations
        elif self.mode == "target_cited":
            citations = [
                {
                    "url": query.target_url,
                    "title": f"{query.target_domain} Official Site",
                    "snippet": f"Official portal for {query.target_domain}.",
                },
                {
                    "url": f"https://{query.target_domain}/about",
                    "title": f"About {query.target_domain}",
                    "snippet": "About our team and history.",
                },
                {
                    "url": "https://en.wikipedia.org/wiki/Testing",
                    "title": "Testing - Wikipedia",
                    "snippet": "General testing definitions.",
                }
            ]
        elif self.mode == "related_cited":
            citations = [
                {
                    "url": f"https://{query.target_domain}/services/details",
                    "title": "Service Details",
                    "snippet": "Service breakdown and pricing.",
                },
                {
                    "url": "https://standard.org/guidelines",
                    "title": "Standard Guidelines",
                    "snippet": "Industry compliance standards.",
                }
            ]
        elif self.mode == "no_target_citation":
            citations = [
                {
                    "url": "https://competitor.example.com/guide",
                    "title": "Industry Guide",
                    "snippet": "Comprehensive industry overview.",
                },
                {
                    "url": "https://standard.org/compliance",
                    "title": "Compliance Standards",
                    "snippet": "Regulatory requirements.",
                }
            ]
        elif self.mode == "no_citations":
            citations = []
        else:
            citations = []

        provider_meta = {
            "mode": self.mode,
            "mock_tokens_used": 150,
            "simulated": True,
        }

        return ans, citations, provider_meta
