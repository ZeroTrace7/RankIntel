"""
Google Gemini Grounded Search Adapter.
Queries Google Gemini models with the official Google Search Grounding tool enabled.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, Tuple, List
import requests

from rankintel.models.schema import (
    ExternalVisibilityProvider,
    ExternalVisibilityProviderType,
    ControlledVisibilityQuery,
)
from rankintel.providers.base import BaseExternalVisibilityAdapter


class GeminiGroundedAdapter(BaseExternalVisibilityAdapter):
    """
    Adapter for Google Gemini with Google Search Grounding.
    Extracts answer text, executed search queries, and grounding chunks/citations.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-2.5-flash",
        timeout_sec: float = 20.0,
    ):
        super().__init__(
            provider=ExternalVisibilityProvider.GEMINI,
            provider_type=ExternalVisibilityProviderType.AI_GROUNDED_ANSWER,
            api_key=api_key or os.getenv("GEMINI_API_KEY"),
            default_model=default_model,
            timeout_sec=timeout_sec,
        )

    def is_available(self) -> Tuple[bool, str]:
        """Check availability of Gemini API key."""
        if not self.api_key:
            return False, "GEMINI_API_KEY environment variable not configured"
        return True, "GEMINI_API_KEY available"

    def _execute_query_internal(
        self,
        query: ControlledVisibilityQuery,
        config: Dict[str, Any],
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Executes Google Gemini call with Google Search Grounding enabled.
        """
        model = config.get("model", self.default_model)
        url = f"{self.BASE_URL}/{model}:generateContent?key={self.api_key}"

        # Construct request payload with google_search tool
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": query.query_text}
                    ]
                }
            ],
            "tools": [
                {"google_search": {}}
            ],
            "generationConfig": {
                "temperature": config.get("temperature", 0.2),
                "maxOutputTokens": config.get("max_tokens", 800),
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_sec)
        except requests.exceptions.Timeout as te:
            raise TimeoutError(f"Gemini API request timed out after {self.timeout_sec}s") from te
        except requests.exceptions.RequestException as re:
            raise RuntimeError(f"Gemini HTTP connection error: {re}") from re

        if resp.status_code == 429:
            raise RuntimeError(f"HTTP 429: Rate limited or quota exceeded by Gemini API: {resp.text[:200]}")
        elif resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} from Gemini API: {resp.text[:300]}")

        data = resp.json()

        # Parse text from candidates
        candidates = data.get("candidates", [])
        if not candidates:
            return "", [], {"raw_response_empty": True}

        cand = candidates[0]
        content_parts = cand.get("content", {}).get("parts", [])
        answer_text = "".join(part.get("text", "") for part in content_parts).strip()

        # Parse Grounding metadata
        grounding = cand.get("groundingMetadata", {})
        web_queries = grounding.get("webSearchQueries", [])
        chunks = grounding.get("groundingChunks", [])

        citations: List[Dict[str, Any]] = []
        for chk in chunks:
            web = chk.get("web", {})
            uri = web.get("uri")
            title = web.get("title")
            if uri:
                citations.append({
                    "url": uri,
                    "title": title,
                    "snippet": "",
                })

        provider_meta = {
            "model": model,
            "web_search_queries": web_queries,
            "grounding_chunks_count": len(chunks),
            "finish_reason": cand.get("finishReason"),
        }

        return answer_text, citations, provider_meta
