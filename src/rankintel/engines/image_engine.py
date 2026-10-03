import re
from urllib.parse import urlparse
from typing import List, Optional
from bs4 import BeautifulSoup

from rankintel.models.schema import (
    ImageSEOEvidence, ImageDetail, ImageFormatEvidence, HtmlHeadEvidence
)

class ImageEngine:
    """
    Evaluates visual assets for search, layout stability (CLS), and modern responsive delivery
    without redundant network fetches. Also performs HTML Head technical validation.
    """
    
    # Generic alt terms to flag
    GENERIC_TERMS = {"image", "logo", "banner", "photo", "picture", "icon", "img", "thumbnail"}
    # Camera prefixes
    CAMERA_PREFIXES = re.compile(r"^(IMG|DSC|DCIM)_[0-9]+", re.IGNORECASE)
    # Filename-like alt (e.g., photo.jpg, image.png)
    FILENAME_PATTERN = re.compile(r".*\.(jpg|jpeg|png|webp|avif|gif|svg)$", re.IGNORECASE)

    @classmethod
    def evaluate(cls, raw_html: str, url: str) -> ImageSEOEvidence:
        """
        Parses raw HTML to evaluate image SEO and HTML head elements.
        """
        soup = BeautifulSoup(raw_html, "lxml")
        
        evidence = ImageSEOEvidence()
        evidence.images = cls._evaluate_images(soup, url, evidence)
        evidence.head_audit = cls._evaluate_head(soup, url)
        
        return evidence

    @classmethod
    def _evaluate_images(cls, soup: BeautifulSoup, page_url: str, evidence: ImageSEOEvidence) -> List[ImageDetail]:
        images_found = soup.find_all("img")
        evidence.total_images = len(images_found)
        
        details = []
        is_https_page = urlparse(page_url).scheme.lower() == "https"
        
        for idx, img in enumerate(images_found):
            src = img.get("src", "")
            if not src:
                # Try data-src or similar if lazy loaded, but for basic img tag src is required
                src = img.get("data-src", "")
                if not src:
                    continue # Ignore empty image tags
            
            detail = ImageDetail(src=src)
            
            # Alt Text Semantics
            alt = img.get("alt")
            if alt is None:
                detail.alt_status = "MISSING"
                evidence.missing_alt_count += 1
            else:
                alt_stripped = alt.strip()
                detail.alt = alt_stripped
                evidence.images_with_alt += 1
                
                if alt_stripped == "":
                    # Check if it's wrapped in an anchor
                    parent_a = img.find_parent("a")
                    # If inside an anchor tag with no other text, it's problematic
                    if parent_a and not parent_a.get_text(strip=True):
                        detail.alt_status = "MISSING" # Acts as empty link text
                        evidence.missing_alt_count += 1
                    else:
                        detail.alt_status = "EMPTY_DECORATIVE"
                        evidence.decorative_alt_count += 1
                else:
                    alt_lower = alt_stripped.lower()
                    if (alt_lower in cls.GENERIC_TERMS or 
                        cls.CAMERA_PREFIXES.match(alt_stripped) or 
                        cls.FILENAME_PATTERN.match(alt_stripped)):
                        detail.alt_status = "GENERIC_FILENAME"
                        evidence.generic_alt_count += 1
                    else:
                        detail.alt_status = "OPTIMAL"
            
            # Layout Shift Risk
            width = img.get("width")
            height = img.get("height")
            style = img.get("style", "").lower()
            has_inline_aspect_ratio = "aspect-ratio" in style
            
            if width and str(width).isdigit():
                detail.width = int(width)
            if height and str(height).isdigit():
                detail.height = int(height)
                
            detail.has_dimensions = bool(detail.width and detail.height)
            
            if not detail.has_dimensions and not has_inline_aspect_ratio:
                detail.potential_layout_shift_risk = True
                evidence.missing_dimensions_count += 1
                
            # LCP Risk Heuristic
            loading = img.get("loading", "")
            if isinstance(loading, list):
                loading = loading[0] if loading else ""
            loading = str(loading).lower()
            
            detail.is_lazy = (loading == "lazy")
            
            # Simple heuristic: top 2 images or inside header/nav
            is_early = idx < 2 or bool(img.find_parent(["header", "nav", "div[role='banner']"]) or (img.has_attr("role") and img["role"] == "banner"))
            
            if detail.is_lazy and is_early:
                detail.potential_lcp_risk = True
                evidence.early_lazy_lcp_risks_count += 1
                
            # Fetch priority
            fetchpriority = img.get("fetchpriority", "")
            if isinstance(fetchpriority, list):
                fetchpriority = fetchpriority[0] if fetchpriority else ""
            fetchpriority = str(fetchpriority).lower()
            
            detail.is_fetchpriority_high = (fetchpriority == "high")
            
            # Responsiveness
            srcset = img.get("srcset")
            sizes = img.get("sizes")
            is_in_picture = bool(img.find_parent("picture"))
            detail.is_responsive = bool(srcset or sizes or is_in_picture)
            
            if detail.is_lazy:
                evidence.lazy_loaded_count += 1
                
            # Format Classification
            detail.format_evidence = cls._classify_format(img, src)
            if detail.format_evidence.is_modern_format:
                evidence.modern_format_count += 1
            elif detail.format_evidence.declared_format in ["jpg", "jpeg", "png", "gif"]:
                evidence.legacy_format_count += 1
                
            details.append(detail)
            
        return details

    @classmethod
    def _classify_format(cls, img, src: str) -> ImageFormatEvidence:
        format_evidence = ImageFormatEvidence(observed_mime_type="UNKNOWN")
        
        # Check source tags if in picture
        picture = img.find_parent("picture")
        if picture:
            source = picture.find("source")
            if source:
                source_type = source.get("type", "")
                if source_type:
                    source_type_lower = source_type.lower()
                    if "webp" in source_type_lower:
                        format_evidence.declared_format = "webp"
                    elif "avif" in source_type_lower:
                        format_evidence.declared_format = "avif"
                    elif "svg" in source_type_lower:
                        format_evidence.declared_format = "svg"
                    elif "jpeg" in source_type_lower or "jpg" in source_type_lower:
                        format_evidence.declared_format = "jpeg"
                    elif "png" in source_type_lower:
                        format_evidence.declared_format = "png"
        
        if format_evidence.declared_format == "UNKNOWN":
            # Fallback to extension
            ext_match = re.search(r'\.(webp|avif|svg|jpg|jpeg|png|gif)(?:[?#]|$)', src, re.IGNORECASE)
            if ext_match:
                format_evidence.declared_format = ext_match.group(1).lower()
                
        format_evidence.is_modern_format = format_evidence.declared_format in ["webp", "avif", "svg"]
        
        return format_evidence

    @classmethod
    def _evaluate_head(cls, soup: BeautifulSoup, page_url: str) -> HtmlHeadEvidence:
        head_audit = HtmlHeadEvidence()
        is_https_page = urlparse(page_url).scheme.lower() == "https"
        
        # Viewport
        viewport_meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        if viewport_meta:
            head_audit.viewport_present = True
            content = viewport_meta.get("content")
            if isinstance(content, list):
                content = content[0] if content else ""
            head_audit.viewport_configuration = content
            
        # Lang
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            head_audit.lang_present = True
            lang = html_tag.get("lang")
            if isinstance(lang, list):
                lang = lang[0] if lang else ""
            head_audit.lang_code = lang
            
        # Charset
        charset_meta = soup.find("meta", charset=True)
        if not charset_meta:
            charset_meta = soup.find("meta", attrs={"http-equiv": re.compile(r"^Content-Type$", re.I)})
        if charset_meta:
            head_audit.charset_present = True
            charset = charset_meta.get("charset") or charset_meta.get("content")
            if isinstance(charset, list):
                charset = charset[0] if charset else ""
            head_audit.charset_declared = charset
            
        # Heading hierarchy
        headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
        h1s = [h for h in headings if h.name.lower() == "h1"]
        
        if len(h1s) != 1:
            head_audit.heading_hierarchy_valid = False
            head_audit.heading_skips.append(f"Found {len(h1s)} H1 tags, expected exactly 1.")
            
        current_level = 0
        for h in headings:
            level = int(h.name[1])
            if current_level != 0 and level > current_level + 1:
                head_audit.heading_skips.append(f"Skipped from H{current_level} to H{level}.")
                head_audit.heading_hierarchy_valid = False
            current_level = level
            
        # Insecure asset URL extraction
        if is_https_page:
            # Check for http:// resources
            for tag, attr in [("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src"), ("source", "src"), ("source", "srcset")]:
                for el in soup.find_all(tag):
                    val = el.get(attr, "")
                    if isinstance(val, str) and val.startswith("http://"):
                        head_audit.insecure_resource_urls.append(val)
                    elif isinstance(val, list):
                        for v in val:
                            if isinstance(v, str) and v.startswith("http://"):
                                head_audit.insecure_resource_urls.append(v)
            
            # Deduplicate
            head_audit.insecure_resource_urls = list(dict.fromkeys(head_audit.insecure_resource_urls))

        return head_audit
