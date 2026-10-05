"""
Google Search Console Provider for RankIntel.
"""
from __future__ import annotations
import os
import json
import time
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from uuid import uuid4

from rankintel.models.schema import (
    ExternalIntelligenceResult,
    ExternalIntelligenceObservation,
    ExternalValidationState,
    RemediationRecord
)
from rankintel.providers.external import ExternalIntelligenceAdapter

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    GSC_AVAILABLE = True
except ImportError:
    GSC_AVAILABLE = False

class SearchConsoleProvider(ExternalIntelligenceAdapter):
    """
    Provider for Google Search Console first-party intelligence.
    Extracts historical Search Analytics data via Desktop OAuth Flow.
    """

    SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
    
    def __init__(
        self,
        property_url: str,
        start_date: str,
        end_date: str,
        data_state: str = "final",
        dimensions: Optional[List[str]] = None
    ):
        self.property_url = property_url
        self.start_date = start_date
        self.end_date = end_date
        self.data_state = data_state
        self.dimensions = dimensions or ['query', 'page']
        
        self.credentials_path = os.getenv(
            "GSC_CLIENT_SECRET_PATH", 
            os.path.join("D:\\", "RankIntel-Secrets", "google-search-console-client.json")
        )
        self.token_path = os.getenv(
            "GSC_TOKEN_PATH",
            os.path.join("D:\\", "RankIntel-Secrets", "google-search-console-token.json")
        )

    def _authenticate(self) -> Optional[Credentials]:
        """Authenticate with Google Search Console using local tokens."""
        if not GSC_AVAILABLE:
            return None

        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    pass
            
            if not creds or not creds.valid:
                if not os.path.exists(self.credentials_path):
                    return None
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    # Run local server, but don't hang indefinitely. Wait 60 seconds.
                    creds = flow.run_local_server(port=0, timeout_seconds=60)
                except Exception:
                    return None
            
            if creds:
                os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
                    
        return creds

    def enrich(self, url: str, remediations: List[RemediationRecord]) -> ExternalIntelligenceResult:
        result = ExternalIntelligenceResult(
            provider="GoogleSearchConsole",
            status=ExternalValidationState.AVAILABLE,
            observations=[],
            provenance="FIRST_PARTY_SEARCH_CONSOLE"
        )
        
        if not GSC_AVAILABLE:
            result.status = ExternalValidationState.UNAVAILABLE
            result.errors.append("Google API Client libraries are not installed.")
            return result

        creds = self._authenticate()
        if not creds:
            result.status = ExternalValidationState.UNAVAILABLE
            result.errors.append(f"GSC Authentication failed. Missing or invalid {self.credentials_path}.")
            return result

        try:
            service = build('searchconsole', 'v1', credentials=creds, cache_discovery=False)
            
            request_body = {
                'startDate': self.start_date,
                'endDate': self.end_date,
                'dimensions': self.dimensions,
                'dataState': self.data_state,
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'page',
                        'operator': 'equals',
                        'expression': url
                    }]
                }],
                'rowLimit': 25000,
                'startRow': 0
            }
            
            all_rows = []
            while True:
                response = service.searchanalytics().query(
                    siteUrl=self.property_url,
                    body=request_body
                ).execute()
                
                rows = response.get('rows', [])
                all_rows.extend(rows)
                
                if len(rows) < request_body['rowLimit']:
                    break
                
                request_body['startRow'] += request_body['rowLimit']
            
            if not all_rows:
                result.status = ExternalValidationState.INSUFFICIENT_EVIDENCE
                result.errors.append(f"No GSC data returned for {url}")
                return result
                
            for row in all_rows:
                keys = row.get('keys', [])
                
                # Map keys back to dimensions based on request
                dim_map = {}
                for idx, dim in enumerate(self.dimensions):
                    if idx < len(keys):
                        dim_map[dim] = keys[idx]
                
                query_val = dim_map.get("query", "UNKNOWN")
                page_val = dim_map.get("page", url)
                
                obs_result = {
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0.0),
                    "position": row.get("position", 0.0),
                    "dataState": self.data_state,
                    "startDate": self.start_date,
                    "endDate": self.end_date,
                }
                obs_result.update(dim_map)
                
                obs = ExternalIntelligenceObservation(
                    provider="GoogleSearchConsole",
                    observation_id=f"OBS-GSC-{uuid4().hex[:8]}",
                    query=f"gsc_analytics:{self.property_url}:{url}:{query_val}",
                    result=obs_result,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    provenance="FIRST_PARTY_SEARCH_CONSOLE",
                    status=ExternalValidationState.AVAILABLE
                )
                result.observations.append(obs)
                
        # Handle specific authorization errors (403)
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "forbidden" in error_msg.lower():
                result.status = ExternalValidationState.ERROR
                result.errors.append(f"GSC Authorization Error (403). Ensure account has access to {self.property_url}. Details: {error_msg}")
            else:
                result.status = ExternalValidationState.ERROR
                result.errors.append(f"GSC API Error: {error_msg}")
            
        return result
