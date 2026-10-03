"""
Unit & Integration Tests for Security & Web Best-Practices Engine (Phase 7.2).
"""
import pytest
import datetime
from unittest.mock import patch, MagicMock
import httpx

from rankintel.engines.security_engine import SecurityEngine
from rankintel.models.schema import (
    SecurityFindingCategory,
    SecuritySeverity,
    SecurityEvidence,
    TlsCertificateDetails,
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
)
from rankintel.reporters.markdown import MarkdownReporter


class TestSecurityEngineHeaders:
    @pytest.fixture
    def engine(self):
        return SecurityEngine()

    def test_hsts_missing_on_https(self, engine):
        headers = {}
        findings, meta = engine.audit_security_headers(headers, is_https=True)
        hsts_finding = next((f for f in findings if f.code == "SEC_HSTS_MISSING"), None)
        assert hsts_finding is not None
        assert hsts_finding.category == SecurityFindingCategory.SECURITY_VULNERABILITY
        assert hsts_finding.severity == SecuritySeverity.HIGH

    def test_hsts_short_max_age(self, engine):
        headers = {"Strict-Transport-Security": "max-age=86400"}
        findings, meta = engine.audit_security_headers(headers, is_https=True)
        age_finding = next((f for f in findings if f.code == "SEC_HSTS_SHORT_MAX_AGE"), None)
        assert age_finding is not None
        assert meta["hsts_max_age"] == 86400

    def test_hsts_hardened(self, engine):
        headers = {"Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"}
        findings, meta = engine.audit_security_headers(headers, is_https=True)
        hsts_findings = [f for f in findings if "HSTS" in f.code]
        assert len(hsts_findings) == 0
        assert meta["hsts_include_subdomains"] is True
        assert meta["hsts_preload"] is True

    def test_csp_missing_and_unsafe_inline(self, engine):
        # Missing
        findings, meta = engine.audit_security_headers({}, is_https=True)
        assert any(f.code == "SEC_CSP_MISSING" for f in findings)

        # Unsafe inline
        csp_unsafe = {"Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'"}
        findings2, meta2 = engine.audit_security_headers(csp_unsafe, is_https=True)
        assert any(f.code == "SEC_CSP_UNSAFE_INLINE" for f in findings2)

    def test_x_frame_options_and_nosniff(self, engine):
        findings, meta = engine.audit_security_headers({}, is_https=True)
        assert any(f.code == "SEC_X_FRAME_OPTIONS_MISSING" for f in findings)
        assert any(f.code == "SEC_X_CONTENT_TYPE_OPTIONS_MISSING" for f in findings)

        # Configured properly
        good_headers = {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=()",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        }
        findings_good, _ = engine.audit_security_headers(good_headers, is_https=True)
        assert len(findings_good) == 0

    def test_server_and_stack_leakage(self, engine):
        headers = {
            "Server": "Apache/2.4.41 (Ubuntu)",
            "X-Powered-By": "PHP/7.4.3",
        }
        findings, meta = engine.audit_security_headers(headers, is_https=True)
        assert any(f.code == "SEC_SERVER_HEADER_VERSION_LEAK" for f in findings)
        assert any(f.code == "SEC_X_POWERED_BY_LEAK" for f in findings)
        assert len(meta["server_leakage"]) == 2


class TestCookieSecurity:
    @pytest.fixture
    def engine(self):
        return SecurityEngine()

    def test_cookies_missing_flags(self, engine):
        cookie_headers = [
            "sessionid=xyz123; Path=/",
            "tracking=abc; Path=/; Secure; SameSite=Lax",
        ]
        cookies, findings = engine.audit_cookies(cookie_headers, is_https=True)

        assert len(cookies) == 2
        # Session cookie has no Secure, no HttpOnly, no SameSite
        c1 = cookies[0]
        assert not c1.secure
        assert not c1.httponly
        assert c1.samesite is None
        assert len(c1.issues) == 3

        # Tracking cookie has Secure and SameSite, but not HttpOnly
        c2 = cookies[1]
        assert c2.secure
        assert c2.samesite == "Lax"
        assert not c2.httponly

        assert any(f.code == "SEC_COOKIE_INSECURE" for f in findings)
        assert any(f.code == "SEC_COOKIE_NO_HTTPONLY" for f in findings)


class TestMixedContent:
    @pytest.fixture
    def engine(self):
        return SecurityEngine()

    def test_active_and_passive_mixed_content(self, engine):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="http://cdn.example.com/analytics.js"></script>
            <link rel="stylesheet" href="http://cdn.example.com/style.css">
        </head>
        <body>
            <img src="http://cdn.example.com/banner.jpg" />
            <img src="https://cdn.example.com/logo.png" />
            <iframe src="http://insecure.example.com/frame"></iframe>
        </body>
        </html>
        """
        resources, findings = engine.audit_mixed_content(html, "https://secure.example.com")
        assert len(resources) == 4
        assert any(f.code == "SEC_ACTIVE_MIXED_CONTENT" for f in findings)
        assert any(f.code == "SEC_PASSIVE_MIXED_CONTENT" for f in findings)

    def test_no_mixed_content_on_http_site(self, engine):
        html = '<html><script src="http://cdn.example.com/app.js"></script></html>'
        resources, findings = engine.audit_mixed_content(html, "http://plain.example.com")
        assert len(resources) == 0
        assert len(findings) == 0


class TestTlsCertificateAudit:
    @pytest.fixture
    def engine(self):
        return SecurityEngine()

    def test_expired_certificate_triggers_critical_finding(self, engine):
        tls = TlsCertificateDetails(
            is_valid=True,
            expires_at="Jan 01 00:00:00 2020 GMT",
            days_until_expiration=-100,
            protocol_version="TLSv1.3",
        )
        evidence = engine.audit_headers_and_html(
            url="https://expired.example.com",
            headers={"Strict-Transport-Security": "max-age=31536000"},
            tls_details=tls
        )
        assert any(f.code == "SEC_TLS_EXPIRED" for f in evidence.findings)
        assert evidence.overall_status.name in ("FAIL", "PARTIAL")

    def test_cert_expiring_soon_triggers_medium_finding(self, engine):
        tls = TlsCertificateDetails(
            is_valid=True,
            expires_at="May 01 00:00:00 2026 GMT",
            days_until_expiration=15,
            protocol_version="TLSv1.3",
        )
        evidence = engine.audit_headers_and_html(
            url="https://expiring.example.com",
            headers={"Strict-Transport-Security": "max-age=31536000"},
            tls_details=tls
        )
        assert any(f.code == "SEC_TLS_EXPIRING_SOON" for f in evidence.findings)


class TestSecurityEngineAsyncAndSync:
    @pytest.fixture
    def engine(self):
        return SecurityEngine()

    @pytest.mark.anyio
    async def test_async_audit_url_with_mock_client(self, engine):
        async def handler(request: httpx.Request):
            return httpx.Response(
                200,
                headers={
                    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                    "Content-Security-Policy": "default-src 'self'",
                    "X-Frame-Options": "DENY",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Type": "text/html",
                },
                text="<html><body>Hello</body></html>"
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.object(engine, "check_tls_certificate", return_value=TlsCertificateDetails(is_valid=True, days_until_expiration=120, protocol_version="TLSv1.3")):
                evidence = await engine.audit_url("https://example.com", client=client)

        assert evidence.is_https is True
        assert evidence.hsts_present is True
        assert evidence.csp_present is True
        assert evidence.overall_status.name in ("PARTIAL", "FAIL", "PASS")

    def test_sync_audit_url(self, engine):
        mock_resp = MagicMock()
        mock_resp.headers = {
            "strict-transport-security": "max-age=31536000",
            "content-security-policy": "default-src 'self'",
            "content-type": "text/html",
        }
        mock_resp.text = "<html><body>Safe</body></html>"

        with patch("httpx.Client.get", return_value=mock_resp), \
             patch.object(engine, "check_tls_certificate", return_value=TlsCertificateDetails(is_valid=True, days_until_expiration=60)):
            evidence = engine.audit_url_sync("https://example.com")

        assert evidence.is_https is True
        assert evidence.hsts_present is True


class TestMarkdownReporterSecurityIntegration:
    def test_reporter_renders_security_section(self):
        engine = SecurityEngine()
        headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        }
        tls = TlsCertificateDetails(is_valid=True, days_until_expiration=90, protocol_version="TLSv1.3")
        sec_ev = engine.audit_headers_and_html("https://example.com", headers=headers, tls_details=tls)

        report = SynthesisReport(
            url="https://example.com",
            domain="example.com",
            timestamp="2026-10-02T20:00:00",
            overall_health_score=90,
            security_score=100,
            unified_on_page=OnPageEvidence(url="https://example.com", status_code=200, title="Example"),
            unified_robots=RobotsEvidence(found=True),
            unified_schema=SchemaEvidence(),
            unified_geo=GeoAeoEvidence(),
            unified_security=sec_ev,
        )

        reporter = MarkdownReporter()
        md = reporter.render(report)

        assert "SECURITY & WEB BEST PRACTICES" in md
        assert "Security Posture Score" in md
        assert "Strict-Transport-Security" in md
        assert "Content-Security-Policy" in md
        assert "TLS Certificate" in md
