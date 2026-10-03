"""
Entity Intelligence Engine — Deterministic, evidence-driven extraction, normalization,
relationship mapping, and structured-vs-visible alignment for observable web entities.
"""
from __future__ import annotations
import re
import json
from typing import List, Optional, Tuple, Set, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag

from rankintel.models.schema import (
    EntityEvidence,
    DetectedEntity,
    EntityRelationship,
    VisibleStructuredComparison,
    EntityType,
    EntitySource,
    EntitySignalType,
    EntityAlignmentStatus,
    EntityRelationshipType,
    EvidenceNature,
    OnPageEvidence,
)

# Corporate and legal entity suffixes to strip during loose identity comparison
CORPORATE_SUFFIX_PATTERNS = [
    r"\bprivate\s+limited\b",
    r"\bpvt\.?\s+ltd\.?\b",
    r"\bltd\.?\b",
    r"\blimited\b",
    r"\binc\.?\b",
    r"\bincorporated\b",
    r"\bllc\.?\b",
    r"\bl\.l\.c\.?\b",
    r"\bcorp\.?\b",
    r"\bcorporation\b",
    r"\bco\.?\b",
    r"\bcompany\b",
    r"\bholdings\b",
    r"\bgroup\b",
    r"\bgmbh\b",
    r"\bllp\.?\b",
    r"\bpllc\.?\b",
    r"\bs\.a\.?\b",
    r"\bs\.r\.o\.?\b",
]
CORPORATE_SUFFIX_REGEX = re.compile(
    r"(?:" + "|".join(CORPORATE_SUFFIX_PATTERNS) + r")",
    re.IGNORECASE
)

# Regex to detect visible copyright statements
COPYRIGHT_REGEX = re.compile(
    r"(?:©|&copy;|\(c\)|copyright)\s*(?:20\d\d[-–—\s\d]*)?\s*([^,.\n<]{2,60})",
    re.IGNORECASE
)

# Schema.org type mapping to EntityType
SCHEMA_TYPE_MAP: Dict[str, EntityType] = {
    # Organizations
    "Organization": EntityType.ORGANIZATION,
    "Corporation": EntityType.ORGANIZATION,
    "EducationalOrganization": EntityType.ORGANIZATION,
    "CollegeOrUniversity": EntityType.ORGANIZATION,
    "GovernmentOrganization": EntityType.ORGANIZATION,
    "NGO": EntityType.ORGANIZATION,
    "NewsMediaOrganization": EntityType.ORGANIZATION,
    "OnlineBusiness": EntityType.ORGANIZATION,
    "PerformingGroup": EntityType.ORGANIZATION,
    "SportsOrganization": EntityType.ORGANIZATION,
    "Airline": EntityType.ORGANIZATION,

    # Local Businesses
    "LocalBusiness": EntityType.LOCAL_BUSINESS,
    "Store": EntityType.LOCAL_BUSINESS,
    "Restaurant": EntityType.LOCAL_BUSINESS,
    "MedicalBusiness": EntityType.LOCAL_BUSINESS,
    "FinancialService": EntityType.LOCAL_BUSINESS,
    "ProfessionalService": EntityType.LOCAL_BUSINESS,
    "LegalService": EntityType.LOCAL_BUSINESS,
    "AutomotiveBusiness": EntityType.LOCAL_BUSINESS,
    "AutoRepair": EntityType.LOCAL_BUSINESS,
    "Hotel": EntityType.LOCAL_BUSINESS,
    "LodgingBusiness": EntityType.LOCAL_BUSINESS,
    "HealthAndBeautyBusiness": EntityType.LOCAL_BUSINESS,
    "FoodEstablishment": EntityType.LOCAL_BUSINESS,

    # Person
    "Person": EntityType.PERSON,
    "Author": EntityType.PERSON,

    # Products
    "Product": EntityType.PRODUCT,
    "IndividualProduct": EntityType.PRODUCT,
    "ProductGroup": EntityType.PRODUCT,
    "ProductModel": EntityType.PRODUCT,
    "SoftwareApplication": EntityType.PRODUCT,

    # Services
    "Service": EntityType.SERVICE,
    "FinancialProduct": EntityType.SERVICE,
    "GovernmentService": EntityType.SERVICE,

    # Places
    "Place": EntityType.PLACE,
    "CivicStructure": EntityType.PLACE,
    "TouristAttraction": EntityType.PLACE,
    "AdministrativeArea": EntityType.PLACE,
    "City": EntityType.PLACE,
    "Country": EntityType.PLACE,
    "State": EntityType.PLACE,
    "LandmarksOrHistoricalBuildings": EntityType.PLACE,
}


