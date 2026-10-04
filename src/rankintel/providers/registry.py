"""
Provider Registry for External AI Visibility Adapters.
Manages adapter lifecycle, discovery, and credential inspection.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, List, Type

from rankintel.models.schema import ExternalVisibilityProvider
from rankintel.providers.base import BaseExternalVisibilityAdapter
from rankintel.providers.gemini_grounded import GeminiGroundedAdapter
from rankintel.providers.mock import MockVisibilityAdapter


class ProviderRegistry:
    """Registry and factory for external AI visibility adapters."""

    _ADAPTER_CLASSES: Dict[ExternalVisibilityProvider, Type[BaseExternalVisibilityAdapter]] = {
        ExternalVisibilityProvider.GEMINI: GeminiGroundedAdapter,
        ExternalVisibilityProvider.MOCK: MockVisibilityAdapter,
    }

    @classmethod
    def get_adapter(
        cls,
        provider: ExternalVisibilityProvider | str,
        **kwargs,
    ) -> BaseExternalVisibilityAdapter:
        """Instantiate a provider adapter by name or enum."""
        if isinstance(provider, str):
            try:
                provider_enum = ExternalVisibilityProvider(provider.lower())
            except ValueError:
                provider_enum = ExternalVisibilityProvider.CUSTOM
        else:
            provider_enum = provider

        adapter_cls = cls._ADAPTER_CLASSES.get(provider_enum)
        if adapter_cls:
            return adapter_cls(**kwargs)

        # Fallback to mock adapter if unknown provider requested
        return MockVisibilityAdapter(
            available=False,
            unavailable_reason=f"Unknown or unsupported provider '{provider}'",
            **kwargs,
        )

    @classmethod
    def get_configured_adapters(
        cls,
        requested_providers: Optional[List[str]] = None,
    ) -> List[BaseExternalVisibilityAdapter]:
        """
        Returns instantiated adapters for requested or available providers.
        Only returns providers that are explicitly requested or safely detected.
        """
        adapters: List[BaseExternalVisibilityAdapter] = []

        if requested_providers:
            for p_str in requested_providers:
                adapters.append(cls.get_adapter(p_str))
            return adapters

        # Default detection: if GEMINI_API_KEY is present, configure Gemini
        if os.getenv("GEMINI_API_KEY"):
            adapters.append(GeminiGroundedAdapter())

        # If no real credentials exist, return mock adapter by default
        if not adapters:
            adapters.append(MockVisibilityAdapter())

        return adapters
