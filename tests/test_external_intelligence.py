import pytest
from rankintel.providers.external import OpenSEOProvider, MockExternalIntelligenceProvider
from rankintel.models.schema import ExternalValidationState, RemediationRecord

def test_mock_provider_available():
    provider = MockExternalIntelligenceProvider()
    result = provider.enrich("https://example.com", [])
    assert result.provider == "MockProvider"
    assert result.status == ExternalValidationState.AVAILABLE
    assert len(result.observations) == 1
    assert result.observations[0].result["organic_traffic"] == 500

def test_mock_provider_unavailable():
    provider = MockExternalIntelligenceProvider(unavailable=True)
    result = provider.enrich("https://example.com", [])
    assert result.status == ExternalValidationState.UNAVAILABLE
    assert "Provider is unavailable." in result.errors[0]

def test_mock_provider_error():
    provider = MockExternalIntelligenceProvider(should_fail=True)
    result = provider.enrich("https://example.com", [])
    assert result.status == ExternalValidationState.ERROR
    assert "Simulated explicit failure." in result.errors[0]

def test_openseo_provider_no_key():
    provider = OpenSEOProvider(api_key="")
    result = provider.enrich("https://example.com", [])
    assert result.status == ExternalValidationState.ERROR
    assert "OPENSEO_API_KEY not found or provided." in result.errors[0]
def test_mock_provider_insufficient_evidence():
    from rankintel.providers.external import MockExternalIntelligenceProvider
    from rankintel.models.schema import ExternalValidationState
    provider = MockExternalIntelligenceProvider(insufficient=True)
    result = provider.enrich("https://example.com", [])
    assert result.status == ExternalValidationState.INSUFFICIENT_EVIDENCE
