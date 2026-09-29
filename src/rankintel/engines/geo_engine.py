"""
GEO Engine Adapter — Generative Engine Optimization & Answer Engine Intelligence.
Implements Princeton GEO / AutoGEO citation metrics, llms.txt v2 validation, and AI bot trust signals.
"""
from __future__ import annotations
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from collections import Counter
from typing import Dict, List, Optional

from rankintel.models.schema import (
    GeoCitabilityMethod,
    GeoAeoEvidence,
    EngineResult
)

AUTHORITATIVE_TLDS = {".edu", ".gov", ".org", ".nic.in", ".gov.in"}
AUTHORITATIVE_DOMAINS = {
    "wikipedia.org", "pubmed.ncbi.nlm.nih.gov", "scholar.google.com",
    "nature.com", "sciencedirect.com", "arxiv.org", "who.int",
    "cdc.gov", "bis.gov.in", "standard.gov", "iso.org"
}

STAT_RE = re.compile(
    r"\b\d+(?:\.\d+)?%|\$\d+(?:[.,]\d+)*(?:\s*(?:M|B|K|million|crore|lakh))?|\b\d{1,3}(?:,\d{3})+\b|\b\d+\s*(?:million|billion|crore|lakh)\b",
    re.IGNORECASE
)

FACT_RE = re.compile(
    r"\b\d+(?:\.\d+)?%|\b\d{2,}\b|\b(?:is|are|was|were|has|have|can|will|must|should|provides|certifies)\b",
    re.IGNORECASE
)

AUTHORITY_RE = re.compile(
    r"\b(?:according to|research (?:shows?|indicates?)|studies? (?:show|confirm)|evidence suggests?|certified by|accredited by|established in)\b",
    re.IGNORECASE
)

TECH_RE = re.compile(r"\b[A-Z]{2,6}\b|\bISO\s*\d+\b|\bIS\s*\d+\b|\bRFC\s*\d+\b|`[^`]+`")

