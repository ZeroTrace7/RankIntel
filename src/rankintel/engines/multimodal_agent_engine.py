"""
RankIntel Phase 10.4 — Multimodal + Agent Readiness Intelligence Engine.

Builds a deterministic, evidence-driven layer that evaluates:
1. Whether important website information is accessible through non-text visual content
   or if content is trapped inside visual-only assets without text/alt/caption representation.
2. Whether the site exposes observable signals relevant to machine/agent interaction
   (forms, controls, accessible buttons, descriptive navigation, structured actions).
3. Grounded information access paths linking multimodal assets and interaction surfaces
   to Phase 10.2 answerable information units and Phase 10.3 claims/entities.

Strict constraints:
- Zero external LLM or computer vision API calls.
- Zero image binary downloads or OCR processing.
- Zero duplicate HTTP requests (strictly reuses existing DOM, headers, and previous engine outputs).
- Health-score formulas remain 100% unchanged.
- Purely deterministic, evidence-driven, and neutral.
- Never claims a site is "AI optimized" merely because it has images, forms, or metadata.
"""
from __future__ import annotations
import re
import json
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Tag, NavigableString

from rankintel.models.schema import (
    MultimodalRepresentationStatus,
    AgentInteractionSignal,
    AgentInteractionStatus,
    MultimodalAssetItem,
    MultimodalInformationEvidence,
    AgentInteractionSurfaceItem,
    AgentReadinessEvidence,
    InformationAccessPathEvidence,
    MultimodalAgentIntelligence,
    SiteMultimodalAgentIntelligence,
    ImageSEOEvidence,
    ImageDetail,
    AnswerabilityEvidence,
    AnswerableInformationUnit,
    AnswerableUnitType,
    ClaimGroundingEvidence,
    ClaimEvidence,
    EntityEvidence,
    SchemaEvidence,
    OnPageEvidence,
    CrawlRecord,
    SiteCrawlResult,
)

GENERIC_ALT_TERMS: Set[str] = {
    "image", "img", "logo", "banner", "photo", "picture", "icon", "thumbnail",
    "placeholder", "graphic", "pic", "illustration", "figure", "header", "footer"
}

GENERIC_LINK_TERMS: Set[str] = {
    "click here", "click", "read more", "more", "learn more", "here", "link",
    "view more", "details", "see details", "continue", "go", "next"
}

DECORATIVE_HINTS: Set[str] = {
    "spacer", "bullet", "divider", "separator", "bg-", "background", "decor",
    "decoration", "shadow", "line", "blank", "arrow", "dot", "pixel"
}

SEARCH_INPUT_NAMES: Set[str] = {
    "q", "s", "query", "search", "keyword", "keywords", "search_query", "searchterm"
}

CONTACT_INPUT_NAMES: Set[str] = {
    "email", "phone", "tel", "telephone", "mobile", "message", "msg", "comment",
    "inquiry", "enquiry", "quote", "name", "fullname", "firstname", "lastname",
    "subject", "contact"
}

AUTH_INPUT_NAMES: Set[str] = {
    "password", "pass", "pwd", "user", "username", "login", "signin", "auth"
}


def bound_text(text: Optional[str], max_len: int = 300) -> str:
    """Clean and safely truncate text snippets."""
    if not text:
        return ""
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


