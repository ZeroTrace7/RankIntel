import pytest
from unittest.mock import patch, MagicMock

from rankintel.models.schema import (
    SynthesisReport,
    ExternalValidationState,
    ExternalIntelligenceResult,
    ExternalIntelligenceObservation
)
from rankintel.providers.search_console import SearchConsoleProvider
from rankintel.intelligence.synthesizer import IntelligenceSynthesizer

# Test A: No --search-console -> zero provider invocation
def test_zero_gsc_activity_when_not_opted_in():
    synthesizer = IntelligenceSynthesizer()
    with patch("rankintel.intelligence.synthesizer.SearchConsoleProvider") as mock_provider:
        report = synthesizer.synthesize("https://example.com", {})
        assert report.search_console_intelligence is None
        mock_provider.assert_not_called()

# Test B: Explicit opt-in -> provider invoked
def test_explicit_opt_in():
    synthesizer = IntelligenceSynthesizer()
    with patch("rankintel.intelligence.synthesizer.SearchConsoleProvider") as mock_provider:
        mock_provider_instance = MagicMock()
        mock_provider_instance.enrich.return_value = ExternalIntelligenceResult(
            provider="GoogleSearchConsole",
            status=ExternalValidationState.AVAILABLE,
            observations=[],
            provenance="FIRST_PARTY_SEARCH_CONSOLE"
        )
        mock_provider.return_value = mock_provider_instance
        
        report = synthesizer.synthesize("https://example.com", {}, gsc_property="https://example.com/")
        assert report.search_console_intelligence is not None
        assert mock_provider.called
        # Verify first kwarg is correct
        kwargs = mock_provider.call_args.kwargs
        assert kwargs["property_url"] == "https://example.com/"
        mock_provider_instance.enrich.assert_called_once()

# Test C: Missing credentials -> explicit unavailable state
@patch("rankintel.providers.search_console.os.path.exists", return_value=False)
@patch("rankintel.providers.search_console.InstalledAppFlow")
def test_missing_credentials(mock_flow, mock_exists):
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    res = provider.enrich("https://example.com/", [])
    assert res.status == ExternalValidationState.UNAVAILABLE
    assert "Missing or invalid" in res.errors[0]

# Test D: Authentication failure -> explicit error and no hang
@patch("rankintel.providers.search_console.os.path.exists", return_value=True)
@patch("rankintel.providers.search_console.InstalledAppFlow")
@patch("rankintel.providers.search_console.Credentials")
def test_authentication_failure(mock_creds, mock_flow, mock_exists):
    mock_flow_instance = MagicMock()
    mock_flow_instance.run_local_server.side_effect = Exception("Browser hang timeout")
    mock_flow.from_client_secrets_file.return_value = mock_flow_instance
    mock_creds.from_authorized_user_file.return_value = None
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    # Change credentials_path so it passes exists
    provider.credentials_path = "mock.json"
    provider.token_path = "mock_token.json"
    
    res = provider.enrich("https://example.com/", [])
    assert res.status == ExternalValidationState.UNAVAILABLE

# Test E: Authorization/403 -> explicit error
@patch("rankintel.providers.search_console.build")
def test_authorization_403(mock_build):
    mock_service = MagicMock()
    mock_service.searchanalytics.return_value.query.return_value.execute.side_effect = Exception("HttpError 403: User does not have sufficient permission for site 'https://example.com/'. See also: https://support.google.com/webmasters/answer/2451999.")
    mock_build.return_value = mock_service
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    provider._authenticate = MagicMock(return_value=MagicMock()) # Mock valid creds
    
    res = provider.enrich("https://example.com/", [])
    assert res.status == ExternalValidationState.ERROR
    assert "GSC Authorization Error (403)" in res.errors[0]

# Test F: Generic API/network failure
@patch("rankintel.providers.search_console.build")
def test_generic_api_failure(mock_build):
    mock_service = MagicMock()
    mock_service.searchanalytics.return_value.query.return_value.execute.side_effect = Exception("503 Backend Error")
    mock_build.return_value = mock_service
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    provider._authenticate = MagicMock(return_value=MagicMock())
    
    res = provider.enrich("https://example.com/", [])
    assert res.status == ExternalValidationState.ERROR
    assert "503 Backend Error" in res.errors[0]

# Test G: Empty result -> explicit insufficient-evidence/no-data state
@patch("rankintel.providers.search_console.build")
def test_empty_result(mock_build):
    mock_service = MagicMock()
    mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {} # No rows
    mock_build.return_value = mock_service
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    provider._authenticate = MagicMock(return_value=MagicMock())
    
    res = provider.enrich("https://example.com/", [])
    assert res.status == ExternalValidationState.INSUFFICIENT_EVIDENCE
    assert "No GSC data returned" in res.errors[0]

