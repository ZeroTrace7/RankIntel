"""
Fix Generator — Generates production-ready, copy-paste assets for SEO and GEO.
"""
from __future__ import annotations
import json
from urllib.parse import urlparse
from typing import Dict, List, Optional
from rankintel.models.schema import OnPageEvidence, RobotsEvidence, SchemaEvidence, GeoAeoEvidence

class FixGenerator:
    """Manufactures syntactically valid, production-ready code fixes."""

    @staticmethod
    def generate_meta_fixes(on_page: OnPageEvidence, domain: str) -> Dict[str, str]:
        """Generate optimized Title and Description tags with rationale."""
        current_title = on_page.title
        current_desc = on_page.meta_description
        h1 = on_page.h1_text[0] if on_page.h1_text else domain

        # Construct optimized title (target 50-60 characters)
        brand = domain.replace("www.", "").split(".")[0].capitalize()
        if len(h1) > 35:
            opt_title = f"{h1[:35]}... | {brand}"
        elif h1 and brand not in h1:
            opt_title = f"{h1} | {brand}"
        elif current_title:
            opt_title = current_title[:58]
        else:
            opt_title = f"Industry Solutions & Consulting | {brand}"

        if len(opt_title) > 60:
            opt_title = opt_title[:57] + "..."

        # Construct optimized description (target 140-160 characters with CTA)
        if current_desc and len(current_desc) >= 120 and len(current_desc) <= 165:
            opt_desc = current_desc
        elif current_desc and len(current_desc) > 165:
            base_cut = current_desc[:135].rsplit(' ', 1)[0]
            opt_desc = f"{base_cut}. Get a quote today."
        else:
            opt_desc = f"Discover comprehensive services with {brand}. Leading technical expertise, certified quality, and dedicated support. Contact our specialists today."

        if len(opt_desc) > 160:
            opt_desc = opt_desc[:157].rsplit(' ', 1)[0] + "..."

        return {
            "current_title": current_title,
            "optimized_title": opt_title,
            "title_length": str(len(opt_title)),
            "current_description": current_desc,
            "optimized_description": opt_desc,
            "desc_length": str(len(opt_desc)),
        }

    @staticmethod
    def generate_jsonld_schema(
        url: str, domain: str, on_page: OnPageEvidence,
        schema: Optional[SchemaEvidence] = None
    ) -> Optional[str]:
        """
        Generate complete, valid JSON-LD @graph schema block.
        Returns None if Organization schema is already present (no fix needed).
        """
        if schema and schema.has_organization:
            return None  # Already has Organization schema — skip generation

        brand = domain.replace("www.", "").split(".")[0].capitalize()
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        graph = [
            {
                "@type": "Organization",
                "@id": f"{base_url}/#organization",
                "name": brand,
                "url": base_url,
                "description": on_page.meta_description or f"Official site of {brand}",
            },
            {
                "@type": "WebSite",
                "@id": f"{base_url}/#website",
                "url": base_url,
                "name": brand,
                "publisher": {
                    "@id": f"{base_url}/#organization"
                }
            },
            {
                "@type": "WebPage",
                "@id": f"{url}#webpage",
                "url": url,
                "name": on_page.title or brand,
                "isPartOf": {
                    "@id": f"{base_url}/#website"
                },
                "about": {
                    "@id": f"{base_url}/#organization"
                },
                "description": on_page.meta_description or f"Services and information by {brand}"
            }
        ]

        schema_dict = {
            "@context": "https://schema.org",
            "@graph": graph
        }

        json_str = json.dumps(schema_dict, indent=2, ensure_ascii=False)
        return f'<script type="application/ld+json">\n{json_str}\n</script>'

    @staticmethod
    def generate_llms_txt(domain: str, url: str, on_page: OnPageEvidence, geo: GeoAeoEvidence) -> Optional[str]:
        """
        Generate standard-compliant /llms.txt manifest per llmstxt.org specification.
        Returns None if llms.txt is already present (no fix needed).
        """
        if geo.llms_txt_found:
            return None  # Already present — skip generation

        brand = domain.replace("www.", "").split(".")[0].capitalize()
        summary = on_page.meta_description or f"{brand} delivers premier industry solutions, compliance, and enterprise services."

        lines = [
            f"# {brand}",
            "",
            f"> {summary}",
            "",
            "## Core Services & Knowledge Base",
            f"- [{on_page.title or 'Homepage'}]({url}): Primary portal and overview.",
        ]

        if geo.question_h2s:
            lines.append("")
            lines.append("## Key Inquiries & Subject Matter")
            for q in geo.question_h2s[:5]:
                lines.append(f"- {q}")

        lines.extend([
            "",
            "## Optional & Detailed Documentation",
            f"- [/llms-full.txt]({urlparse(url).scheme}://{urlparse(url).netloc}/llms-full.txt): Comprehensive documentation for deeper context.",
        ])

        return "\n".join(lines)


    @staticmethod
    def generate_hardened_robots_txt() -> str:
        """Generate AI-optimized robots.txt rules enabling search citations while controlling training."""
        return (
            "# RankIntel Hardened AI Robots.txt Policy\n"
            "# 1. Allow AI Search & Citation Bots (Essential for ChatGPT Search, Google, Perplexity, Claude)\n"
            "User-agent: OAI-SearchBot\n"
            "Allow: /\n\n"
            "User-agent: PerplexityBot\n"
            "Allow: /\n\n"
            "User-agent: Claude-SearchBot\n"
            "Allow: /\n\n"
            "User-agent: Googlebot\n"
            "Allow: /\n\n"
            "User-agent: Applebot\n"
            "Allow: /\n\n"
            "# 2. Optional: Disallow AI Model Pre-Training Scrapers (If preserving intellectual property)\n"
            "# User-agent: GPTBot\n"
            "# Disallow: /\n"
            "# User-agent: ClaudeBot\n"
            "# Disallow: /\n"
            "# User-agent: Google-Extended\n"
            "# Disallow: /\n\n"
            "# 3. Standard Crawler Settings\n"
            "User-agent: *\n"
            "Allow: /\n"
        )
