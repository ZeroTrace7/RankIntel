"""
Trust Evaluator — 5-Layer E-E-A-T & Trust Signal Aggregation.
Ported and enhanced from geo-optimizer trust_stack.py architecture.
Evaluates signals without additional HTTP requests.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    TrustLayerScore,
    TrustStackResult,
    OnPageEvidence,
    SchemaEvidence,
    GeoAeoEvidence
)

# Academic & Authority domains
AUTHORITATIVE_DOMAINS = [
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "doi.org",
    "scholar.google.com",
    "arxiv.org",
    "wikipedia.org",
    "wikidata.org",
    "nature.com",
    "sciencedirect.com",
    "ieee.org",
    "acm.org",
    "gov",
    "edu",
]

# Social proof domains
SOCIAL_DOMAINS = [
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "github.com",
    "pinterest.com",
    "reddit.com",
]

# Regex for statistics and research patterns
STATISTICS_PATTERN = re.compile(
    r"\d+[\.,]?\d*\s*(?:%|percent(?:age)?)"
    r"|(?:\d{2,}[\.,]?\d*)\s+(?:study|studies|research|survey|report|data)\b"
    r"|(?:according\s+to\s+(?:(?:a|the)\s+)?(?:study|research|survey|report|source))\b",
    re.IGNORECASE,
)

REFERENCES_HEADING_PATTERNS = [
    "references", "sources", "bibliography", "citations", "further reading", "fonti", "riferimenti"
]

class TrustEvaluator:
    """Evaluates 5-layer trust stack and E-E-A-T credibility metrics."""

    @classmethod
    def evaluate(
        cls,
        url: str,
        on_page: OnPageEvidence,
        schema: SchemaEvidence,
        geo: Optional[GeoAeoEvidence] = None,
        html_soup: Optional[BeautifulSoup] = None,
    ) -> TrustStackResult:
        layers: Dict[str, TrustLayerScore] = {}

        # Layer 1: Technical Trust
        layers["technical"] = cls._evaluate_technical_trust(url, on_page.response_headers)

        # Layer 2: Identity Trust
        layers["identity"] = cls._evaluate_identity_trust(url, on_page, schema, html_soup)

        # Layer 3: Social Trust
        layers["social"] = cls._evaluate_social_trust(schema, on_page, html_soup)

        # Layer 4: Academic & Authority Trust
        layers["academic"] = cls._evaluate_academic_trust(on_page, geo, html_soup)

        # Layer 5: Consistency & Compliance Trust
        layers["consistency"] = cls._evaluate_consistency_trust(on_page, schema, html_soup)

        # Calculate totals
        raw_score = sum(layer.score for layer in layers.values())
        overall_score = int(round((raw_score / 25.0) * 100))

        if overall_score >= 80:
            grade = "A"
        elif overall_score >= 65:
            grade = "B"
        elif overall_score >= 50:
            grade = "C"
        elif overall_score >= 35:
            grade = "D"
        else:
            grade = "F"

        summary = (
            f"Trust Grade: {grade} ({overall_score}/100, Raw {raw_score}/25). "
            f"Strongest layer: {max(layers.values(), key=lambda l: l.score).label}. "
            f"Weakest layer: {min(layers.values(), key=lambda l: l.score).label}."
        )

        return TrustStackResult(
            overall_score=overall_score,
            raw_score=raw_score,
            grade=grade,
            layers=layers,
            summary=summary,
        )

    @classmethod
    def _evaluate_technical_trust(cls, url: str, headers: Dict[str, str]) -> TrustLayerScore:
        score = 0
        found = []
        missing = []
        lower_headers = {k.lower(): v for k, v in headers.items()}

        # 1. HTTPS (+2)
        if url.lower().startswith("https://"):
            score += 2
            found.append("HTTPS Protocol Active (+2)")
        else:
            missing.append("HTTPS Not Enabled (Insecure HTTP)")

        # 2. HSTS (+1)
        if "strict-transport-security" in lower_headers:
            score += 1
            found.append("Strict-Transport-Security (HSTS)")
        else:
            missing.append("HSTS Header Missing")

        # 3. Content Security Policy (+1)
        if "content-security-policy" in lower_headers:
            score += 1
            found.append("Content-Security-Policy (CSP)")
        else:
            missing.append("Content-Security-Policy Header Missing")

        # 4. X-Frame-Options or frame-ancestors (+1)
        csp_val = lower_headers.get("content-security-policy", "")
        if "x-frame-options" in lower_headers or "frame-ancestors" in csp_val.lower():
            score += 1
            found.append("Clickjacking Protection (X-Frame-Options/frame-ancestors)")
        else:
            missing.append("X-Frame-Options Header Missing")

        return TrustLayerScore(
            name="technical",
            label="Technical & Infrastructure Trust",
            score=min(score, 5),
            max_score=5,
            signals_found=found,
            signals_missing=missing,
        )

    @classmethod
    def _evaluate_identity_trust(
        cls,
        url: str,
        on_page: OnPageEvidence,
        schema: SchemaEvidence,
        soup: Optional[BeautifulSoup],
    ) -> TrustLayerScore:
        score = 0
        found = []
        missing = []

        # 1. Organization Schema (+1)
        has_org = schema.has_organization or any("Organization" in t or "Corporation" in t or "LocalBusiness" in t for t in schema.detected_types)
        if has_org:
            score += 1
            found.append("Organization / LocalBusiness Structured Data")
        else:
            missing.append("No Organization/Business Schema in JSON-LD")

        # 2. Identifiable Author / Person (+1)
        has_author = schema.has_author or any("Person" in t or "Author" in t for t in schema.detected_types)
        if not has_author and soup:
            author_meta = soup.find("meta", attrs={"name": re.compile(r"author", re.I)})
            if author_meta and author_meta.get("content"):
                has_author = True
        if has_author:
            score += 1
            found.append("Identified Author / Person Entity")
        else:
            missing.append("No Author Attribution in Meta or Schema")

        # 3. About page link (+1)
        has_about = False
        all_links = on_page.internal_links + on_page.external_links
        if any(re.search(r"/(about|chi-siamo|who-we-are|company)", link.lower()) for link in all_links):
            has_about = True
        elif soup and soup.find("a", href=re.compile(r"(about|company|chi-siamo)", re.I)):
            has_about = True

        if has_about:
            score += 1
            found.append("About Page Link")
        else:
            missing.append("No Clear 'About' Page Link Found")

        # 4. Contact page link / info (+1)
        has_contact = False
        if any(re.search(r"/(contact|contatti|support|help)", link.lower()) for link in all_links):
            has_contact = True
        elif soup and soup.find("a", href=re.compile(r"(contact|contatti|support)", re.I)):
            has_contact = True

        if has_contact:
            score += 1
            found.append("Contact / Support Page Link")
        else:
            missing.append("No Contact Page Link Found")

        # 5. Brand consistency (+1)
        title = on_page.title.lower()
        h1s = " ".join(on_page.h1_text).lower()
        parsed = urlparse(url)
        brand_hint = parsed.netloc.split(".")[0].lower()

        if brand_hint in title or (on_page.h1_text and any(word in h1s for word in title.split()[:2])):
            score += 1
            found.append("Consistent Brand Identity across Title/H1")
        else:
            missing.append("Weak or Inconsistent Brand Signature")

        return TrustLayerScore(
            name="identity",
            label="Entity & Identity Trust",
            score=min(score, 5),
            max_score=5,
            signals_found=found,
            signals_missing=missing,
        )

    @classmethod
    def _evaluate_social_trust(
        cls,
        schema: SchemaEvidence,
        on_page: OnPageEvidence,
        soup: Optional[BeautifulSoup],
    ) -> TrustLayerScore:
        score = 0
        found = []
        missing = []

        # 1. sameAs in Schema (+1)
        if schema.sameas_urls:
            score += 1
            found.append(f"Entity sameAs Profiles ({len(schema.sameas_urls)} linked)")
        else:
            missing.append("No sameAs Links in Schema.org")

        # 2. Multiple sameAs (3+) (+1)
        if len(schema.sameas_urls) >= 3:
            score += 1
            found.append("Multi-Platform Verification (3+ sameAs)")
        else:
            missing.append("Fewer than 3 verified sameAs profiles")

        # 3. Social Media Links in DOM (+1)
        detected_social = set()
        all_ext = on_page.external_links
        if soup:
            for a in soup.find_all("a", href=True):
                all_ext.append(a["href"])

        for href in all_ext:
            href_low = href.lower()
            for s_dom in SOCIAL_DOMAINS:
                if s_dom in href_low:
                    detected_social.add(s_dom)

        if detected_social:
            score += 1
            found.append(f"Linked Social Profiles ({', '.join(list(detected_social)[:3])})")
        else:
            missing.append("No Outbound Social Media Profile Links")

        # 4. Reviews / Testimonials (+1)
        has_reviews = any("Review" in t or "AggregateRating" in t for t in schema.detected_types)
        if not has_reviews and soup:
            if soup.find(attrs={"class": re.compile(r"(review|testimonial|testimony)", re.I)}):
                has_reviews = True
            elif soup.find(attrs={"itemprop": "review"}):
                has_reviews = True

        if has_reviews:
            score += 1
            found.append("Customer Reviews / Testimonials Evidence")
        else:
            missing.append("No Reviews or Testimonials Detected")

        # 5. Knowledge Graph / Authority presence (+1)
        has_kg = any("wikipedia.org" in u.lower() or "wikidata.org" in u.lower() for u in schema.sameas_urls)
        if not has_kg and any("wikipedia.org" in link.lower() or "wikidata.org" in link.lower() for link in all_ext):
            has_kg = True

        if has_kg:
            score += 1
            found.append("Knowledge Graph Anchor (Wikipedia/Wikidata link)")
        else:
            missing.append("No Knowledge Graph Pillar Link (Wikidata/Wikipedia)")

        return TrustLayerScore(
            name="social",
            label="Social Proof & Reputation Trust",
            score=min(score, 5),
            max_score=5,
            signals_found=found,
            signals_missing=missing,
        )

    @classmethod
    def _evaluate_academic_trust(
        cls,
        on_page: OnPageEvidence,
        geo: Optional[GeoAeoEvidence],
        soup: Optional[BeautifulSoup],
    ) -> TrustLayerScore:
        score = 0
        found = []
        missing = []

        # 1. Numerical data & statistics (+1)
        stat_density = geo.statistical_density_per_1000 if geo else 0.0
        if stat_density >= 5.0 or (geo and geo.passage_density_ratio > 0.1):
            score += 1
            found.append(f"Data-Rich Content ({stat_density:.1f} stats per 1,000 words)")
        else:
            missing.append("Sparse Quantitative Data / Statistics")

        # 2. External Non-Social Sources (+1)
        non_social_ext = []
        for l in on_page.external_links:
            if not any(s in l.lower() for s in SOCIAL_DOMAINS):
                non_social_ext.append(l)

        if len(non_social_ext) >= 2 or (geo and geo.outbound_citations_count >= 2):
            score += 1
            found.append(f"External Source Citations ({len(non_social_ext)} non-social links)")
        else:
            missing.append("Few or No External Non-Social Citations")

        # 3. Authoritative Source Citations (.gov, .edu, doi, pubmed) (+1)
        auth_links_found = []
        for l in on_page.external_links:
            for ad in AUTHORITATIVE_DOMAINS:
                if ad in l.lower():
                    auth_links_found.append(ad)
                    break

        if auth_links_found or (geo and geo.authoritative_citations_count > 0):
            score += 1
            found.append(f"Authoritative Domain Links ({', '.join(list(set(auth_links_found))[:2]) or 'Academic/Gov'})")
        else:
            missing.append("No Links to Recognized Authoritative Sources (.gov, .edu, DOI, PubMed)")

        # 4. References / Bibliography Section (+1)
        has_ref = False
        all_headings = on_page.h2_text + on_page.h3_text
        if any(any(ref in h.lower() for ref in REFERENCES_HEADING_PATTERNS) for h in all_headings):
            has_ref = True
        elif soup:
            for tag in soup.find_all(["h2", "h3", "h4"]):
                if any(p in tag.get_text().lower() for p in REFERENCES_HEADING_PATTERNS):
                    has_ref = True
                    break

        if has_ref:
            score += 1
            found.append("Dedicated Sources / References Section")
        else:
            missing.append("No Dedicated References or Sources Section")

        # 5. Original Statistical Research Patterns (+1)
        stats_matches = 0
        if soup and soup.body:
            body_text = soup.body.get_text(separator=" ", strip=True)
            stats_matches = len(STATISTICS_PATTERN.findall(body_text))

        if stats_matches >= 3:
            score += 1
            found.append(f"Statistical Evidence Patterns ({stats_matches} research/metric instances)")
        else:
            missing.append("Few Formal Statistical Patterns (Percentages / Research Citations)")

        return TrustLayerScore(
            name="academic",
            label="Academic & Authority Trust",
            score=min(score, 5),
            max_score=5,
            signals_found=found,
            signals_missing=missing,
        )

    @classmethod
    def _evaluate_consistency_trust(
        cls,
        on_page: OnPageEvidence,
        schema: SchemaEvidence,
        soup: Optional[BeautifulSoup],
    ) -> TrustLayerScore:
        score = 0
        found = []
        missing = []

        all_links = on_page.internal_links + on_page.external_links

        # 1. Privacy Policy (+1)
        has_privacy = any("privacy" in l.lower() or "politica-privacy" in l.lower() for l in all_links)
        if not has_privacy and soup:
            if soup.find("a", href=re.compile(r"privacy", re.I)):
                has_privacy = True
        if has_privacy:
            score += 1
            found.append("Privacy Policy Documented")
        else:
            missing.append("No Privacy Policy Link Detected")

        # 2. Terms of Service / Terms of Use (+1)
        has_terms = any(re.search(r"(terms|conditions|termini)", l.lower()) for l in all_links)
        if not has_terms and soup:
            if soup.find("a", href=re.compile(r"(terms|conditions)", re.I)):
                has_terms = True
        if has_terms:
            score += 1
            found.append("Terms of Service / Terms of Use Documented")
        else:
            missing.append("No Terms of Service Link Detected")

        # 3. Copyright / Current Notice (+1)
        has_copyright = False
        if soup and soup.body:
            body_text = soup.body.get_text()
            if re.search(r"(©|copyright|\(c\))\s*(?:20\d\d)", body_text, re.I):
                has_copyright = True
        if has_copyright:
            score += 1
            found.append("Dated Copyright Notice")
        else:
            missing.append("Missing or Undated Copyright Notice")

        # 4. Canonical consistency (+1)
        if on_page.canonical_url:
            score += 1
            found.append(f"Canonical URL Explicit ({on_page.canonical_url[:40]}...)")
        else:
            missing.append("Missing Canonical Tag")

        # 5. Freshness / Schema Dates (+1)
        has_dates = False
        if soup:
            if soup.find("time") or soup.find(attrs={"property": re.compile(r"date", re.I)}):
                has_dates = True
        if has_dates:
            score += 1
            found.append("Machine-Readable Timestamp / Freshness Signal")
        else:
            missing.append("No Machine-Readable Publication/Modification Timestamps")

        return TrustLayerScore(
            name="consistency",
            label="Consistency & Compliance Trust",
            score=min(score, 5),
            max_score=5,
            signals_found=found,
            signals_missing=missing,
        )