# Test H & J & K: Valid mapping, Date range, dataState=final
@patch("rankintel.providers.search_console.build")
def test_valid_mapping_and_dates(mock_build):
    mock_service = MagicMock()
    mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["buy widgets", "https://example.com/widgets"], "clicks": 100, "impressions": 1000, "ctr": 0.1, "position": 2.5}
        ]
    }
    mock_build.return_value = mock_service
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30", data_state="final")
    provider._authenticate = MagicMock(return_value=MagicMock())
    
    res = provider.enrich("https://example.com/widgets", [])
    assert res.status == ExternalValidationState.AVAILABLE
    assert len(res.observations) == 1
    obs = res.observations[0]
    assert obs.result["clicks"] == 100
    assert obs.result["query"] == "buy widgets"
    assert obs.result["startDate"] == "2026-09-01"
    assert obs.result["endDate"] == "2026-09-30"
    assert obs.result["dataState"] == "final"
    
    # Verify request exact dates reach API
    args, kwargs = mock_service.searchanalytics.return_value.query.call_args
    assert kwargs["body"]["startDate"] == "2026-09-01"
    assert kwargs["body"]["endDate"] == "2026-09-30"
    assert kwargs["body"]["dataState"] == "final"

# Test I: Pagination
@patch("rankintel.providers.search_console.build")
def test_pagination(mock_build):
    mock_service = MagicMock()
    
    first_response = {"rows": [{"keys": [f"query{i}", "page"], "clicks": 1} for i in range(25000)]}
    second_response = {"rows": [{"keys": [f"query_page2_{i}", "page"], "clicks": 1} for i in range(10)]}
    
    # Correct mock setup
    mock_service.searchanalytics.return_value.query.return_value.execute.side_effect = [first_response, second_response]
    mock_build.return_value = mock_service
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    provider._authenticate = MagicMock(return_value=MagicMock())
    
    res = provider.enrich("https://example.com/", [])
    assert len(res.observations) == 25010
    
    calls = mock_service.searchanalytics.return_value.query.call_args_list
    assert len(calls) == 2

# Test L: dataState=all
@patch("rankintel.providers.search_console.build")
def test_data_state_all(mock_build):
    mock_service = MagicMock()
    mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["query"], "clicks": 5}
        ]
    }
    mock_build.return_value = mock_service
    
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30", data_state="all")
    provider._authenticate = MagicMock(return_value=MagicMock())
    
    res = provider.enrich("https://example.com/", [])
    obs = res.observations[0]
    assert obs.result["dataState"] == "all"
    
    args, kwargs = mock_service.searchanalytics.return_value.query.call_args
    assert kwargs["body"]["dataState"] == "all"

# Test M: Provenance
def test_provenance_preserved():
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    provider._authenticate = MagicMock(return_value=MagicMock())
    
    with patch("rankintel.providers.search_console.build") as mock_build:
        mock_service = MagicMock()
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {"rows": [{"keys": ["query"], "clicks": 5}]}
        mock_build.return_value = mock_service
        
        res = provider.enrich("https://example.com/", [])
        assert res.provenance == "FIRST_PARTY_SEARCH_CONSOLE"
        assert res.observations[0].provenance == "FIRST_PARTY_SEARCH_CONSOLE"

# Test N: Secret Redaction
@patch("rankintel.providers.search_console.os.path.exists", return_value=False)
def test_secret_redaction(mock_exists):
    provider = SearchConsoleProvider("https://example.com/", "2026-09-01", "2026-09-30")
    provider.credentials_path = "D:\\RankIntel-Secrets\\google-search-console-client.json"
    
    res = provider.enrich("https://example.com/", [])
    assert "Missing or invalid" in res.errors[0]
    assert "{" not in res.errors[0]
    
# Test O: Formula Invariance
def test_formula_invariance():
    synthesizer = IntelligenceSynthesizer()
    report1 = synthesizer.synthesize("https://example.com", {})
    
    with patch("rankintel.intelligence.synthesizer.SearchConsoleProvider") as mock_provider:
        mock_provider_instance = MagicMock()
        mock_provider_instance.enrich.return_value = ExternalIntelligenceResult(
            provider="GoogleSearchConsole",
            status=ExternalValidationState.AVAILABLE,
            observations=[],
            provenance="FIRST_PARTY_SEARCH_CONSOLE"
        )
        mock_provider.return_value = mock_provider_instance
        
        report2 = synthesizer.synthesize("https://example.com", {}, gsc_property="https://example.com/")
        
        assert report1.overall_health_score == report2.overall_health_score
        assert report1.technical_health_score == report2.technical_health_score
        assert report1.trust_score == report2.trust_score

# Test P: Backward Compatibility
def test_backward_compatibility():
    # Calling the CLI without GSC should not crash
    from rankintel.cli import audit
    from click.testing import CliRunner
    
    runner = CliRunner()
    result = runner.invoke(audit, ["https://example.com", "--output-dir", "scratch"])
    # It should run successfully (might have warnings depending on other tools, but shouldn't crash on GSC)
    assert result.exit_code == 0
