"""
Image SEO & Visual Search Engine (Phase 7.3).

Audits visual assets for:
- Alt text intelligence (missing alt, decorative alt="", generic low-quality alt)
- Layout stability & CLS prevention (explicit width/height attributes, aspect-ratio)
- Modern image compression formats (WebP, AVIF vs uncompressed PNG/JPEG/GIF)
- Responsive markup (<picture>, srcset, sizes)
- Performance & LCP hero prioritization (loading="lazy" vs fetchpriority="high")
- Filename semantics (descriptive slugs vs raw camera files)
"""
from __future__ import annotations
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from rankintel.models.schema import (
    ImageFindingSeverity,
    ImageFinding,
    ImageDetail,
    ImageSeoEvidence,
)

GENERIC_ALT_PATTERNS = {
    "image", "img", "photo", "picture", "logo", "banner", "icon", "placeholder",
    "thumbnail", "graphic", "screenshot", "untitled", "avatar", "temp", "header"
}

GENERIC_FILENAME_RE = re.compile(
    r"^(img|dsc|photo|image|screenshot|untitled|pic|asset|capture|frame)[-_]?\d*$",
    re.IGNORECASE
)


class ImageEngine:
    """Specialized engine for on-page image SEO, visual search, and Core Web Vitals layout stability."""

    def __init__(self, timeout_sec: float = 10.0):
        self.timeout_sec = timeout_sec

    def evaluate_image(
        self,
        img_tag: Any,
        index: int,
        base_url: str = ""
    ) -> ImageDetail:
        """Evaluates single <img> tag from HTML DOM."""
        raw_src = img_tag.get("src", "").strip()
        full_src = urljoin(base_url, raw_src) if base_url and raw_src else raw_src

        # Filename & Format
        parsed_src = urlparse(full_src)
        basename = os.path.basename(parsed_src.path)
        ext = os.path.splitext(basename)[1].lower().lstrip(".")
        img_format = ext if ext else "unknown"

        # Modern format check
        modern_formats = {"webp", "avif", "svg"}
        is_modern = img_format in modern_formats

        # Filename semantics
        name_without_ext = os.path.splitext(basename)[0]
        is_descriptive = bool(name_without_ext and not GENERIC_FILENAME_RE.match(name_without_ext) and len(name_without_ext) > 3)

        # Alt text analysis
        alt_attr = img_tag.get("alt")
        has_alt = False
        is_decorative = False
        alt_quality = "good"

        if alt_attr is None:
            has_alt = False
            alt_quality = "missing"
        elif alt_attr.strip() == "":
            has_alt = True
            is_decorative = True
            alt_quality = "decorative"
        else:
            has_alt = True
            alt_clean = alt_attr.strip().lower()
            # Check if alt is merely filename or generic word
            if alt_clean in GENERIC_ALT_PATTERNS or alt_clean == basename.lower() or alt_clean.endswith(f".{ext}"):
                alt_quality = "generic"
            else:
                alt_quality = "good"

        # Dimensions & CLS prevention
        width_attr = img_tag.get("width")
        height_attr = img_tag.get("height")
        width_val: Optional[int] = None
        height_val: Optional[int] = None

        try:
            if width_attr and str(width_attr).replace("px", "").isdigit():
                width_val = int(str(width_attr).replace("px", ""))
        except Exception:
            pass

        try:
            if height_attr and str(height_attr).replace("px", "").isdigit():
                height_val = int(str(height_attr).replace("px", ""))
        except Exception:
            pass

        style = img_tag.get("style", "").lower()
        has_aspect_ratio = "aspect-ratio" in style or (width_val is not None and height_val is not None)

        # Loading & Prioritization
        loading_attr = img_tag.get("loading", "").lower() or None
        fetchpriority_attr = img_tag.get("fetchpriority", "").lower() or None

        # Responsive attributes
        has_srcset = bool(img_tag.get("srcset"))
        parent = img_tag.parent
        is_in_picture = bool(parent and parent.name == "picture")

        issues: List[str] = []
        if alt_quality == "missing":
            issues.append("Missing alt attribute")
        elif alt_quality == "generic":
            issues.append(f"Generic/low-quality alt text: '{alt_attr}'")

        if not has_aspect_ratio:
            issues.append("Missing explicit width and height attributes (CLS risk)")

        if not is_modern and img_format in ("png", "jpg", "jpeg", "bmp"):
            issues.append(f"Legacy image format '{img_format}' (recommend WebP or AVIF)")

        if index == 0 and loading_attr == "lazy":
            issues.append("LCP hero image configured with loading='lazy' (delays paint)")

        return ImageDetail(
            src=full_src,
            alt=alt_attr,
            has_alt=has_alt,
            is_decorative=is_decorative,
            alt_quality=alt_quality,
            width=width_val,
            height=height_val,
            has_dimensions=has_aspect_ratio,
            format=img_format,
            is_modern_format=is_modern,
            loading=loading_attr,
            fetchpriority=fetchpriority_attr,
            has_srcset=has_srcset,
            is_in_picture_tag=is_in_picture,
            filename=basename,
            is_descriptive_filename=is_descriptive,
            issues=issues
        )

    def audit_html(self, html: str, base_url: str = "") -> ImageSeoEvidence:
        """Audits all images in an HTML page string."""
        if not html:
            return ImageSeoEvidence(score=100, grade="A")

        soup = BeautifulSoup(html, "html.parser")
        img_tags = soup.find_all("img")

        images: List[ImageDetail] = []
        findings: List[ImageFinding] = []

        total = len(img_tags)
        with_alt_count = 0
        decorative_count = 0
        with_dims_count = 0
        modern_count = 0
        lazy_count = 0
        hero_candidate: Optional[str] = None

        for idx, tag in enumerate(img_tags):
            detail = self.evaluate_image(tag, index=idx, base_url=base_url)
            images.append(detail)

            if detail.has_alt:
                with_alt_count += 1
            if detail.is_decorative:
                decorative_count += 1
            if detail.has_dimensions:
                with_dims_count += 1
            if detail.is_modern_format:
                modern_count += 1
            if detail.loading == "lazy":
                lazy_count += 1

            if idx == 0 and detail.src:
                hero_candidate = detail.src

        # Aggregate findings
        missing_alts = [img for img in images if img.alt_quality == "missing"]
        if missing_alts:
            findings.append(
                ImageFinding(
                    code="IMG_MISSING_ALT",
                    severity=ImageFindingSeverity.HIGH,
                    src=missing_alts[0].src,
                    description=f"{len(missing_alts)} of {total} images lack an alt attribute entirely. Screen readers and search indexers cannot parse image content.",
                    recommendation="Add descriptive, keyword-aligned alt attributes to informative images, or alt='' to purely decorative icons."
                )
            )

        generic_alts = [img for img in images if img.alt_quality == "generic"]
        if generic_alts:
            findings.append(
                ImageFinding(
                    code="IMG_GENERIC_ALT",
                    severity=ImageFindingSeverity.MEDIUM,
                    src=generic_alts[0].src,
                    description=f"{len(generic_alts)} images use generic alt text (e.g. 'logo', 'image', or raw filenames) providing zero semantic search context.",
                    recommendation="Replace generic alt text with context-rich descriptions (e.g., 'Sunrise Quality Testing NABL Calibration Laboratory in Nagpur')."
                )
            )

        missing_dims = [img for img in images if not img.has_dimensions]
        if missing_dims:
            findings.append(
                ImageFinding(
                    code="IMG_MISSING_DIMENSIONS_CLS",
                    severity=ImageFindingSeverity.MEDIUM,
                    src=missing_dims[0].src,
                    description=f"{len(missing_dims)} of {total} images lack explicit width/height dimensions. Browsers cannot allocate layout space before download, triggering Cumulative Layout Shift (CLS).",
                    recommendation="Declare width and height attributes or CSS aspect-ratio on all <img> elements."
                )
            )

        legacy_images = [img for img in images if not img.is_modern_format and img.format in ("png", "jpg", "jpeg", "bmp")]
        if legacy_images and total > 0:
            pct_legacy = round(len(legacy_images) / total * 100)
            if pct_legacy > 50:
                findings.append(
                    ImageFinding(
                        code="IMG_LEGACY_FORMAT",
                        severity=ImageFindingSeverity.LOW,
                        src=legacy_images[0].src,
                        description=f"{len(legacy_images)} images ({pct_legacy}%) use legacy uncompressed image formats (JPEG/PNG).",
                        recommendation="Convert images to modern WebP or AVIF formats to reduce payload by 30-50%."
                    )
                )

        if images and images[0].loading == "lazy":
            findings.append(
                ImageFinding(
                    code="IMG_LAZY_HERO_CONFLICT",
                    severity=ImageFindingSeverity.HIGH,
                    src=images[0].src,
                    description="The first above-the-fold hero image is marked with loading='lazy'. Browsers defer loading, directly degrading Largest Contentful Paint (LCP).",
                    recommendation="Remove loading='lazy' from above-the-fold hero images and add fetchpriority='high'."
                )
            )

        # Calculate score and grade
        score = 100
        if total > 0:
            alt_ratio = (with_alt_count / total)
            dims_ratio = (with_dims_count / total)

            # Penalties
            if alt_ratio < 1.0:
                score -= int((1.0 - alt_ratio) * 35)
            if dims_ratio < 1.0:
                score -= int((1.0 - dims_ratio) * 25)
            if modern_count == 0 and total > 2:
                score -= 10
            if images and images[0].loading == "lazy":
                score -= 15

        score = max(0, min(100, score))

        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        recommendations = [f.recommendation for f in findings]

        return ImageSeoEvidence(
            total_images=total,
            images_with_alt=with_alt_count,
            decorative_images=decorative_count,
            images_with_dimensions=with_dims_count,
            modern_format_count=modern_count,
            lazy_loaded_count=lazy_count,
            hero_or_lcp_candidate=hero_candidate,
            score=score,
            grade=grade,
            images=images,
            findings=findings,
            recommendations=recommendations,
        )

    async def audit_url(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None
    ) -> ImageSeoEvidence:
        """Fetches page asynchronously and audits images."""
        try:
            if client is not None:
                resp = await client.get(url, follow_redirects=True, timeout=self.timeout_sec)
            else:
                async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True) as local_client:
                    resp = await local_client.get(url)

            if resp.status_code == 200:
                return self.audit_html(resp.text, base_url=url)
        except Exception:
            pass

        return ImageSeoEvidence()

    def audit_url_sync(self, url: str) -> ImageSeoEvidence:
        """Fetches page synchronously and audits images."""
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return self.audit_html(resp.text, base_url=url)
        except Exception:
            pass

        return ImageSeoEvidence()
