"""
Security & Web Best-Practices Engine.

Audits transport security, HTTP security headers, TLS certificates,
cookie flags, server information leakage, and mixed content.
Distinguishes between:
- SEO Problems (e.g. Mixed content blocking resource rendering or HTTP internal links)
- Security Vulnerabilities (e.g. Missing HSTS, vulnerable cookie flags, exposed server headers)
- Modern Web Best Practices (e.g. Missing Permissions-Policy, outdated TLS cipher suites)
"""
from __future__ import annotations
import datetime
import re
import socket
import ssl
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx

from rankintel.models.schema import (
    SecurityFindingCategory,
    SecuritySeverity,
    SecurityFinding,
    TlsCertificateDetails,
    CookieSecurityDetails,
    SecurityEvidence,
)


class SecurityEngine:
    """Specialized engine for transport, header, and web security posture evaluation."""

    def __init__(self, timeout_sec: float = 10.0):
        self.timeout_sec = timeout_sec

    def check_tls_certificate(self, hostname: str, port: int = 443) -> TlsCertificateDetails:
        """
        Connects via TLS and extracts certificate metadata, validity, and remaining days.
        """
        details = TlsCertificateDetails()
        context = ssl.create_default_context()

        try:
            with socket.create_connection((hostname, port), timeout=self.timeout_sec) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssl_sock:
                    cert = ssl_sock.getpeercert()
                    details.is_valid = True
                    details.protocol_version = ssl_sock.version()
                    cipher_info = ssl_sock.cipher()
                    if cipher_info:
                        details.cipher = f"{cipher_info[0]} ({cipher_info[1]})"

                    if cert:
                        # Subject extraction
                        for rdn in cert.get("subject", ()):
                            for k, v in rdn:
                                details.subject[k] = v

                        # Issuer extraction
                        for rdn in cert.get("issuer", ()):
                            for k, v in rdn:
                                details.issuer[k] = v

                        # Expiration date: e.g. "May 10 12:00:00 2027 GMT"
                        not_after = cert.get("notAfter")
                        if not_after:
                            details.expires_at = not_after
                            try:
                                exp_dt = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
                                now = datetime.datetime.now(datetime.timezone.utc)
                                days_left = (exp_dt - now).days
                                details.days_until_expiration = days_left
                            except Exception:
                                pass
        except ssl.SSLCertVerificationError as e:
            details.is_valid = False
            details.error_message = f"SSL Certificate Verification Failed: {e}"
        except Exception as e:
            details.is_valid = False
            details.error_message = f"TLS Handshake Failed: {e}"

        return details

    def audit_security_headers(
        self,
        headers: Dict[str, str],
        is_https: bool
    ) -> Tuple[List[SecurityFinding], Dict[str, Any]]:
        """
        Inspects response headers against modern security standards and RFC recommendations.
        """
        norm_headers = {k.lower(): v for k, v in headers.items()}
        findings: List[SecurityFinding] = []
        meta: Dict[str, Any] = {}

        # 1. Strict-Transport-Security (HSTS)
        hsts = norm_headers.get("strict-transport-security")
        if not is_https:
            pass  # HSTS is only valid over HTTPS
        elif not hsts:
            findings.append(
                SecurityFinding(
                    code="SEC_HSTS_MISSING",
                    title="Missing Strict-Transport-Security (HSTS) Header",
                    category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                    severity=SecuritySeverity.HIGH,
                    description="The server does not enforce HTTPS connections via HSTS. Users are vulnerable to SSL-stripping and man-in-the-middle attacks.",
                    recommendation="Add 'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload' to all HTTPS responses.",
                    header_name="Strict-Transport-Security"
                )
            )
            meta["hsts_present"] = False
        else:
            meta["hsts_present"] = True
            meta["hsts_raw"] = hsts
            # Check max-age
            max_age_match = re.search(r"max-age\s*=\s*(\d+)", hsts, re.IGNORECASE)
            if max_age_match:
                max_age = int(max_age_match.group(1))
                meta["hsts_max_age"] = max_age
                if max_age < 31536000:
                    findings.append(
                        SecurityFinding(
                            code="SEC_HSTS_SHORT_MAX_AGE",
                            title="HSTS Max-Age Shorter Than Recommended 1 Year",
                            category=SecurityFindingCategory.BEST_PRACTICE,
                            severity=SecuritySeverity.MEDIUM,
                            description=f"HSTS max-age is set to {max_age} seconds (recommended is at least 31536000 seconds / 1 year).",
                            recommendation="Increase HSTS max-age to 31536000 (1 year) to qualify for browser preload lists.",
                            header_name="Strict-Transport-Security",
                            header_value=hsts
                        )
                    )
            meta["hsts_include_subdomains"] = "includesubdomains" in hsts.lower()
            meta["hsts_preload"] = "preload" in hsts.lower()

        # 2. Content-Security-Policy (CSP)
        csp = norm_headers.get("content-security-policy")
        if not csp:
            findings.append(
                SecurityFinding(
                    code="SEC_CSP_MISSING",
                    title="Missing Content-Security-Policy (CSP) Header",
                    category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                    severity=SecuritySeverity.HIGH,
                    description="No Content-Security-Policy header declared. The application lacks defense-in-depth against Cross-Site Scripting (XSS) and data injection.",
                    recommendation="Implement a robust Content-Security-Policy defining trusted sources for scripts, styles, frames, and images.",
                    header_name="Content-Security-Policy"
                )
            )
            meta["csp_present"] = False
        else:
            meta["csp_present"] = True
            directives = [d.strip() for d in csp.split(";") if d.strip()]
            meta["csp_directives"] = directives

            # Check for dangerous keywords
            if "'unsafe-inline'" in csp and "nonce-" not in csp and "hash-" not in csp:
                findings.append(
                    SecurityFinding(
                        code="SEC_CSP_UNSAFE_INLINE",
                        title="CSP Allows Unrestricted 'unsafe-inline' Scripts",
                        category=SecurityFindingCategory.BEST_PRACTICE,
                        severity=SecuritySeverity.MEDIUM,
                        description="Content-Security-Policy contains 'unsafe-inline' without nonces or hashes, significantly weakening XSS protection.",
                        recommendation="Migrate inline scripts to external bundles or adopt cryptographic nonces/hashes.",
                        header_name="Content-Security-Policy",
                        header_value=csp
                    )
                )

        # 3. X-Frame-Options
        xfo = norm_headers.get("x-frame-options")
        meta["x_frame_options"] = xfo
        has_csp_frame_ancestors = csp and "frame-ancestors" in csp.lower()
        if not xfo and not has_csp_frame_ancestors:
            findings.append(
                SecurityFinding(
                    code="SEC_X_FRAME_OPTIONS_MISSING",
                    title="Missing Clickjacking Defense (X-Frame-Options / frame-ancestors)",
                    category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                    severity=SecuritySeverity.MEDIUM,
                    description="Neither X-Frame-Options nor CSP frame-ancestors is configured. The page can be embedded into malicious iframes (clickjacking risk).",
                    recommendation="Add 'X-Frame-Options: SAMEORIGIN' or 'frame-ancestors 'self'' to prevent unauthorized framing.",
                    header_name="X-Frame-Options"
                )
            )
        elif xfo and xfo.upper() not in ("DENY", "SAMEORIGIN"):
            findings.append(
                SecurityFinding(
                    code="SEC_X_FRAME_OPTIONS_INVALID",
                    title="Non-Standard X-Frame-Options Directive",
                    category=SecurityFindingCategory.BEST_PRACTICE,
                    severity=SecuritySeverity.LOW,
                    description=f"X-Frame-Options is set to '{xfo}', which is deprecated or unsupported across modern browsers.",
                    recommendation="Set X-Frame-Options to 'DENY' or 'SAMEORIGIN'.",
                    header_name="X-Frame-Options",
                    header_value=xfo
                )
            )

        # 4. X-Content-Type-Options
        xcto = norm_headers.get("x-content-type-options")
        meta["x_content_type_options"] = xcto
        if not xcto or xcto.lower() != "nosniff":
            findings.append(
                SecurityFinding(
                    code="SEC_X_CONTENT_TYPE_OPTIONS_MISSING",
                    title="Missing 'X-Content-Type-Options: nosniff'",
                    category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                    severity=SecuritySeverity.LOW,
                    description="Without 'X-Content-Type-Options: nosniff', legacy browsers may perform MIME-type sniffing, transforming non-executable files into executable scripts.",
                    recommendation="Add 'X-Content-Type-Options: nosniff' header.",
                    header_name="X-Content-Type-Options",
                    header_value=xcto
                )
            )

        # 5. Referrer-Policy
        ref_pol = norm_headers.get("referrer-policy")
        meta["referrer_policy"] = ref_pol
        if not ref_pol:
            findings.append(
                SecurityFinding(
                    code="SEC_REFERRER_POLICY_MISSING",
                    title="Missing Referrer-Policy Header",
                    category=SecurityFindingCategory.BEST_PRACTICE,
                    severity=SecuritySeverity.LOW,
                    description="No explicit Referrer-Policy declared. Internal URL query parameters may leak to external third parties when following links.",
                    recommendation="Set 'Referrer-Policy: strict-origin-when-cross-origin' to protect internal analytics and sensitive query tokens.",
                    header_name="Referrer-Policy"
                )
            )

        # 6. Permissions-Policy
        perm_pol = norm_headers.get("permissions-policy")
        meta["permissions_policy_present"] = bool(perm_pol)
        if not perm_pol:
            findings.append(
                SecurityFinding(
                    code="SEC_PERMISSIONS_POLICY_MISSING",
                    title="Missing Permissions-Policy Header",
                    category=SecurityFindingCategory.BEST_PRACTICE,
                    severity=SecuritySeverity.LOW,
                    description="Modern browser APIs (geolocation, microphone, camera) are not explicitly constrained via Permissions-Policy.",
                    recommendation="Declare 'Permissions-Policy: camera=(), microphone=(), geolocation=()' to restrict unnecessary hardware access.",
                    header_name="Permissions-Policy"
                )
            )

        # 7. Server Information Leakage
        server_leaks: List[str] = []
        srv = norm_headers.get("server")
        if srv:
            if re.search(r"[\d\.]+", srv):  # Contains version numbers (e.g., Apache/2.4.41)
                server_leaks.append(f"Server: {srv}")
                findings.append(
                    SecurityFinding(
                        code="SEC_SERVER_HEADER_VERSION_LEAK",
                        title="Server Header Discloses Software Version",
                        category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                        severity=SecuritySeverity.LOW,
                        description=f"Server header exposes exact version details ('{srv}'), easing automated exploit targeting.",
                        recommendation="Configure your web server to suppress or generalize the Server header (e.g., ServerTokens Prod in Apache).",
                        header_name="Server",
                        header_value=srv
                    )
                )

        x_powered_by = norm_headers.get("x-powered-by")
        if x_powered_by:
            server_leaks.append(f"X-Powered-By: {x_powered_by}")
            findings.append(
                SecurityFinding(
                    code="SEC_X_POWERED_BY_LEAK",
                    title="X-Powered-By Header Discloses Technology Stack",
                    category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                    severity=SecuritySeverity.LOW,
                    description=f"Header reveals backend technology ('{x_powered_by}').",
                    recommendation="Remove X-Powered-By header via server configuration or application middleware.",
                    header_name="X-Powered-By",
                    header_value=x_powered_by
                )
            )

        meta["server_leakage"] = server_leaks

        return findings, meta

    def audit_cookies(self, cookie_headers: List[str], is_https: bool) -> Tuple[List[CookieSecurityDetails], List[SecurityFinding]]:
        """
        Inspects cookies for Secure, HttpOnly, and SameSite attributes.
        """
        cookie_list: List[CookieSecurityDetails] = []
        findings: List[SecurityFinding] = []

        for raw_cookie in cookie_headers:
            parts = [p.strip() for p in raw_cookie.split(";") if p.strip()]
            if not parts:
                continue
            name_val = parts[0]
            c_name = name_val.split("=", 1)[0].strip()

            c_secure = False
            c_httponly = False
            c_samesite: Optional[str] = None
            issues: List[str] = []

            for part in parts[1:]:
                p_lower = part.lower()
                if p_lower == "secure":
                    c_secure = True
                elif p_lower == "httponly":
                    c_httponly = True
                elif p_lower.startswith("samesite"):
                    if "=" in part:
                        c_samesite = part.split("=", 1)[1].strip()

            # Flag security issues
            if is_https and not c_secure:
                issues.append("Missing Secure flag on HTTPS")
                findings.append(
                    SecurityFinding(
                        code="SEC_COOKIE_INSECURE",
                        title=f"Cookie '{c_name}' Missing Secure Flag",
                        category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                        severity=SecuritySeverity.HIGH,
                        description=f"Cookie '{c_name}' transmitted over HTTPS lacks the Secure flag, risking interception over plaintext HTTP fallback.",
                        recommendation=f"Add 'Secure' attribute to Set-Cookie for '{c_name}'."
                    )
                )

            if not c_httponly:
                issues.append("Missing HttpOnly flag")
                findings.append(
                    SecurityFinding(
                        code="SEC_COOKIE_NO_HTTPONLY",
                        title=f"Cookie '{c_name}' Missing HttpOnly Flag",
                        category=SecurityFindingCategory.SECURITY_VULNERABILITY,
                        severity=SecuritySeverity.MEDIUM,
                        description=f"Cookie '{c_name}' is accessible to JavaScript document.cookie, exposing session identifiers to XSS attacks.",
                        recommendation=f"Add 'HttpOnly' attribute to Set-Cookie for '{c_name}'."
                    )
                )

            if not c_samesite:
                issues.append("Missing SameSite attribute")
                findings.append(
                    SecurityFinding(
                        code="SEC_COOKIE_NO_SAMESITE",
                        title=f"Cookie '{c_name}' Missing SameSite Attribute",
                        category=SecurityFindingCategory.BEST_PRACTICE,
                        severity=SecuritySeverity.LOW,
                        description=f"Cookie '{c_name}' lacks explicit SameSite configuration, risking Cross-Site Request Forgery (CSRF).",
                        recommendation=f"Set 'SameSite=Lax' or 'SameSite=Strict' for '{c_name}'."
                    )
                )

            cookie_list.append(
                CookieSecurityDetails(
                    name=c_name,
                    secure=c_secure,
                    httponly=c_httponly,
                    samesite=c_samesite,
                    issues=issues
                )
            )

        return cookie_list, findings

    def audit_mixed_content(self, raw_html: str, url: str) -> Tuple[List[str], List[SecurityFinding]]:
        """
        Detects active and passive mixed content resources on HTTPS pages.
        """
        mixed_resources: List[str] = []
        findings: List[SecurityFinding] = []

        parsed = urlparse(url)
        if parsed.scheme.lower() != "https" or not raw_html:
            return mixed_resources, findings

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Active mixed content: <script src="http://">, <link rel="stylesheet" href="http://">, <iframe src="http://">
        active_tags = []
        for s in soup.find_all("script", src=True):
            if s["src"].startswith("http://"):
                active_tags.append(s["src"])
        for link in soup.find_all("link", rel=lambda v: v and "stylesheet" in (v if isinstance(v, list) else [str(v).lower()]), href=True):
            if link["href"].startswith("http://"):
                active_tags.append(link["href"])
        for iframe in soup.find_all("iframe", src=True):
            if iframe["src"].startswith("http://"):
                active_tags.append(iframe["src"])

        if active_tags:
            mixed_resources.extend(active_tags)
            findings.append(
                SecurityFinding(
                    code="SEC_ACTIVE_MIXED_CONTENT",
                    title="Active Mixed Content Detected (Insecure Scripts / Styles / Iframes)",
                    category=SecurityFindingCategory.SEO_PROBLEM,
                    severity=SecuritySeverity.CRITICAL,
                    description=f"Detected {len(active_tags)} active insecure resources (scripts/stylesheets/iframes) loaded over http://. Modern browsers block these automatically, breaking site rendering, functionality, and search crawler indexation.",
                    recommendation="Migrate all active resource URLs from http:// to https://."
                )
            )

        # 2. Passive mixed content: <img src="http://">, <video src="http://">, <audio src="http://">
        passive_tags = []
        for img in soup.find_all("img", src=True):
            if img["src"].startswith("http://"):
                passive_tags.append(img["src"])
        for v in soup.find_all(["video", "audio"], src=True):
            if v["src"].startswith("http://"):
                passive_tags.append(v["src"])

        if passive_tags:
            mixed_resources.extend(passive_tags)
            findings.append(
                SecurityFinding(
                    code="SEC_PASSIVE_MIXED_CONTENT",
                    title="Passive Mixed Content Detected (Insecure Images / Media)",
                    category=SecurityFindingCategory.SEO_PROBLEM,
                    severity=SecuritySeverity.MEDIUM,
                    description=f"Detected {len(passive_tags)} passive media assets loaded over http://. Browsers display 'Not Secure' padlock warnings to users.",
                    recommendation="Update media URLs to https:// or use protocol-relative or site-root paths."
                )
            )

        return mixed_resources, findings


    def audit_headers_and_html(
        self,
        url: str,
        headers: Dict[str, str],
        cookie_headers: Optional[List[str]] = None,
        raw_html: Optional[str] = None,
        tls_details: Optional[TlsCertificateDetails] = None
    ) -> SecurityEvidence:
        """
        Synthesizes header audit, cookie inspection, mixed content, and TLS cert into SecurityEvidence.
        """
        parsed = urlparse(url)
        is_https = parsed.scheme.lower() == "https"

        # Audit headers
        findings, meta = self.audit_security_headers(headers, is_https)

        # Audit cookies
        cookies, cookie_findings = self.audit_cookies(cookie_headers or [], is_https)
        findings.extend(cookie_findings)

        # Audit mixed content
        mixed_resources: List[str] = []
        if raw_html:
            mixed_resources, mixed_findings = self.audit_mixed_content(raw_html, url)
            findings.extend(mixed_findings)

        # Check TLS details
        if is_https and tls_details:
            if not tls_details.is_valid:
                findings.append(
                    SecurityFinding(
                        code="SEC_TLS_INVALID",
                        title="Invalid or Broken TLS Certificate",
                        category=SecurityFindingCategory.SEO_PROBLEM,
                        severity=SecuritySeverity.CRITICAL,
                        description=f"TLS certificate validation failed: {tls_details.error_message}. Browsers and search crawlers will abort connections.",
                        recommendation="Re-issue a valid TLS certificate from an authorized certificate authority immediately."
                    )
                )
            elif tls_details.days_until_expiration is not None:
                if tls_details.days_until_expiration < 0:
                    findings.append(
                        SecurityFinding(
                            code="SEC_TLS_EXPIRED",
                            title="TLS Certificate is Expired",
                            category=SecurityFindingCategory.SEO_PROBLEM,
                            severity=SecuritySeverity.CRITICAL,
                            description=f"TLS certificate expired {abs(tls_details.days_until_expiration)} days ago.",
                            recommendation="Renew and deploy an active TLS certificate immediately."
                        )
                    )
                elif tls_details.days_until_expiration < 30:
                    findings.append(
                        SecurityFinding(
                            code="SEC_TLS_EXPIRING_SOON",
                            title="TLS Certificate Expiring Soon (< 30 Days)",
                            category=SecurityFindingCategory.BEST_PRACTICE,
                            severity=SecuritySeverity.MEDIUM,
                            description=f"TLS certificate will expire in {tls_details.days_until_expiration} days.",
                            recommendation="Ensure automated certificate renewal (e.g. Certbot cron) is functioning."
                        )
                    )

        from rankintel.models.schema import SecurityStatus
        
        # Calculate counts
        critical_count = sum(1 for f in findings if f.severity == SecuritySeverity.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == SecuritySeverity.HIGH)
        medium_count = sum(1 for f in findings if f.severity == SecuritySeverity.MEDIUM)
        low_count = sum(1 for f in findings if f.severity == SecuritySeverity.LOW)
        info_count = sum(1 for f in findings if f.severity == SecuritySeverity.INFO)
        total_findings = len(findings)
        
        overall_status = SecurityStatus.UNKNOWN
        if critical_count > 0 or high_count > 0 or not is_https:
            overall_status = SecurityStatus.FAIL
        elif medium_count > 0 or low_count > 0:
            overall_status = SecurityStatus.PARTIAL
        else:
            if headers:
                overall_status = SecurityStatus.PASS
            else:
                overall_status = SecurityStatus.UNAVAILABLE

        # Recommendations list
        recommendations = [f.recommendation for f in findings if f.recommendation]

        return SecurityEvidence(
            url=url,
            is_https=is_https,
            overall_status=overall_status,
            total_findings=total_findings,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            info_count=info_count,
            headers_evaluated=headers,
            hsts_present=meta.get("hsts_present", False),
            hsts_include_subdomains=meta.get("hsts_include_subdomains", False),
            hsts_preload=meta.get("hsts_preload", False),
            hsts_max_age=meta.get("hsts_max_age"),
            csp_present=meta.get("csp_present", False),
            csp_directives=meta.get("csp_directives", []),
            x_frame_options=meta.get("x_frame_options"),
            x_content_type_options=meta.get("x_content_type_options"),
            referrer_policy=meta.get("referrer_policy"),
            permissions_policy_present=meta.get("permissions_policy_present", False),
            server_leakage=meta.get("server_leakage", []),
            mixed_content_resources=mixed_resources,
            tls_details=tls_details,
            cookies=cookies,
            findings=findings,
            recommendations=recommendations,
        )

    async def audit_url(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None,
        raw_html: Optional[str] = None
    ) -> SecurityEvidence:
        """
        Asynchronously fetches headers, cookies, and TLS certificate for target URL.
        """
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        is_https = parsed.scheme.lower() == "https"

        tls_details: Optional[TlsCertificateDetails] = None
        if is_https and hostname:
            try:
                tls_details = self.check_tls_certificate(hostname, parsed.port or 443)
            except Exception:
                pass

        headers: Dict[str, str] = {}
        cookie_headers: List[str] = []
        body_html = raw_html

        try:
            if client is not None:
                resp = await client.get(url, follow_redirects=True, timeout=self.timeout_sec)
            else:
                async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True) as local_client:
                    resp = await local_client.get(url)

            headers = dict(resp.headers)
            # httpx multiple Set-Cookie headers
            cookie_headers = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
            if not body_html and "text/html" in headers.get("content-type", ""):
                body_html = resp.text
        except Exception as e:
            # Failed request
            findings = [
                SecurityFinding(
                    code="SEC_CONNECTION_ERROR",
                    title="Failed to Connect to Host",
                    category=SecurityFindingCategory.SEO_PROBLEM,
                    severity=SecuritySeverity.CRITICAL,
                    description=f"HTTP connection failed: {e}",
                    recommendation="Ensure the web server is listening and DNS records resolve correctly."
                )
            ]
            return SecurityEvidence(
                url=url,
                is_https=is_https,
                score=0,
                grade="F",
                findings=findings,
                tls_details=tls_details
            )

        return self.audit_headers_and_html(
            url=url,
            headers=headers,
            cookie_headers=cookie_headers,
            raw_html=body_html,
            tls_details=tls_details
        )

    def audit_url_sync(
        self,
        url: str,
        raw_html: Optional[str] = None
    ) -> SecurityEvidence:
        """
        Synchronously fetches headers, cookies, and TLS certificate for target URL.
        """
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        is_https = parsed.scheme.lower() == "https"

        tls_details: Optional[TlsCertificateDetails] = None
        if is_https and hostname:
            try:
                tls_details = self.check_tls_certificate(hostname, parsed.port or 443)
            except Exception:
                pass

        headers: Dict[str, str] = {}
        cookie_headers: List[str] = []
        body_html = raw_html

        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                resp = client.get(url)
                headers = dict(resp.headers)
                cookie_headers = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
                if not body_html and "text/html" in headers.get("content-type", ""):
                    body_html = resp.text
        except Exception as e:
            findings = [
                SecurityFinding(
                    code="SEC_CONNECTION_ERROR",
                    title="Failed to Connect to Host",
                    category=SecurityFindingCategory.SEO_PROBLEM,
                    severity=SecuritySeverity.CRITICAL,
                    description=f"HTTP connection failed: {e}",
                    recommendation="Ensure the web server is reachable."
                )
            ]
            return SecurityEvidence(
                url=url,
                is_https=is_https,
                score=0,
                grade="F",
                findings=findings,
                tls_details=tls_details
            )

        return self.audit_headers_and_html(
            url=url,
            headers=headers,
            cookie_headers=cookie_headers,
            raw_html=body_html,
            tls_details=tls_details
        )