class GeoEngine:
    """Specialized engine for AI Answer Engine Optimization and citability analysis."""

    def __init__(self, headers: Optional[dict] = None):
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def audit_llms_txt(self, base_url: str) -> tuple[bool, List[str], bool]:
        """Validate llms.txt and llms-full.txt against standard specification."""
        llms_url = urljoin(base_url, "/llms.txt")
        full_url = urljoin(base_url, "/llms-full.txt")
        warnings = []
        found = False
        full_found = False

        try:
            r = requests.get(llms_url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                found = True
                content = r.text.lstrip("\ufeff")
                lines = content.splitlines()

                # Must have H1 title
                if not any(l.startswith("# ") for l in lines):
                    warnings.append("Missing H1 project title in llms.txt")

                # Must have > blockquote summary
                if not any(l.startswith("> ") for l in lines):
                    warnings.append("Missing '> blockquote' project summary per llms.txt standard")

                # Should have markdown links
                if not re.search(r"\[([^\]]+)\]\(([^)]+)\)", content):
                    warnings.append("No markdown links to key site documentation found in llms.txt")

                # Word count check
                if len(content.split()) < 30:
                    warnings.append("llms.txt is excessively sparse (<30 words)")

            elif r.status_code in (403, 406):
                warnings.append(f"HTTP {r.status_code}: CDN/WAF blocking bot access to /llms.txt")
            else:
                warnings.append("HTTP 404: /llms.txt is missing from website root")

            # Check /llms-full.txt
            r_full = requests.get(full_url, headers=self.headers, timeout=6)
            if r_full.status_code == 200 and len(r_full.text.strip()) > 50:
                full_found = True

        except Exception as e:
            warnings.append(f"Network error checking llms.txt: {e}")

        return found, warnings, full_found

    def analyze_citability(self, soup: BeautifulSoup, base_url: str) -> GeoAeoEvidence:
        """Run multi-method GEO/AEO content citability audit."""
        evidence = GeoAeoEvidence(engine_source="rankintel_geo_engine")
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.replace("www.", "")

        # 1. Authoritative Outbound Links
        auth_links = 0
        all_links = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                continue
            l_domain = urlparse(href).netloc.replace("www.", "")
            if l_domain == base_domain:
                continue
            all_links += 1
            tld = "." + l_domain.split(".")[-1] if "." in l_domain else ""
            if tld in AUTHORITATIVE_TLDS or any(d in l_domain for d in AUTHORITATIVE_DOMAINS):
                auth_links += 1

        evidence.outbound_citations_count = all_links
        evidence.authoritative_citations_count = auth_links

        cite_score = min(auth_links * 2 + (1 if all_links > 0 else 0), 6)
        evidence.methods.append(GeoCitabilityMethod(
            name="cite_sources",
            label="Cite Authoritative Sources",
            detected=auth_links >= 1,
            score=cite_score,
            max_score=6,
            impact="+27%",
            details={"authoritative": auth_links, "total_external": all_links}
        ))

        # 2. Quotation Addition
        blockquotes = len(soup.find_all("blockquote"))
        q_tags = len(soup.find_all("q"))
        quote_score = min(blockquotes * 3 + q_tags * 2, 6)
        evidence.methods.append(GeoCitabilityMethod(
            name="quotation_addition",
            label="Attributed Quotations",
            detected=(blockquotes + q_tags) >= 1,
            score=quote_score,
            max_score=6,
            impact="+41%",
            details={"blockquotes": blockquotes, "q_tags": q_tags}
        ))

        # 3. Statistical Density
        clean_text = soup.get_text(separator=' ')
        stats_matches = STAT_RE.findall(clean_text)
        word_count = max(len(clean_text.split()), 1)
        stat_density = round(len(stats_matches) / word_count * 1000, 2)
        evidence.statistical_density_per_1000 = stat_density

        stat_score = min(int(stat_density * 2), 6)
        evidence.methods.append(GeoCitabilityMethod(
            name="statistics_addition",
            label="Statistical & Quantitative Data",
            detected=len(stats_matches) >= 3,
            score=stat_score,
            max_score=6,
            impact="+33%",
            details={"stats_count": len(stats_matches), "density_per_1000": stat_density}
        ))

        # 4. Answer-First Structure (AutoGEO - H2 followed by concrete fact)
        h2_tags = soup.find_all("h2")
        answer_first_count = 0
        q_headings = []
        question_words = ('what', 'how', 'why', 'who', 'when', 'where', 'is', 'are', 'can', 'which', 'difference')

        for h2 in h2_tags:
            h2_text = h2.get_text().strip()
            if any(h2_text.lower().startswith(q) for q in question_words) or '?' in h2_text:
                q_headings.append(h2_text)

            next_el = h2.find_next(["p", "div", "li"])
            if next_el:
                f_text = next_el.get_text(strip=True)[:150]
                if FACT_RE.search(f_text):
                    answer_first_count += 1

        total_h2 = len(h2_tags)
        af_ratio = round(answer_first_count / total_h2, 2) if total_h2 > 0 else 0.0
        evidence.answer_first_ratio = af_ratio
        evidence.question_h2s = q_headings

        af_score = min(int(af_ratio * 7), 5)
        evidence.methods.append(GeoCitabilityMethod(
            name="answer_first",
            label="Answer-First H2 Structure",
            detected=af_ratio >= 0.3,
            score=af_score,
            max_score=5,
            impact="+25%",
            details={"h2_count": total_h2, "answer_first_h2s": answer_first_count, "ratio": af_ratio}
        ))

        # 5. Passage Density (Self-contained 50-150 word data-dense paragraphs)
        paras = soup.find_all("p")
        dense_paras = 0
        total_p = 0
        for p in paras:
            t = p.get_text(strip=True)
            w = len(t.split())
            if w >= 15:
                total_p += 1
                if 50 <= w <= 160 and re.search(r"\b\d+", t):
                    dense_paras += 1

        pd_ratio = round(dense_paras / total_p, 2) if total_p > 0 else 0.0
        evidence.passage_density_ratio = pd_ratio
        pd_score = min(int(pd_ratio * 8), 5)
        evidence.methods.append(GeoCitabilityMethod(
            name="passage_density",
            label="Passage Citability Density (50-150 words)",
            detected=dense_paras >= 2,
            score=pd_score,
            max_score=5,
            impact="+23%",
            details={"dense_paragraphs": dense_paras, "total_paragraphs": total_p, "ratio": pd_ratio}
        ))

        # 6. Technical & Standards Terms
        tech_matches = TECH_RE.findall(clean_text)
        code_blocks = len(soup.find_all(["code", "pre"]))
        tech_score = min(len(tech_matches) // 5 + code_blocks * 2, 5)
        evidence.methods.append(GeoCitabilityMethod(
            name="technical_terms",
            label="Technical & Standards Terminology",
            detected=len(tech_matches) >= 5,
            score=tech_score,
            max_score=5,
            impact="+18%",
            details={"tech_matches": len(tech_matches), "code_blocks": code_blocks}
        ))

        # 7. Authoritative Tone & Credentials
        auth_signals = len(AUTHORITY_RE.findall(clean_text))
        author_meta = soup.find("meta", attrs={"name": re.compile(r"author", re.I)})
        has_author = bool(author_meta or soup.find(class_=re.compile(r"author|byline", re.I)))
        tone_score = min(auth_signals + (2 if has_author else 0), 5)
        evidence.methods.append(GeoCitabilityMethod(
            name="authoritative_tone",
            label="Authoritative Tone & Credentials",
            detected=auth_signals >= 2 or has_author,
            score=tone_score,
            max_score=5,
            impact="+16%",
            details={"authority_signals": auth_signals, "has_author_byline": has_author}
        ))

        # Calculate Total Citability Score (Normalized to 0 - 100)
        current_sum = sum(m.score for m in evidence.methods)
        max_possible = sum(m.max_score for m in evidence.methods)
        evidence.overall_citability_score = int(round((current_sum / max_possible) * 100))

        return evidence

    def execute(self, url: str) -> EngineResult:
        """Run complete GEO engine pass."""
        t0 = time.time()
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code != 200:
                return EngineResult(
                    engine_name="rankintel_geo",
                    status="error",
                    error_message=f"HTTP status {r.status_code}",
                    execution_time_sec=round(time.time() - t0, 2)
                )

            soup = BeautifulSoup(r.text, 'html.parser')
            geo_data = self.analyze_citability(soup, base_url)
            llms_found, llms_warnings, full_found = self.audit_llms_txt(base_url)
            geo_data.llms_txt_found = llms_found
            geo_data.llms_txt_warnings = llms_warnings
            geo_data.llms_full_found = full_found

            return EngineResult(
                engine_name="rankintel_geo",
                status="success",
                execution_time_sec=round(time.time() - t0, 2),
                geo_aeo=geo_data
            )
        except Exception as e:
            return EngineResult(
                engine_name="rankintel_geo",
                status="error",
                error_message=str(e),
                execution_time_sec=round(time.time() - t0, 2)
            )