class MultimodalAgentEngine:
    """
    Evaluates multimodal information representation, agent interaction surfaces,
    and information access paths across individual pages and aggregated site crawls.
    """

    @classmethod
    def evaluate_page(
        cls,
        url: str,
        raw_html: Optional[str] = None,
        rendered_html: Optional[str] = None,
        image_seo_ev: Optional[ImageSEOEvidence] = None,
        answerability_ev: Optional[AnswerabilityEvidence] = None,
        claim_grounding_ev: Optional[ClaimGroundingEvidence] = None,
        entity_ev: Optional[EntityEvidence] = None,
        schema_ev: Optional[SchemaEvidence] = None,
        on_page: Optional[OnPageEvidence] = None,
    ) -> MultimodalAgentIntelligence:
        """
        Evaluate multimodal and agent readiness signals for a single page.
        Strictly reuses existing HTML and previously extracted engine evidence.
        """
        active_html = rendered_html or raw_html
        if not active_html:
            return MultimodalAgentIntelligence(
                url=url,
                engine_source="multimodal_agent_engine",
                multimodal=MultimodalInformationEvidence(
                    url=url,
                    limitations_recorded=["No HTML content available for multimodal inspection."],
                    facts=["Multimodal inspection unavailable: HTML missing."],
                ),
                agent_readiness=AgentReadinessEvidence(
                    url=url,
                    facts=["Agent readiness inspection unavailable: HTML missing."],
                ),
                facts=["Evaluation skipped: No HTML available."],
            )

        soup = BeautifulSoup(active_html, "lxml")

        # Part A: Multimodal Information Readiness
        multimodal_ev = cls._analyze_multimodal_assets(
            soup=soup,
            url=url,
            image_seo_ev=image_seo_ev,
            answerability_ev=answerability_ev,
        )

        # Part B: Agent Readiness Signals
        agent_ev = cls._analyze_agent_readiness(
            soup=soup,
            url=url,
            schema_ev=schema_ev,
        )

        # Part C: Information Access Path Analysis
        access_paths = cls._analyze_access_paths(
            url=url,
            multimodal_ev=multimodal_ev,
            agent_ev=agent_ev,
            answerability_ev=answerability_ev,
            claim_grounding_ev=claim_grounding_ev,
            entity_ev=entity_ev,
        )

        # Count gaps
        visual_gaps = sum(1 for p in access_paths if p.evidence_gap_identified and "VISUAL" in p.path_type)
        action_gaps = sum(1 for p in access_paths if p.evidence_gap_identified and "ACTION" in p.path_type)

        facts: List[str] = []
        facts.append(
            f"Observed {multimodal_ev.total_visual_assets} visual asset(s): "
            f"{multimodal_ev.informational_assets_count} informational, "
            f"{multimodal_ev.alt_represented_count} with meaningful alt text, "
            f"{multimodal_ev.caption_represented_count} with figure captions, "
            f"{multimodal_ev.visual_only_observed_count} visual-only information gap(s)."
        )
        facts.append(
            f"Observed {agent_ev.total_forms_detected} form(s) ({agent_ev.labeled_forms_count} labeled), "
            f"{agent_ev.action_buttons_detected} action button(s) ({agent_ev.meaningful_accessible_buttons_count} accessible names), "
            f"{agent_ev.schema_actions_detected} structured schema action(s), "
            f"{agent_ev.webmcp_declarations_detected} WebMCP declaration(s)."
        )
        if access_paths:
            facts.append(f"Mapped {len(access_paths)} information access path(s) across multimodal and agent surfaces.")

        analyses: List[str] = []
        if multimodal_ev.visual_only_observed_count > 0:
            analyses.append(
                f"Identified {multimodal_ev.visual_only_observed_count} informational visual asset(s) with no observable text, "
                f"alt, or caption representation. Non-visual consumers and text-based retrieval pipelines cannot extract "
                f"information contained within these graphics from HTML evidence alone."
            )
        if agent_ev.total_forms_detected > 0:
            labeled_ratio = agent_ev.labeled_forms_count / agent_ev.total_forms_detected
            if labeled_ratio < 1.0:
                analyses.append(
                    f"Only {agent_ev.labeled_forms_count} of {agent_ev.total_forms_detected} detected forms have explicit "
                    f"control labeling, creating potential ambiguity for programmatic or accessibility-driven interactions."
                )

        return MultimodalAgentIntelligence(
            url=url,
            engine_source="multimodal_agent_engine",
            multimodal=multimodal_ev,
            agent_readiness=agent_ev,
            access_paths=access_paths,
            visual_only_gaps_count=visual_gaps,
            action_surface_gaps_count=action_gaps,
            facts=facts,
            analyses=analyses,
        )

    # =========================================================================
    # Part A: Multimodal Information Readiness
    # =========================================================================

    @classmethod
    def _analyze_multimodal_assets(
        cls,
        soup: BeautifulSoup,
        url: str,
        image_seo_ev: Optional[ImageSEOEvidence],
        answerability_ev: Optional[AnswerabilityEvidence],
    ) -> MultimodalInformationEvidence:
        """Inspect observable visual elements for informational content and representation status."""
        evidence = MultimodalInformationEvidence(
            url=url,
            engine_source="multimodal_agent_engine",
            limitations_recorded=[
                "No image downloads or computer vision/OCR performed. Visual contents embedded inside pixel data are not extracted."
            ],
        )

        assets: List[MultimodalAssetItem] = []

        # 1. <img> and <picture> elements
        img_tags = soup.find_all("img")
        for idx, img in enumerate(img_tags):
            src = img.get("src") or img.get("data-src") or f"img-{idx}"
            alt_raw = img.get("alt")
            alt_text = alt_raw.strip() if alt_raw is not None else None

            # Check enclosing <figure> and <figcaption>
            figure_parent = img.find_parent("figure")
            caption_text: Optional[str] = None
            if figure_parent:
                figcaption = figure_parent.find("figcaption")
                if figcaption:
                    caption_text = figcaption.get_text(strip=True) or None

            # Check <picture> or responsive attributes
            is_in_picture = bool(img.find_parent("picture"))
            has_srcset = bool(img.get("srcset") or img.get("sizes"))
            is_responsive = is_in_picture or has_srcset

            # Check enclosing anchor
            parent_a = img.find_parent("a")
            is_linked_action = bool(parent_a)
            link_href = parent_a.get("href") if parent_a else None
            link_has_text = bool(parent_a and parent_a.get_text(strip=True))

            # Check proximity to heading
            heading = cls._find_closest_heading(img)

            # Classify decorative vs informational
            is_informational = cls._is_informational_image(
                img=img,
                alt_text=alt_text,
                caption_text=caption_text,
                parent_a=parent_a,
                is_in_figure=bool(figure_parent),
            )

            # Determine representation status
            status, reason = cls._determine_representation_status(
                is_informational=is_informational,
                alt_text=alt_text,
                caption_text=caption_text,
                heading=heading,
                parent_a=parent_a,
            )

            has_meaningful_alt = bool(
                alt_text
                and len(alt_text.split()) >= 2
                and alt_text.lower() not in GENERIC_ALT_TERMS
                and not re.match(r"^(img|dsc|photo|pic|image)[\-_0-9]+", alt_text, re.IGNORECASE)
                and not re.search(r"\.(jpg|jpeg|png|webp|avif|gif|svg)$", alt_text, re.IGNORECASE)
            )

            # Check linkage to M10.2 AnswerableInformationUnit
            related_unit_id = None
            if answerability_ev and heading:
                for unit in answerability_ev.units:
                    if unit.section_heading and heading.lower() in unit.section_heading.lower():
                        related_unit_id = unit.unit_id
                        break

            asset_item = MultimodalAssetItem(
                asset_id=f"img_{idx+1}",
                asset_type="image",
                src_or_id=src,
                representation_status=status,
                is_informational=is_informational,
                alt_text=alt_text,
                caption_text=caption_text,
                is_responsive_or_picture=is_responsive,
                is_linked_action=is_linked_action,
                link_href=link_href,
                link_has_text=link_has_text,
                associated_heading=heading,
                related_unit_id=related_unit_id,
                visual_only_reason=reason if status == MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED else None,
                bounded_snippet=bound_text(str(img)[:200]),
                source_location=f"img[{idx+1}]",
                source_type="raw_html",
                extraction_method="dom_multimodal_inspection",
                provenance="multimodal_agent_engine",
            )
            assets.append(asset_item)

            if is_responsive:
                evidence.responsive_picture_count += 1
            if is_linked_action:
                evidence.image_link_actions_count += 1

        # 2. Standalone <svg> elements
        svg_tags = soup.find_all("svg")
        for s_idx, svg in enumerate(svg_tags):
            # Check if SVG has title, desc, or aria-label
            title_tag = svg.find("title")
            desc_tag = svg.find("desc")
            aria_label = svg.get("aria-label") or svg.get("aria-labelledby")
            title_text = title_tag.get_text(strip=True) if title_tag else None
            desc_text = desc_tag.get_text(strip=True) if desc_tag else None
            label_text = title_text or desc_text or aria_label

            parent_a = svg.find_parent("a")
            is_linked = bool(parent_a)
            link_href = parent_a.get("href") if parent_a else None
            link_has_text = bool(parent_a and parent_a.get_text(strip=True))

            heading = cls._find_closest_heading(svg)

            is_decor = bool(
                svg.get("aria-hidden") == "true"
                or svg.get("role") in ("presentation", "none")
                or (not label_text and not is_linked)
            )
            is_informational = not is_decor

            if label_text:
                status = MultimodalRepresentationStatus.ALT_REPRESENTED
                reason = None
            elif heading and is_informational:
                status = MultimodalRepresentationStatus.TEXT_REPRESENTED
                reason = None
            elif is_informational:
                status = MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED
                reason = "Informational SVG graphic lacks accessible title, desc, or aria-label"
            else:
                status = MultimodalRepresentationStatus.TEXT_REPRESENTED
                reason = None

            asset_item = MultimodalAssetItem(
                asset_id=f"svg_{s_idx+1}",
                asset_type="svg",
                src_or_id=f"inline-svg-{s_idx+1}",
                representation_status=status,
                is_informational=is_informational,
                alt_text=label_text,
                caption_text=desc_text,
                is_responsive_or_picture=False,
                is_linked_action=is_linked,
                link_href=link_href,
                link_has_text=link_has_text,
                associated_heading=heading,
                visual_only_reason=reason if status == MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED else None,
                bounded_snippet=bound_text(str(svg)[:180]),
                source_location=f"svg[{s_idx+1}]",
                source_type="raw_html",
                extraction_method="dom_multimodal_inspection",
                provenance="multimodal_agent_engine",
            )
            assets.append(asset_item)
            evidence.svg_assets_count += 1
            if is_linked:
                evidence.image_link_actions_count += 1

        # 3. <canvas> elements
        canvas_tags = soup.find_all("canvas")
        for c_idx, canvas in enumerate(canvas_tags):
            fallback_text = canvas.get_text(strip=True) or None
            aria_label = canvas.get("aria-label")
            label_text = fallback_text or aria_label
            heading = cls._find_closest_heading(canvas)

            if label_text:
                status = MultimodalRepresentationStatus.TEXT_REPRESENTED
                reason = None
            else:
                status = MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED
                reason = "Interactive canvas region lacks textual fallback description or aria-label"

            asset_item = MultimodalAssetItem(
                asset_id=f"canvas_{c_idx+1}",
                asset_type="canvas",
                src_or_id=f"canvas-{c_idx+1}",
                representation_status=status,
                is_informational=True,
                alt_text=label_text,
                caption_text=None,
                associated_heading=heading,
                visual_only_reason=reason if status == MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED else None,
                bounded_snippet=bound_text(str(canvas)[:180]),
                source_location=f"canvas[{c_idx+1}]",
                source_type="raw_html",
                extraction_method="dom_multimodal_inspection",
                provenance="multimodal_agent_engine",
            )
            assets.append(asset_item)
            evidence.canvas_assets_count += 1

        # Calculate counts
        evidence.total_visual_assets = len(assets)
        evidence.assets = assets
        evidence.informational_assets_count = sum(1 for a in assets if a.is_informational)
        evidence.decorative_assets_count = sum(1 for a in assets if not a.is_informational)
        evidence.text_represented_count = sum(
            1 for a in assets if a.representation_status == MultimodalRepresentationStatus.TEXT_REPRESENTED
        )
        evidence.alt_represented_count = sum(
            1 for a in assets if a.representation_status == MultimodalRepresentationStatus.ALT_REPRESENTED
        )
        evidence.caption_represented_count = sum(
            1 for a in assets if a.representation_status == MultimodalRepresentationStatus.CAPTION_REPRESENTED
        )
        evidence.structured_context_count = sum(
            1 for a in assets if a.representation_status == MultimodalRepresentationStatus.STRUCTURED_CONTEXT_AVAILABLE
        )
        evidence.visual_only_observed_count = sum(
            1 for a in assets if a.representation_status == MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED
        )

        return evidence

    @classmethod
    def _is_informational_image(
        cls,
        img: Tag,
        alt_text: Optional[str],
        caption_text: Optional[str],
        parent_a: Optional[Tag],
        is_in_figure: bool,
    ) -> bool:
        """Distinguish informational images from purely decorative assets."""
        # Explicit decorative indicators
        if img.get("role") in ("presentation", "none"):
            return False
        if img.get("aria-hidden") == "true":
            return False

        # Alt is explicit empty string
        if alt_text == "":
            # If wrapped in link without other text, it's a functional link (informational/action)
            if parent_a and not parent_a.get_text(strip=True):
                return True
            return False

        # Figure parent strongly indicates informational intent
        if is_in_figure or caption_text:
            return True

        # Check dimensions if present
        w = img.get("width")
        h = img.get("height")
        if w and h and str(w).isdigit() and str(h).isdigit():
            width_val = int(w)
            height_val = int(h)
            if width_val <= 16 and height_val <= 16:
                return False

        # Filename hints
        src = (img.get("src") or "").lower()
        if any(hint in src for hint in DECORATIVE_HINTS):
            return False

        # If inside main, article, or section with substantive alt
        if alt_text and len(alt_text.split()) >= 2:
            return True

        # Default: consider it informational if inside content container
        parent_containers = [p.name for p in img.parents if p.name]
        if any(c in parent_containers for c in ("main", "article", "section", "figure")):
            return True

        return True

    @classmethod
    def _determine_representation_status(
        cls,
        is_informational: bool,
        alt_text: Optional[str],
        caption_text: Optional[str],
        heading: Optional[str],
        parent_a: Optional[Tag],
    ) -> Tuple[MultimodalRepresentationStatus, Optional[str]]:
        """Determine representation status for a visual asset."""
        if not is_informational:
            return MultimodalRepresentationStatus.TEXT_REPRESENTED, None

        # 1. Caption represented
        if caption_text and len(caption_text.strip().split()) >= 2:
            return MultimodalRepresentationStatus.CAPTION_REPRESENTED, None

        # 2. Alt represented (meaningful alt)
        if alt_text and alt_text.strip():
            clean_alt = alt_text.strip()
            words = clean_alt.split()
            is_generic = clean_alt.lower() in GENERIC_ALT_TERMS
            is_filename = bool(re.search(r"\.(jpg|jpeg|png|webp|avif|gif|svg)$", clean_alt, re.IGNORECASE))
            if len(words) >= 2 and not is_generic and not is_filename:
                return MultimodalRepresentationStatus.ALT_REPRESENTED, None

        # 3. Text represented via heading or parent link text
        if parent_a and parent_a.get_text(strip=True):
            return MultimodalRepresentationStatus.TEXT_REPRESENTED, None
        if heading and len(heading.split()) >= 2:
            return MultimodalRepresentationStatus.TEXT_REPRESENTED, None

        # 4. Informational with missing or generic alt and no caption/text
        reason = "Informational visual asset lacks meaningful alt text, caption, or proximate textual context"
        return MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED, reason

    @classmethod
    def _find_closest_heading(cls, element: Tag) -> Optional[str]:
        """Find the nearest preceding heading in the document order."""
        for sibling in element.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = sibling.get_text(strip=True)
            if text:
                return bound_text(text, 120)
        return None

    # =========================================================================
    # Part B: Agent Readiness Signals
    # =========================================================================

    @classmethod
    def _analyze_agent_readiness(
        cls,
        soup: BeautifulSoup,
        url: str,
        schema_ev: Optional[SchemaEvidence],
    ) -> AgentReadinessEvidence:
        """Inspect observable machine/agent interaction surfaces, forms, controls, and buttons."""
        evidence = AgentReadinessEvidence(
            url=url,
            engine_source="multimodal_agent_engine",
        )

        surfaces: List[AgentInteractionSurfaceItem] = []

        # 1. Forms Analysis
        forms = soup.find_all("form")
        evidence.total_forms_detected = len(forms)

        for f_idx, form in enumerate(forms):
            form_action = form.get("action") or ""
            form_method = (form.get("method") or "GET").upper()

            controls = form.find_all(["input", "textarea", "select"])
            input_types: List[str] = []
            labeled_controls = 0

            for ctrl in controls:
                if ctrl.name == "input":
                    typ = ctrl.get("type", "text").lower()
                    if typ != "hidden":
                        input_types.append(typ)
                else:
                    input_types.append(ctrl.name)

                # Check labeling
                ctrl_labeled = cls._is_control_labeled(soup, ctrl)
                if ctrl_labeled:
                    labeled_controls += 1

            # Classify Form Signal
            signal_type, surface_name = cls._classify_form_purpose(form, input_types, form_action)

            # Determine form labeling status
            visible_controls_count = len(input_types)
            if visible_controls_count == 0:
                form_status = AgentInteractionStatus.OBSERVED
            elif labeled_controls == visible_controls_count:
                form_status = AgentInteractionStatus.LABELED
                evidence.labeled_forms_count += 1
            elif labeled_controls > 0:
                form_status = AgentInteractionStatus.PARTIALLY_LABELED
            else:
                form_status = AgentInteractionStatus.UNLABELED

            if signal_type == AgentInteractionSignal.SEARCH_FORM:
                evidence.search_forms_count += 1
            elif signal_type == AgentInteractionSignal.CONTACT_INQUIRY_FORM:
                evidence.contact_inquiry_forms_count += 1
            elif signal_type == AgentInteractionSignal.LOGIN_ACCOUNT_SURFACE:
                evidence.login_account_forms_count += 1

            aria_role = form.get("role")
            aria_label = form.get("aria-label") or form.get("aria-labelledby")
            if aria_role or aria_label:
                evidence.aria_interaction_surfaces_count += 1

            surface_item = AgentInteractionSurfaceItem(
                surface_id=f"form_{f_idx+1}",
                signal_type=signal_type,
                surface_name=surface_name,
                form_action=form_action or None,
                form_method=form_method,
                input_types=input_types[:8],
                control_count=visible_controls_count,
                labeled_control_count=labeled_controls,
                status=form_status,
                accessible_name=aria_label,
                aria_role=aria_role,
                aria_label=aria_label,
                is_machine_readable=bool(form_action and form_method),
                bounded_snippet=bound_text(str(form)[:220]),
                source_location=f"form[{f_idx+1}]",
                source_type="raw_html",
                extraction_method="agent_surface_inspection",
                provenance="multimodal_agent_engine",
            )
            surfaces.append(surface_item)

        # 2. Action Buttons Analysis
        buttons = soup.find_all(["button", "input"])
        for b_idx, btn in enumerate(buttons):
            is_button = False
            if btn.name == "button":
                is_button = True
            elif btn.name == "input":
                t = btn.get("type", "").lower()
                if t in ("submit", "button", "reset"):
                    is_button = True

            if not is_button:
                continue

            evidence.action_buttons_detected += 1
            acc_name = cls._compute_accessible_name(btn)
            has_meaningful_name = bool(
                acc_name
                and len(acc_name.strip()) > 0
                and acc_name.strip().lower() not in GENERIC_LINK_TERMS
            )

            if has_meaningful_name:
                evidence.meaningful_accessible_buttons_count += 1
                status = AgentInteractionStatus.LABELED
            else:
                status = AgentInteractionStatus.UNLABELED

            # Record sample of prominent buttons
            if len(surfaces) < 15:
                surfaces.append(
                    AgentInteractionSurfaceItem(
                        surface_id=f"btn_{b_idx+1}",
                        signal_type=AgentInteractionSignal.ACTION_BUTTON,
                        surface_name=acc_name or "(unnamed button)",
                        control_count=1,
                        labeled_control_count=1 if has_meaningful_name else 0,
                        status=status,
                        accessible_name=acc_name,
                        aria_role=btn.get("role"),
                        aria_label=btn.get("aria-label"),
                        is_machine_readable=has_meaningful_name,
                        bounded_snippet=bound_text(str(btn)[:160]),
                        source_location=f"{btn.name}[{b_idx+1}]",
                        source_type="raw_html",
                        extraction_method="agent_surface_inspection",
                        provenance="multimodal_agent_engine",
                    )
                )

        # 3. Descriptive Navigation Analysis
        nav_elements = soup.find_all(["nav", "div"])
        nav_tags = [n for n in nav_elements if n.name == "nav" or n.get("role") == "navigation"]
        for nav in nav_tags:
            links = nav.find_all("a")
            for link in links:
                text = link.get_text(strip=True).lower()
                aria_l = (link.get("aria-label") or "").lower()
                name_candidate = aria_l or text

                if not name_candidate or name_candidate in GENERIC_LINK_TERMS:
                    evidence.ambiguous_navigation_links_count += 1
                else:
                    evidence.descriptive_navigation_links_count += 1

        # 4. Schema PotentialAction / SearchAction
        script_json_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
        for s_tag in script_json_tags:
            try:
                data = json.loads(s_tag.string or "")
                actions = cls._find_schema_actions(data)
                for act in actions:
                    evidence.schema_actions_detected += 1
                    surfaces.append(
                        AgentInteractionSurfaceItem(
                            surface_id=f"schema_act_{evidence.schema_actions_detected}",
                            signal_type=AgentInteractionSignal.SCHEMA_POTENTIAL_ACTION,
                            surface_name=act.get("@type", "Action"),
                            status=AgentInteractionStatus.EXPLICIT,
                            structured_action_target=str(act.get("target") or act.get("url") or ""),
                            is_machine_readable=True,
                            bounded_snippet=bound_text(json.dumps(act)[:200]),
                            source_location="script[type=application/ld+json]",
                            source_type="schema_jsonld",
                            extraction_method="structured_schema_inspection",
                            provenance="multimodal_agent_engine",
                        )
                    )
            except Exception:
                pass

        # 5. Observable WebMCP Declarations (truthful inspection: only if present in DOM)
        webmcp_meta = soup.find_all("meta", attrs={"name": re.compile(r"webmcp", re.I)})
        webmcp_links = soup.find_all("link", attrs={"rel": re.compile(r"webmcp", re.I)})
        webmcp_scripts = soup.find_all("script", attrs={"type": re.compile(r"webmcp", re.I)})
        total_webmcp = len(webmcp_meta) + len(webmcp_links) + len(webmcp_scripts)
        evidence.webmcp_declarations_detected = total_webmcp

        if total_webmcp > 0:
            for wm_idx, item in enumerate(webmcp_meta + webmcp_links + webmcp_scripts):
                surfaces.append(
                    AgentInteractionSurfaceItem(
                        surface_id=f"webmcp_{wm_idx+1}",
                        signal_type=AgentInteractionSignal.WEBMCP_DECLARATION,
                        surface_name="Observable WebMCP Endpoint Declaration",
                        status=AgentInteractionStatus.EXPLICIT,
                        is_machine_readable=True,
                        bounded_snippet=bound_text(str(item)[:200]),
                        source_location="head",
                        source_type="raw_html",
                        extraction_method="agent_surface_inspection",
                        provenance="multimodal_agent_engine",
                    )
                )

        evidence.surfaces = surfaces
        return evidence

    @classmethod
    def _is_control_labeled(cls, soup: BeautifulSoup, control: Tag) -> bool:
        """Check if an input, select, or textarea control has an explicit or implicit label."""
        # aria-label or aria-labelledby
        if control.get("aria-label") or control.get("aria-labelledby"):
            return True

        # Enclosing <label>
        if control.find_parent("label"):
            return True

        # Explicit <label for="id">
        ctrl_id = control.get("id")
        if ctrl_id and soup.find("label", attrs={"for": ctrl_id}):
            return True

        # Placeholder or title as fallback
        if control.get("placeholder") or control.get("title"):
            return True

        return False

    @classmethod
    def _compute_accessible_name(cls, element: Tag) -> str:
        """Compute the accessible name for an interactive control."""
        # 1. aria-label
        if element.get("aria-label"):
            return element["aria-label"].strip()

        # 2. value attribute for input buttons
        if element.name == "input" and element.get("value"):
            return element["value"].strip()

        # 3. Inner text
        inner_text = element.get_text(strip=True)
        if inner_text:
            return inner_text

        # 4. title attribute
        if element.get("title"):
            return element["title"].strip()

        # 5. Alt of nested img
        nested_img = element.find("img")
        if nested_img and nested_img.get("alt"):
            return nested_img["alt"].strip()

        return ""

    @classmethod
    def _classify_form_purpose(
        cls,
        form: Tag,
        input_types: List[str],
        action: str,
    ) -> Tuple[AgentInteractionSignal, str]:
        """Classify the functional purpose of a form based on its inputs and action."""
        action_lower = action.lower()
        inputs_found = form.find_all("input")
        input_names = [str(i.get("name", "")).lower() for i in inputs_found]

        # 1. Search Form
        if "search" in input_types or any(n in SEARCH_INPUT_NAMES for n in input_names) or "search" in action_lower:
            return AgentInteractionSignal.SEARCH_FORM, "Site Search Form"

        # 2. Login / Auth Form
        if "password" in input_types or any(n in AUTH_INPUT_NAMES for n in input_names) or "login" in action_lower or "signin" in action_lower:
            return AgentInteractionSignal.LOGIN_ACCOUNT_SURFACE, "Authentication Surface"

        # 3. Contact / Inquiry / Quote Form
        if any(n in CONTACT_INPUT_NAMES for n in input_names) or "contact" in action_lower or "quote" in action_lower or "inquiry" in action_lower:
            return AgentInteractionSignal.CONTACT_INQUIRY_FORM, "Inquiry / Contact Surface"

        # Default: General Form Control
        return AgentInteractionSignal.FORM_CONTROL, "Interactive Form Surface"

    @classmethod
    def _find_schema_actions(cls, data: Any) -> List[Dict[str, Any]]:
        """Recursively locate Action or potentialAction entries in JSON-LD data."""
        actions: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            if "potentialAction" in data:
                pa = data["potentialAction"]
                if isinstance(pa, list):
                    actions.extend([x for x in pa if isinstance(x, dict)])
                elif isinstance(pa, dict):
                    actions.append(pa)
            if data.get("@type") in ("SearchAction", "OrderAction", "ReserveAction", "TradeAction"):
                actions.append(data)
            for v in data.values():
                actions.extend(cls._find_schema_actions(v))
        elif isinstance(data, list):
            for item in data:
                actions.extend(cls._find_schema_actions(item))
        return actions

    # =========================================================================
    # Part C: Information Access Path Analysis
    # =========================================================================

    @classmethod
    def _analyze_access_paths(
        cls,
        url: str,
        multimodal_ev: MultimodalInformationEvidence,
        agent_ev: AgentReadinessEvidence,
        answerability_ev: Optional[AnswerabilityEvidence],
        claim_grounding_ev: Optional[ClaimGroundingEvidence],
        entity_ev: Optional[EntityEvidence],
    ) -> List[InformationAccessPathEvidence]:
        """
        Connect multimodal and agent interaction signals to Phase 10.2 answerable units
        and Phase 10.3 claims and entity contacts.
        """
        paths: List[InformationAccessPathEvidence] = []
        path_idx = 1

        # 1. Connect Services (M10.2) to Action Forms / Interaction Surfaces
        if answerability_ev:
            service_units = [
                u for u in answerability_ev.units
                if u.unit_type == AnswerableUnitType.SERVICE_DESCRIPTION
            ]
            inquiry_forms = [
                s for s in agent_ev.surfaces
                if s.signal_type in (AgentInteractionSignal.CONTACT_INQUIRY_FORM, AgentInteractionSignal.FORM_CONTROL)
            ]

            for s_unit in service_units[:4]:
                if inquiry_forms:
                    form_ref = inquiry_forms[0]
                    paths.append(
                        InformationAccessPathEvidence(
                            path_id=f"path_{path_idx}",
                            url=url,
                            path_type="SERVICE_TO_ACTION",
                            related_concept=s_unit.topic or "Service Offering",
                            textual_representation_present=True,
                            agent_action_surface_present=True,
                            representation_status=MultimodalRepresentationStatus.TEXT_REPRESENTED,
                            interaction_status=form_ref.status,
                            linked_unit_id=s_unit.unit_id,
                            description=f"Service '{s_unit.topic or 'Described Service'}' is explained in text and exposed via {form_ref.surface_name}.",
                            evidence_gap_identified=False,
                            bounded_snippet=bound_text(s_unit.snippet, 180),
                            source_location=s_unit.content_location,
                            source_type="dom_cross_layer",
                            extraction_method="access_path_analysis",
                            provenance="multimodal_agent_engine",
                        )
                    )
                    path_idx += 1

        # 2. Connect Contact Information (M10.2 / M10.3) to Form Actions
        contact_units = (
            [u for u in answerability_ev.units if u.unit_type == AnswerableUnitType.LOCATION_CONTACT]
            if answerability_ev else []
        )
        contact_forms = [
            s for s in agent_ev.surfaces
            if s.signal_type == AgentInteractionSignal.CONTACT_INQUIRY_FORM
        ]

        if contact_units and contact_forms:
            c_unit = contact_units[0]
            c_form = contact_forms[0]
            paths.append(
                InformationAccessPathEvidence(
                    path_id=f"path_{path_idx}",
                    url=url,
                    path_type="CONTACT_TO_FORM_ACTION",
                    related_concept="Contact Surface",
                    textual_representation_present=True,
                    agent_action_surface_present=True,
                    representation_status=MultimodalRepresentationStatus.TEXT_REPRESENTED,
                    interaction_status=c_form.status,
                    linked_unit_id=c_unit.unit_id,
                    description=f"Contact info appears in text ({c_unit.content_location}) and in an interactive form ({c_form.surface_name}).",
                    evidence_gap_identified=False,
                    bounded_snippet=bound_text(c_unit.snippet, 180),
                    source_location=c_unit.content_location,
                    source_type="dom_cross_layer",
                    extraction_method="access_path_analysis",
                    provenance="multimodal_agent_engine",
                )
            )
            path_idx += 1

        # 3. Connect Answerable Units to Illustrated Alt Images
        for asset in multimodal_ev.assets:
            if asset.related_unit_id and asset.representation_status in (
                MultimodalRepresentationStatus.ALT_REPRESENTED,
                MultimodalRepresentationStatus.CAPTION_REPRESENTED,
            ):
                paths.append(
                    InformationAccessPathEvidence(
                        path_id=f"path_{path_idx}",
                        url=url,
                        path_type="UNIT_TO_ALT_IMAGE",
                        related_concept=asset.associated_heading or "Information Topic",
                        textual_representation_present=True,
                        multimodal_representation_present=True,
                        representation_status=asset.representation_status,
                        linked_unit_id=asset.related_unit_id,
                        description=(
                            f"Information unit is accompanied by visual asset '{asset.src_or_id[:35]}' "
                            f"with meaningful representation ({asset.representation_status.value})."
                        ),
                        evidence_gap_identified=False,
                        bounded_snippet=bound_text(asset.alt_text or asset.caption_text, 180),
                        source_location=asset.source_location,
                        source_type="dom_cross_layer",
                        extraction_method="access_path_analysis",
                        provenance="multimodal_agent_engine",
                    )
                )
                path_idx += 1

        # 4. Identify Visual-Only Information Limitations (Gaps)
        visual_only_assets = [
            a for a in multimodal_ev.assets
            if a.representation_status == MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED
            and a.is_informational
        ]
        for v_asset in visual_only_assets[:5]:
            paths.append(
                InformationAccessPathEvidence(
                    path_id=f"path_{path_idx}",
                    url=url,
                    path_type="VISUAL_ONLY_GAP",
                    related_concept=v_asset.associated_heading or "Visual Graphic",
                    textual_representation_present=False,
                    multimodal_representation_present=True,
                    representation_status=MultimodalRepresentationStatus.VISUAL_ONLY_OBSERVED,
                    description=(
                        f"Informational visual asset '{v_asset.src_or_id[:35]}' has no observable text, "
                        f"alt, or caption representation. Content appears accessible only visually."
                    ),
                    evidence_gap_identified=True,
                    gap_description=v_asset.visual_only_reason or "Missing textual representation for visual graphic",
                    bounded_snippet=v_asset.bounded_snippet,
                    source_location=v_asset.source_location,
                    source_type="multimodal_gap",
                    extraction_method="access_path_analysis",
                    provenance="multimodal_agent_engine",
                )
            )
            path_idx += 1

        return paths

    # =========================================================================
    # Crawl / Site-Wide Aggregation
    # =========================================================================

    @classmethod
    def evaluate_site(cls, site_crawl: SiteCrawlResult) -> None:
        """
        Aggregate multimodal and agent readiness intelligence across all crawled pages.
        Attaches SiteMultimodalAgentIntelligence to site_crawl.multimodal_agent_intelligence.
        """
        records = [
            r for r in site_crawl.crawl_records
            if getattr(r, "crawl_status", None) and r.crawl_status.value == "FETCHED" and r.status_code == 200
        ]

        if not records:
            site_crawl.multimodal_agent_intelligence = SiteMultimodalAgentIntelligence(
                status="success",
                total_pages_evaluated=0,
                completeness_disclaimer="No successfully crawled 200 OK pages available for multimodal analysis.",
                facts=["Site multimodal aggregation completed with 0 evaluated pages."],
            )
            return

        page_intel: Dict[str, MultimodalAgentIntelligence] = {}
        total_assets = 0
        total_info_images = 0
        total_meaningful_alt = 0
        total_visual_gaps = 0
        total_forms = 0
        total_labeled_ctrls = 0
        total_buttons = 0
        total_schema_actions = 0
        total_webmcp = 0
        total_paths = 0
        total_path_gaps = 0

        for rec in records:
            # Check if multimodal_agent was already computed for the record
            p_intel = getattr(rec, "multimodal_agent", None)
            if not p_intel and rec.raw_html:
                # Deterministic page evaluation fallback
                p_intel = cls.evaluate_page(
                    url=rec.url,
                    raw_html=rec.raw_html,
                    answerability_ev=getattr(rec, "answerability", None),
                    claim_grounding_ev=getattr(rec, "claim_grounding", None),
                )
                rec.multimodal_agent = p_intel

            if p_intel:
                page_intel[rec.url] = p_intel
                total_assets += p_intel.multimodal.total_visual_assets
                total_info_images += p_intel.multimodal.informational_assets_count
                total_meaningful_alt += p_intel.multimodal.alt_represented_count
                total_visual_gaps += p_intel.multimodal.visual_only_observed_count
                total_forms += p_intel.agent_readiness.total_forms_detected
                total_labeled_ctrls += p_intel.agent_readiness.labeled_forms_count
                total_buttons += p_intel.agent_readiness.action_buttons_detected
                total_schema_actions += p_intel.agent_readiness.schema_actions_detected
                total_webmcp += p_intel.agent_readiness.webmcp_declarations_detected
                total_paths += len(p_intel.access_paths)
                total_path_gaps += p_intel.visual_only_gaps_count + p_intel.action_surface_gaps_count

        total_pages = len(page_intel)
        is_partial = getattr(site_crawl, "completeness_status", "") != "CRAWL_COMPLETE"
        disclaimer = (
            "Partial crawl: Multimodal and agent readiness metrics represent observed sample only."
            if is_partial else ""
        )

        facts = [
            f"Evaluated {total_pages} page(s) across site: {total_assets} visual asset(s) observed ({total_info_images} informational, {total_meaningful_alt} with meaningful alt).",
            f"Observed {total_forms} site form(s), {total_buttons} action button(s), {total_schema_actions} schema action(s), {total_webmcp} WebMCP declaration(s).",
            f"Triangulated {total_paths} cross-layer information access path(s) ({total_visual_gaps} visual-only information limitation(s)).",
        ]

        analyses: List[str] = []
        if total_visual_gaps > 0:
            analyses.append(
                f"Across {total_pages} page(s), {total_visual_gaps} visual asset(s) present informational graphics without "
                f"observable text or alt representation. Search engine text indexers and screen readers cannot access this content."
            )
        if total_forms > 0:
            analyses.append(
                f"The site exposes {total_forms} observable interactive form surface(s) for user/agent actions."
            )

        site_intel = SiteMultimodalAgentIntelligence(
            status="success",
            total_pages_evaluated=total_pages,
            is_partial_crawl=is_partial,
            completeness_disclaimer=disclaimer,
            total_site_visual_assets=total_assets,
            total_informational_images=total_info_images,
            total_meaningful_alt_images=total_meaningful_alt,
            total_visual_only_gaps=total_visual_gaps,
            total_site_forms=total_forms,
            total_labeled_controls=total_labeled_ctrls,
            total_action_buttons=total_buttons,
            total_schema_actions=total_schema_actions,
            total_webmcp_declarations=total_webmcp,
            total_access_paths_observed=total_paths,
            total_path_gaps_identified=total_path_gaps,
            page_multimodal_agent_intelligence=page_intel,
            facts=facts,
            analyses=analyses,
        )

        site_crawl.multimodal_agent_intelligence = site_intel
