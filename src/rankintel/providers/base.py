"""
Base External Visibility Provider Adapter.
Defines the agnostic contract for querying external search and AI systems under controlled conditions.
"""
from __future__ import annotations
import abc
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import urlparse

from rankintel.models.schema import (
    ExternalVisibilityProvider,
    ExternalVisibilityProviderType,
    ExternalVisibilityStatus,
    ControlledVisibilityQuery,
    ExternalAIObservation,
    ExternalCitationObservation,
    ExternalMentionObservation,
    ExternalAnswerEvidence,
    CitationRelationship,
    CitationContentMatchStatus,
)


class BaseExternalVisibilityAdapter(abc.ABC):
    """Abstract base adapter for controlled external AI/search visibility observations."""

    def __init__(
        self,
        provider: ExternalVisibilityProvider,
        provider_type: ExternalVisibilityProviderType,
        api_key: Optional[str] = None,
        default_model: str = "default",
        timeout_sec: float = 15.0,
    ):
        self.provider = provider
        self.provider_type = provider_type
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_sec = timeout_sec

    @abc.abstractmethod
    def is_available(self) -> Tuple[bool, str]:
        """Check if provider credentials, endpoint, and configuration are available."""
        pass

    @abc.abstractmethod
    def _execute_query_internal(
        self,
        query: ControlledVisibilityQuery,
        config: Dict[str, Any],
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Provider-specific query execution.
        Must return:
            (answer_text, raw_citations_list, provider_metadata)
        """
        pass

    def execute_query(
        self,
        query: ControlledVisibilityQuery,
        config: Optional[Dict[str, Any]] = None,
    ) -> ExternalAIObservation:
        """
        Executes a controlled visibility query with strict error boundaries,
        latency measurements, secret masking, and normalized observation output.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        cfg = dict(config or {})
        model_version = cfg.get("model", self.default_model)
        observation_id = f"obs-{self.provider.value}-{query.query_id}-t{query.trial_index}-{int(time.time() * 1000)}"

        # 1. Availability check
        avail, reason = self.is_available()
        if not avail:
            return ExternalAIObservation(
                observation_id=observation_id,
                provider=self.provider,
                provider_type=self.provider_type,
                model_version=model_version,
                query=query,
                target_domain=query.target_domain,
                target_url=query.target_url,
                timestamp=now_iso,
                request_config=self._sanitize_config(cfg),
                status=ExternalVisibilityStatus.UNAVAILABLE,
                provenance="external_visibility_engine",
                failure_reason=reason,
                trial_index=query.trial_index,
            )

        # 2. Execution with explicit boundary error trapping
        t0 = time.perf_counter()
        try:
            answer_text, raw_citations, provider_meta = self._execute_query_internal(query, cfg)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            status = ExternalVisibilityStatus.SUCCESS
            failure_reason = None
        except TimeoutError as te:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return ExternalAIObservation(
                observation_id=observation_id,
                provider=self.provider,
                provider_type=self.provider_type,
                model_version=model_version,
                query=query,
                target_domain=query.target_domain,
                target_url=query.target_url,
                timestamp=now_iso,
                request_config=self._sanitize_config(cfg),
                status=ExternalVisibilityStatus.TIMEOUT,
                latency_ms=latency_ms,
                provenance="external_visibility_engine",
                failure_reason=f"Request timed out after {self.timeout_sec}s: {te}",
                trial_index=query.trial_index,
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            err_msg = str(e)
            # Detect rate-limiting specifically
            if "429" in err_msg or "rate limit" in err_msg.lower() or "quota" in err_msg.lower():
                status = ExternalVisibilityStatus.RATE_LIMITED
            else:
                status = ExternalVisibilityStatus.ERROR

            return ExternalAIObservation(
                observation_id=observation_id,
                provider=self.provider,
                provider_type=self.provider_type,
                model_version=model_version,
                query=query,
                target_domain=query.target_domain,
                target_url=query.target_url,
                timestamp=now_iso,
                request_config=self._sanitize_config(cfg),
                status=status,
                latency_ms=latency_ms,
                provenance="external_visibility_engine",
                failure_reason=f"{status.value}: {err_msg}",
                trial_index=query.trial_index,
            )

        # 3. Citation normalization
        citations: List[ExternalCitationObservation] = []
        target_domain_clean = self._clean_domain(query.target_domain)
        target_domain_cited = False
        target_page_cited = False
        cited_target_urls: List[str] = []

        if not raw_citations:
            relationship_default = CitationRelationship.PROVIDER_DID_NOT_RETURN_CITATIONS
        else:
            relationship_default = CitationRelationship.NO_TARGET_CITATION

        for idx, item in enumerate(raw_citations, start=1):
            c_url = item.get("url") or ""
            c_title = item.get("title")
            c_snippet = item.get("snippet")
            
            c_domain = self._clean_domain(urlparse(c_url).netloc)
            is_target_domain = bool(target_domain_clean and (c_domain == target_domain_clean or c_domain.endswith("." + target_domain_clean)))
            is_target_page = bool(is_target_domain and (self._normalize_url(c_url) == self._normalize_url(query.target_url)))

            if is_target_page:
                rel = CitationRelationship.TARGET_PAGE_CITED
                target_domain_cited = True
                target_page_cited = True
                cited_target_urls.append(c_url)
            elif is_target_domain:
                rel = CitationRelationship.TARGET_DOMAIN_CITED
                target_domain_cited = True
                cited_target_urls.append(c_url)
            else:
                rel = CitationRelationship.NO_TARGET_CITATION

            citations.append(ExternalCitationObservation(
                citation_url=c_url,
                title=c_title,
                snippet=c_snippet,
                position=idx,
                relationship=rel,
                is_target_domain=is_target_domain,
                is_target_page=is_target_page,
                raw_citation_data=self._sanitize_dict(item),
            ))

        # 4. Mention detection
        mention_obs = self._detect_mentions(answer_text, query)

        # 5. Answer evidence
        answer_ev = ExternalAnswerEvidence(
            answer_text=answer_text,
            answer_char_count=len(answer_text),
            answer_word_count=len(answer_text.split()),
            appears_to_answer_topic=bool(len(answer_text.strip()) > 30),
            bounded_excerpt=answer_text[:250] + ("..." if len(answer_text) > 250 else ""),
        )

        return ExternalAIObservation(
            observation_id=observation_id,
            provider=self.provider,
            provider_type=self.provider_type,
            model_version=model_version,
            query=query,
            target_domain=query.target_domain,
            target_url=query.target_url,
            timestamp=now_iso,
            request_config=self._sanitize_config(cfg),
            status=status,
            latency_ms=latency_ms,
            answer_evidence=answer_ev,
            citations=citations,
            target_domain_cited=target_domain_cited,
            target_page_cited=target_page_cited,
            target_domain_citations_count=len(cited_target_urls),
            cited_target_urls=list(dict.fromkeys(cited_target_urls)),
            mention_observation=mention_obs,
            provider_specific_evidence=self._sanitize_dict(provider_meta),
            provenance="external_visibility_engine",
            failure_reason=failure_reason,
            trial_index=query.trial_index,
        )

    def _detect_mentions(
        self,
        answer_text: str,
        query: ControlledVisibilityQuery,
    ) -> ExternalMentionObservation:
        """Observable mention detection for target domain, brand, or entity name."""
        if not answer_text:
            return ExternalMentionObservation()

        text_lower = answer_text.lower()
        domain_clean = self._clean_domain(query.target_domain).lower()
        root_name = domain_clean.split(".")[0] if domain_clean else ""

        names_to_check: List[str] = []
        if query.derived_from_entity:
            names_to_check.append(query.derived_from_entity.strip())
        if root_name and len(root_name) > 3 and root_name not in [n.lower() for n in names_to_check]:
            names_to_check.append(root_name)
        if domain_clean and domain_clean not in [n.lower() for n in names_to_check]:
            names_to_check.append(domain_clean)

        strings_found: List[str] = []
        contexts: List[str] = []
        positions: List[int] = []

        for name in names_to_check:
            name_lower = name.lower()
            start = 0
            while True:
                idx = text_lower.find(name_lower, start)
                if idx == -1:
                    break
                strings_found.append(name)
                positions.append(idx)
                ctx_start = max(0, idx - 40)
                ctx_end = min(len(answer_text), idx + len(name) + 40)
                ctx = answer_text[ctx_start:ctx_end].replace("\n", " ").strip()
                contexts.append(f"...{ctx}...")
                start = idx + len(name)

        return ExternalMentionObservation(
            target_mentioned=bool(strings_found),
            mention_strings_found=list(dict.fromkeys(strings_found)),
            mention_contexts=contexts[:5],
            mention_positions=positions[:5],
            entity_names_checked=names_to_check,
            domain_names_checked=[domain_clean],
        )

    @staticmethod
    def _clean_domain(domain: str) -> str:
        d = domain.strip().lower()
        if d.startswith("http://") or d.startswith("https://"):
            d = urlparse(d).netloc
        if d.startswith("www."):
            d = d[4:]
        return d.split(":")[0]

    @staticmethod
    def _normalize_url(url: str) -> str:
        p = urlparse(url.strip())
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = p.path.rstrip("/")
        return f"{p.scheme}://{netloc}{path}"

    def _sanitize_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Redact secrets and keys from configuration dictionaries."""
        sanitized = {}
        for k, v in cfg.items():
            if any(secret_term in k.lower() for secret_term in ["key", "token", "secret", "auth", "pass"]):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            else:
                sanitized[k] = v
        return sanitized

    def _sanitize_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact secrets and bounded values."""
        clean = {}
        for k, v in d.items():
            if any(secret_term in k.lower() for secret_term in ["key", "token", "secret", "auth"]):
                clean[k] = "[REDACTED]"
            elif isinstance(v, dict):
                clean[k] = self._sanitize_dict(v)
            elif isinstance(v, (str, int, float, bool, list)):
                # Keep bounded length for strings
                if isinstance(v, str) and len(v) > 500:
                    clean[k] = v[:497] + "..."
                else:
                    clean[k] = v
        return clean