def normalize_entity_name(name: str) -> str:
    """Normalize entity name by stripping punctuation, extra whitespace, and corporate suffixes."""
    if not name:
        return ""
    # Strip whitespace & quotes
    cleaned = re.sub(r'["\'`]', '', name).strip()
    # Strip corporate suffixes
    stripped = CORPORATE_SUFFIX_REGEX.sub("", cleaned)
    # Strip non-alphanumeric except spaces
    normalized = re.sub(r"[^\w\s]", " ", stripped.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized if normalized else cleaned.lower().strip()


def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to standard digit representation."""
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", phone)
    return digits


def format_postal_address(addr: Any) -> Optional[str]:
    """Convert a schema.org PostalAddress dict or string to a normalized string."""
    if isinstance(addr, str):
        return addr.strip()
    if isinstance(addr, dict):
        parts = []
        for key in ["streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"]:
            val = addr.get(key)
            if val and isinstance(val, str) and val.strip():
                parts.append(val.strip())
        return ", ".join(parts) if parts else None
    return None


class EntityEngine:
    """
    Deterministic, evidence-driven Entity Intelligence Engine.
    Operates strictly on provided DOM / raw HTML without initiating network calls.
    """

    @classmethod
    def evaluate(
        cls,
        raw_html: Optional[str],
        url: str = "",
        on_page: Optional[OnPageEvidence] = None,
    ) -> EntityEvidence:
        """
        Evaluate page evidence for observable entities, relationships,
        and structured data vs visible content alignment.
        """
        if not raw_html or not raw_html.strip():
            return EntityEvidence(
                url=url,
                facts=["No HTML content was provided or response body was empty."],
            )

        soup = BeautifulSoup(raw_html, "html.parser")
        detected_entities: List[DetectedEntity] = []
        relationships: List[EntityRelationship] = []

        # 1. Structured Data (JSON-LD) Extraction
        jsonld_entities, jsonld_rels = cls._extract_jsonld(soup, url)
        detected_entities.extend(jsonld_entities)
        relationships.extend(jsonld_rels)

        # 2. Microdata Extraction
        microdata_entities = cls._extract_microdata(soup, url)
        detected_entities.extend(microdata_entities)

        # 3. Meta Tag Entity Signals (og:site_name, author, copyright, geo)
        meta_entities, meta_rels = cls._extract_meta_signals(soup, url)
        detected_entities.extend(meta_entities)
        relationships.extend(meta_rels)

        # 4. Visible HTML Signals (Copyright text, <address>, tel:, mailto:)
        visible_entities, visible_rels = cls._extract_visible_signals(soup, url)
        detected_entities.extend(visible_entities)
        relationships.extend(visible_rels)

        # 5. Website-to-Organization Relationship (if domain matches organization url or identity)
        if url:
            cls._link_domain_relationships(url, detected_entities, relationships)

        # 6. Structured Data ↔ Visible Content Contextual Comparison
        comparisons = cls._compare_structured_vs_visible(
            detected_entities=detected_entities,
            soup=soup,
            on_page=on_page,
            url=url,
        )

        # Build summary facts
        facts: List[str] = []
        types_count: Dict[str, int] = {}
        for ent in detected_entities:
            t_name = ent.entity_type.value
            types_count[t_name] = types_count.get(t_name, 0) + 1

        if detected_entities:
            type_summary = ", ".join(f"{k}: {v}" for k, v in types_count.items())
            facts.append(f"Detected {len(detected_entities)} entity signals ({type_summary}).")
        else:
            facts.append("No explicit entity declarations or visible entity signals detected.")

        if relationships:
            facts.append(f"Recorded {len(relationships)} observable entity relationships.")

        return EntityEvidence(
            url=url,
            total_entities_detected=len(detected_entities),
            detected_entities=detected_entities,
            relationships=relationships,
            structured_vs_visible=comparisons,
            facts=facts,
        )

    # -------------------------------------------------------------------------
    # JSON-LD Extraction
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_jsonld(cls, soup: BeautifulSoup, page_url: str) -> Tuple[List[DetectedEntity], List[EntityRelationship]]:
        entities: List[DetectedEntity] = []
        relationships: List[EntityRelationship] = []

        script_tags = soup.find_all("script", type="application/ld+json")
        for tag in script_tags:
            c = tag.string if tag.string else tag.text
            if not c or not c.strip():
                continue
            try:
                data = json.loads(c, strict=False)
            except Exception:
                continue

            items: List[Dict[str, Any]] = []
            if isinstance(data, list):
                items = [d for d in data if isinstance(d, dict)]
            elif isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items = [d for d in data["@graph"] if isinstance(d, dict)]
                else:
                    items = [data]

            for item in items:
                cls._parse_jsonld_item(item, page_url, entities, relationships)

        return entities, relationships

    @classmethod
    def _parse_jsonld_item(
        cls,
        item: Dict[str, Any],
        page_url: str,
        entities: List[DetectedEntity],
        relationships: List[EntityRelationship],
    ):
        raw_types = item.get("@type")
        if not raw_types:
            return

        type_list = raw_types if isinstance(raw_types, list) else [raw_types]
        matched_entity_type: Optional[EntityType] = None
        matched_type_name = str(type_list[0])

        for t in type_list:
            t_str = str(t)
            if t_str in SCHEMA_TYPE_MAP:
                matched_entity_type = SCHEMA_TYPE_MAP[t_str]
                matched_type_name = t_str
                break

        if not matched_entity_type:
            # Fallback substring match
            for t in type_list:
                t_str = str(t)
                for schema_key, ent_enum in SCHEMA_TYPE_MAP.items():
                    if schema_key.lower() in t_str.lower():
                        matched_entity_type = ent_enum
                        matched_type_name = t_str
                        break
                if matched_entity_type:
                    break

        name = item.get("name")
        if isinstance(name, dict):
            name = name.get("@value") or name.get("text")
        if not name or not isinstance(name, str) or not name.strip():
            # Fallback for Person: check 'givenName' / 'familyName'
            if matched_entity_type == EntityType.PERSON and ("givenName" in item or "familyName" in item):
                name = f"{item.get('givenName', '')} {item.get('familyName', '')}".strip()
            # Fallback for Organization: check 'legalName' or 'brand'
            elif matched_entity_type in (EntityType.ORGANIZATION, EntityType.LOCAL_BUSINESS) and "legalName" in item:
                name = str(item.get("legalName")).strip()

        if not name or not isinstance(name, str) or not name.strip():
            return

        name = name.strip()
        telephone = item.get("telephone")
        email = item.get("email")
        description = item.get("description")
        if isinstance(description, str):
            description = description.strip()[:300]
        else:
            description = None

        address_str = format_postal_address(item.get("address"))

        same_as: List[str] = []
        raw_sameas = item.get("sameAs")
        if isinstance(raw_sameas, str):
            same_as = [raw_sameas.strip()]
        elif isinstance(raw_sameas, list):
            same_as = [str(u).strip() for u in raw_sameas if isinstance(u, str) and u.strip().startswith("http")]

        identifiers: Dict[str, str] = {}
        for id_key in ["sku", "gtin", "gtin13", "gtin14", "mpn", "productID"]:
            if item.get(id_key):
                identifiers[id_key] = str(item[id_key]).strip()

        ent = DetectedEntity(
            entity_type=matched_entity_type or EntityType.OTHER,
            name=name,
            normalized_name=normalize_entity_name(name),
            source=EntitySource.JSON_LD,
            signal_type=EntitySignalType.STRUCTURED_DATA_DECLARATION,
            url=page_url,
            structured_data_type=matched_type_name,
            description=description,
            telephone=str(telephone).strip() if telephone else None,
            email=str(email).strip() if email else None,
            address=address_str,
            same_as=same_as,
            identifiers=identifiers,
            confidence_nature=EvidenceNature.OBSERVED,
        )
        entities.append(ent)

        # ---------------------------------------------------------------------
        # Observable Sub-Entity Relationships
        # ---------------------------------------------------------------------
        # 1. Organization -> Location
        if address_str and ent.entity_type in (EntityType.ORGANIZATION, EntityType.LOCAL_BUSINESS):
            relationships.append(EntityRelationship(
                subject_name=name,
                subject_type=ent.entity_type,
                relation=EntityRelationshipType.ORGANIZATION_TO_LOCATION,
                object_name=address_str,
                object_type="PostalAddress",
                source="json_ld",
                evidence_text=f"Address declared in {matched_type_name} structured data",
            ))

        # 2. Organization -> Social Profile (sameAs)
        for s_url in same_as:
            relationships.append(EntityRelationship(
                subject_name=name,
                subject_type=ent.entity_type,
                relation=EntityRelationshipType.ORGANIZATION_TO_SOCIAL_PROFILE,
                object_name=s_url,
                object_type="SocialProfile",
                source="json_ld",
                evidence_text=f"sameAs reference in {matched_type_name} structured data",
            ))

        # 3. Product -> Organization (brand / manufacturer)
        if ent.entity_type == EntityType.PRODUCT:
            brand_val = item.get("brand") or item.get("manufacturer")
            brand_name = None
            if isinstance(brand_val, dict):
                brand_name = brand_val.get("name")
            elif isinstance(brand_val, str):
                brand_name = brand_val.strip()

            if brand_name:
                relationships.append(EntityRelationship(
                    subject_name=name,
                    subject_type=EntityType.PRODUCT,
                    relation=EntityRelationshipType.PRODUCT_TO_ORGANIZATION,
                    object_name=brand_name,
                    object_type="Organization",
                    source="json_ld",
                    evidence_text=f"Product brand/manufacturer in {matched_type_name}",
                ))

        # 4. Service -> Organization (provider / broker)
        if ent.entity_type == EntityType.SERVICE:
            prov_val = item.get("provider") or item.get("broker")
            prov_name = None
            if isinstance(prov_val, dict):
                prov_name = prov_val.get("name")
            elif isinstance(prov_val, str):
                prov_name = prov_val.strip()

            if prov_name:
                relationships.append(EntityRelationship(
                    subject_name=name,
                    subject_type=EntityType.SERVICE,
                    relation=EntityRelationshipType.SERVICE_TO_ORGANIZATION,
                    object_name=prov_name,
                    object_type="Organization",
                    source="json_ld",
                    evidence_text=f"Service provider declared in {matched_type_name}",
                ))

        # 5. Person -> Organization (worksFor / affiliation)
        if ent.entity_type == EntityType.PERSON:
            works_val = item.get("worksFor") or item.get("affiliation")
            org_name = None
            if isinstance(works_val, dict):
                org_name = works_val.get("name")
            elif isinstance(works_val, str):
                org_name = works_val.strip()

            if org_name:
                relationships.append(EntityRelationship(
                    subject_name=name,
                    subject_type=EntityType.PERSON,
                    relation=EntityRelationshipType.PERSON_TO_ORGANIZATION,
                    object_name=org_name,
                    object_type="Organization",
                    source="json_ld",
                    evidence_text=f"Person worksFor/affiliation in {matched_type_name}",
                ))

    # -------------------------------------------------------------------------
    # Microdata Extraction
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_microdata(cls, soup: BeautifulSoup, page_url: str) -> List[DetectedEntity]:
        entities: List[DetectedEntity] = []
        for elem in soup.find_all(attrs={"itemscope": True}):
            itemtype = elem.get("itemtype")
            if not itemtype or not isinstance(itemtype, str):
                continue

            matched_type: Optional[EntityType] = None
            for k, v in SCHEMA_TYPE_MAP.items():
                if k.lower() in itemtype.lower():
                    matched_type = v
                    break

            if not matched_type:
                continue

            # Extract name
            name_elem = elem.find(attrs={"itemprop": "name"})
            name = None
            if name_elem:
                name = name_elem.get("content") or name_elem.get_text()

            if not name or not name.strip():
                continue

            name = name.strip()
            tel_elem = elem.find(attrs={"itemprop": "telephone"})
            tel = tel_elem.get("content") or tel_elem.get_text() if tel_elem else None

            entities.append(DetectedEntity(
                entity_type=matched_type,
                name=name,
                normalized_name=normalize_entity_name(name),
                source=EntitySource.MICRODATA,
                signal_type=EntitySignalType.STRUCTURED_DATA_DECLARATION,
                url=page_url,
                structured_data_type=itemtype.split("/")[-1],
                telephone=tel.strip() if tel else None,
                confidence_nature=EvidenceNature.OBSERVED,
            ))
        return entities

    # -------------------------------------------------------------------------
    # Meta Tag Signals
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_meta_signals(cls, soup: BeautifulSoup, page_url: str) -> Tuple[List[DetectedEntity], List[EntityRelationship]]:
        entities: List[DetectedEntity] = []
        relationships: List[EntityRelationship] = []

        # 1. og:site_name -> Brand or site name signal (NOT automatically a verified Organization)
        og_site_name = soup.find("meta", property="og:site_name")
        if og_site_name and og_site_name.get("content"):
            name = og_site_name["content"].strip()
            if name:
                entities.append(DetectedEntity(
                    entity_type=EntityType.ORGANIZATION,
                    name=name,
                    normalized_name=normalize_entity_name(name),
                    source=EntitySource.META_TAG,
                    signal_type=EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL,
                    url=page_url,
                    raw_context="meta[property='og:site_name']",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        # 2. meta name="author" or property="article:author"
        author_tag = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", property="article:author")
        if author_tag and author_tag.get("content"):
            author_val = author_tag["content"].strip()
            # Ignore url format author tags, keep names
            if author_val and not author_val.startswith("http") and len(author_val) < 80:
                entities.append(DetectedEntity(
                    entity_type=EntityType.PERSON,
                    name=author_val,
                    normalized_name=normalize_entity_name(author_val),
                    source=EntitySource.META_TAG,
                    signal_type=EntitySignalType.AUTHOR_BYLINE_SIGNAL,
                    url=page_url,
                    raw_context="meta[name='author']",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        # 3. meta name="copyright"
        copy_tag = soup.find("meta", attrs={"name": "copyright"})
        if copy_tag and copy_tag.get("content"):
            copy_val = copy_tag["content"].strip()
            if copy_val and len(copy_val) < 80:
                entities.append(DetectedEntity(
                    entity_type=EntityType.ORGANIZATION,
                    name=copy_val,
                    normalized_name=normalize_entity_name(copy_val),
                    source=EntitySource.META_TAG,
                    signal_type=EntitySignalType.COPYRIGHT_SIGNAL,
                    url=page_url,
                    raw_context="meta[name='copyright']",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        # 4. meta name="geo.placename"
        geo_tag = soup.find("meta", attrs={"name": "geo.placename"})
        if geo_tag and geo_tag.get("content"):
            geo_val = geo_tag["content"].strip()
            if geo_val:
                entities.append(DetectedEntity(
                    entity_type=EntityType.PLACE,
                    name=geo_val,
                    normalized_name=normalize_entity_name(geo_val),
                    source=EntitySource.META_TAG,
                    signal_type=EntitySignalType.CONTACT_SIGNAL,
                    url=page_url,
                    raw_context="meta[name='geo.placename']",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        return entities, relationships

    # -------------------------------------------------------------------------
    # Visible Signals (Copyright, address, tel, mailto)
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_visible_signals(cls, soup: BeautifulSoup, page_url: str) -> Tuple[List[DetectedEntity], List[EntityRelationship]]:
        entities: List[DetectedEntity] = []
        relationships: List[EntityRelationship] = []

        # 1. Visible copyright statement in footer or text
        footer = soup.find("footer") or soup.find(class_=re.compile(r"footer", re.I)) or soup
        footer_text = footer.get_text(separator=" ", strip=True) if footer else ""

        c_match = COPYRIGHT_REGEX.search(footer_text)
        if c_match:
            raw_c_name = c_match.group(1).strip()
            # Clean common trailing words like "All rights reserved", "Inc", etc.
            raw_c_name = re.sub(r"\b(all rights reserved|rights reserved)\b.*", "", raw_c_name, flags=re.I).strip(" ,.-|")
            if raw_c_name and len(raw_c_name) >= 2 and len(raw_c_name) <= 60:
                entities.append(DetectedEntity(
                    entity_type=EntityType.ORGANIZATION,
                    name=raw_c_name,
                    normalized_name=normalize_entity_name(raw_c_name),
                    source=EntitySource.VISIBLE_HTML,
                    signal_type=EntitySignalType.COPYRIGHT_SIGNAL,
                    url=page_url,
                    raw_context=f"Copyright notice: '{c_match.group(0).strip()}'",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        # 2. <address> tag
        addr_tag = soup.find("address")
        if addr_tag:
            addr_text = addr_tag.get_text(separator=" ", strip=True)
            if addr_text and len(addr_text) > 5 and len(addr_text) < 250:
                entities.append(DetectedEntity(
                    entity_type=EntityType.LOCAL_BUSINESS,
                    name=addr_text[:60],
                    normalized_name=normalize_entity_name(addr_text[:60]),
                    source=EntitySource.VISIBLE_HTML,
                    signal_type=EntitySignalType.CONTACT_SIGNAL,
                    url=page_url,
                    address=addr_text,
                    raw_context="<address> tag content",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        # 3. Visible tel: links
        for a_tel in soup.find_all("a", href=re.compile(r"^tel:", re.I))[:3]:
            href = a_tel.get("href", "")
            raw_phone = href[4:].strip()
            clean_phone = normalize_phone_number(raw_phone)
            if clean_phone and len(clean_phone) >= 7:
                entities.append(DetectedEntity(
                    entity_type=EntityType.LOCAL_BUSINESS,
                    name=f"Contact Phone ({clean_phone})",
                    normalized_name=clean_phone,
                    source=EntitySource.VISIBLE_HTML,
                    signal_type=EntitySignalType.CONTACT_SIGNAL,
                    url=page_url,
                    telephone=clean_phone,
                    raw_context=f"tel link: {href}",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        # 4. Visible mailto: links
        for a_mail in soup.find_all("a", href=re.compile(r"^mailto:", re.I))[:2]:
            href = a_mail.get("href", "")
            raw_mail = href[7:].split("?")[0].strip()
            if raw_mail and "@" in raw_mail and len(raw_mail) < 80:
                entities.append(DetectedEntity(
                    entity_type=EntityType.ORGANIZATION,
                    name=f"Contact Email ({raw_mail})",
                    normalized_name=raw_mail.lower(),
                    source=EntitySource.VISIBLE_HTML,
                    signal_type=EntitySignalType.CONTACT_SIGNAL,
                    url=page_url,
                    email=raw_mail,
                    raw_context=f"mailto link: {href}",
                    confidence_nature=EvidenceNature.OBSERVED,
                ))

        return entities, relationships

    # -------------------------------------------------------------------------
    # Domain Relationship Linking
    # -------------------------------------------------------------------------
    @classmethod
    def _link_domain_relationships(
        cls,
        page_url: str,
        entities: List[DetectedEntity],
        relationships: List[EntityRelationship],
    ):
        try:
            parsed = urlparse(page_url)
            domain = parsed.netloc.lower().removeprefix("www.")
        except Exception:
            return

        for ent in entities:
            if ent.entity_type in (EntityType.ORGANIZATION, EntityType.LOCAL_BUSINESS):
                if ent.source == EntitySource.JSON_LD:
                    relationships.append(EntityRelationship(
                        subject_name=ent.name,
                        subject_type=ent.entity_type,
                        relation=EntityRelationshipType.ORGANIZATION_TO_WEBSITE,
                        object_name=domain,
                        object_type="WebSite",
                        source="domain_context",
                        evidence_text=f"Organization {ent.name} declared on website origin {domain}",
                    ))

    # -------------------------------------------------------------------------
    # Contextual Structured Data ↔ Visible Content Comparison
    # -------------------------------------------------------------------------
    @classmethod
    def _compare_structured_vs_visible(
        cls,
        detected_entities: List[DetectedEntity],
        soup: BeautifulSoup,
        on_page: Optional[OnPageEvidence],
        url: str,
    ) -> List[VisibleStructuredComparison]:
        """
        Compare structured data declarations against visible brand/text signals.
        Strictly applies contextual identity normalization (e.g. corporate suffixes)
        rather than naive string comparison to avoid false positive alarms.
        """
        comparisons: List[VisibleStructuredComparison] = []

        # Find primary structured organization / business
        structured_orgs = [
            e for e in detected_entities
            if e.source == EntitySource.JSON_LD and e.entity_type in (EntityType.ORGANIZATION, EntityType.LOCAL_BUSINESS)
        ]

        # Find visible brand signals (og:site_name, copyright, header brand)
        visible_brand_signals = [
            e for e in detected_entities
            if e.source in (EntitySource.META_TAG, EntitySource.VISIBLE_HTML)
            and e.signal_type in (EntitySignalType.BRAND_OR_SITE_NAME_SIGNAL, EntitySignalType.COPYRIGHT_SIGNAL)
        ]

        if structured_orgs and visible_brand_signals:
            for s_org in structured_orgs[:2]:
                for v_signal in visible_brand_signals[:2]:
                    status, note = cls._evaluate_name_alignment(s_org.name, v_signal.name)
                    comparisons.append(VisibleStructuredComparison(
                        entity_type=s_org.entity_type,
                        attribute_name="organization_name",
                        structured_value=s_org.name,
                        visible_value=v_signal.name,
                        alignment_status=status,
                        notes=note,
                    ))

        # Check Product / Service structured name vs visible H1 or Title
        structured_products = [
            e for e in detected_entities
            if e.source == EntitySource.JSON_LD and e.entity_type in (EntityType.PRODUCT, EntityType.SERVICE)
        ]
        if structured_products and on_page and on_page.h1_text:
            for s_prod in structured_products[:2]:
                h1_candidate = on_page.h1_text[0]
                status, note = cls._evaluate_name_alignment(s_prod.name, h1_candidate)
                comparisons.append(VisibleStructuredComparison(
                    entity_type=s_prod.entity_type,
                    attribute_name="product_or_service_name",
                    structured_value=s_prod.name,
                    visible_value=h1_candidate,
                    alignment_status=status,
                    notes=f"JSON-LD product name compared with visible <h1>: {note}",
                ))

        # Check structured telephone vs visible phone
        s_phones = [e.telephone for e in structured_orgs if e.telephone]
        v_phones = [e.telephone for e in detected_entities if e.source == EntitySource.VISIBLE_HTML and e.telephone]
        if s_phones and v_phones:
            s_p = normalize_phone_number(s_phones[0])
            v_p = normalize_phone_number(v_phones[0])
            if s_p == v_p or (len(s_p) >= 7 and s_p[-7:] == v_p[-7:]):
                comparisons.append(VisibleStructuredComparison(
                    entity_type=EntityType.LOCAL_BUSINESS,
                    attribute_name="telephone",
                    structured_value=s_phones[0],
                    visible_value=v_phones[0],
                    alignment_status=EntityAlignmentStatus.EXACT_MATCH,
                    notes="Structured phone matches visible tel link.",
                ))
            else:
                comparisons.append(VisibleStructuredComparison(
                    entity_type=EntityType.LOCAL_BUSINESS,
                    attribute_name="telephone",
                    structured_value=s_phones[0],
                    visible_value=v_phones[0],
                    alignment_status=EntityAlignmentStatus.DIVERGENT_IDENTITY_SUSPECTED,
                    notes="Structured telephone number differs from visible contact tel link (manual review recommended).",
                ))

        return comparisons

    @classmethod
    def _evaluate_name_alignment(cls, name_a: str, name_b: str) -> Tuple[EntityAlignmentStatus, str]:
        """
        Compare two entity name signals with corporate suffix stripping and token overlap.
        Never flags a mismatch for standard corporate suffix or brand prefix variations.
        """
        if not name_a or not name_b:
            return EntityAlignmentStatus.UNAVAILABLE, "One or both names unavailable for comparison."

        # 1. Exact match
        if name_a.strip().lower() == name_b.strip().lower():
            return EntityAlignmentStatus.EXACT_MATCH, "Exact character match."

        # 2. Normalized match (corporate suffix stripped)
        norm_a = normalize_entity_name(name_a)
        norm_b = normalize_entity_name(name_b)

        if norm_a == norm_b:
            return (
                EntityAlignmentStatus.NORMALIZED_MATCH,
                "Names match after normalizing whitespace, punctuation, and legal entity suffixes."
            )

        # 3. Substring / Token overlap check
        tokens_a = set(norm_a.split())
        tokens_b = set(norm_b.split())

        if not tokens_a or not tokens_b:
            return EntityAlignmentStatus.UNAVAILABLE, "Insufficient tokens for comparison."

        common = tokens_a & tokens_b
        if tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a):
            return (
                EntityAlignmentStatus.PARTIAL_MATCH,
                f"One brand name is a subset of the other (shared core tokens: '{' '.join(common)}')."
            )

        overlap_ratio = len(common) / max(len(tokens_a), len(tokens_b))
        if overlap_ratio >= 0.5:
            return (
                EntityAlignmentStatus.PARTIAL_MATCH,
                f"Substantial brand token overlap ({int(overlap_ratio * 100)}% shared terms: '{' '.join(common)}')."
            )

        # 4. Completely disjoint tokens
        return (
            EntityAlignmentStatus.DIVERGENT_IDENTITY_SUSPECTED,
            f"Structured entity '{name_a}' and visible signal '{name_b}' share no common brand tokens. Review recommended."
        )
