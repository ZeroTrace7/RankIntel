import abc
import os
import requests
import time
from uuid import uuid4
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from rankintel.models.schema import (
    ExternalIntelligenceResult,
    ExternalIntelligenceObservation,
    ExternalValidationState,
    RemediationRecord
)

class ExternalIntelligenceAdapter(abc.ABC):
    """Abstract base adapter for controlled external intelligence enrichment."""
    @abc.abstractmethod
    def enrich(self, url: str, remediations: List[RemediationRecord]) -> ExternalIntelligenceResult:
        pass

class OpenSEOProvider(ExternalIntelligenceAdapter):
    """Provider for OpenSEO MCP external intelligence."""
    
    MCP_ENDPOINT = "https://app.openseo.so/mcp"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENSEO_API_KEY")

    def enrich(self, url: str, remediations: List[RemediationRecord]) -> ExternalIntelligenceResult:
        domain = urlparse(url).netloc.replace("www.", "")
        
        result = ExternalIntelligenceResult(
            provider="OpenSEO",
            status=ExternalValidationState.AVAILABLE,
            observations=[]
        )
        
        if not self.api_key:
            result.status = ExternalValidationState.ERROR
            result.errors.append("OPENSEO_API_KEY not found or provided.")
            return result
            
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        
        # We only want to enrich if there's a reason to.
        # But for this phase, we do a bounded single request to domain_overview if requested
        try:
            resp = requests.post(
                f"{self.MCP_ENDPOINT}/tools/domain_overview",
                json={"domain": domain},
                headers=headers,
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                
                # Create an observation
                obs = ExternalIntelligenceObservation(
                    provider="OpenSEO",
                    observation_id=f"OBS-OPENSEO-{uuid4().hex[:8]}",
                    query=f"domain_overview:{domain}",
                    result={
                        "organic_traffic": data.get("organic_traffic", data.get("traffic", 0)),
                        "organic_keywords": data.get("organic_keywords", data.get("keywords", 0))
                    },
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    status=ExternalValidationState.AVAILABLE
                )
                result.observations.append(obs)
            else:
                result.status = ExternalValidationState.ERROR
                result.errors.append(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            result.status = ExternalValidationState.ERROR
            result.errors.append(f"Network error: {str(e)}")
            
        return result

class MockExternalIntelligenceProvider(ExternalIntelligenceAdapter):
    """Deterministic mock provider for tests."""
    def __init__(self, should_fail: bool = False, unavailable: bool = False, insufficient: bool = False):
        self.should_fail = should_fail
        self.unavailable = unavailable
        self.insufficient = insufficient
        
    def enrich(self, url: str, remediations: List[RemediationRecord]) -> ExternalIntelligenceResult:
        domain = urlparse(url).netloc.replace("www.", "")
        
        if self.unavailable:
            return ExternalIntelligenceResult(
                provider="MockProvider",
                status=ExternalValidationState.UNAVAILABLE,
                errors=["Provider is unavailable."]
            )
            
        if self.insufficient:
            return ExternalIntelligenceResult(
                provider="MockProvider",
                status=ExternalValidationState.INSUFFICIENT_EVIDENCE,
                errors=["Insufficient evidence returned."]
            )
            
        if self.should_fail:
            return ExternalIntelligenceResult(
                provider="MockProvider",
                status=ExternalValidationState.ERROR,
                errors=["Simulated explicit failure."]
            )
            
        obs = ExternalIntelligenceObservation(
            provider="MockProvider",
            observation_id=f"OBS-MOCK-1234",
            query=f"domain_overview:{domain}",
            result={
                "organic_traffic": 500,
                "organic_keywords": 120
            },
            timestamp="2026-10-05T00:00:00Z",
            status=ExternalValidationState.AVAILABLE
        )
        
        return ExternalIntelligenceResult(
            provider="MockProvider",
            status=ExternalValidationState.AVAILABLE,
            observations=[obs]
        )
