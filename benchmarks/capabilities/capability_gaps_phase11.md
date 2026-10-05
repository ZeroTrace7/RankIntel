# RankIntel Capability-Gap Discovery & Engine Evolution Analysis — Phase 11.4

> **Report Version:** 11.4  
> **Generated Date:** 2026-10-05  
> **Target Domain:** `sunrisetesting.vercel.app`  
> **Benchmark Population:** 11 permanent benchmark sites  
> **Total Gaps Cataloged:** 18 (P0: 2, P1: 8, P2: 8, P3: 0)  
> **False-Gap Exclusions:** 5 confirmed website deficiencies  
> **Formula Invariance:** Verified (Δ = 0)  
> **Execution Mode:** Strictly Offline (0 network requests)

---

## 1. Executive Summary & Epistemic Boundaries

Phase 11.4 establishes RankIntel's self-reflective Capability-Gap Discovery & Engine Evolution Analysis. Forensic investigation across the permanent 11-site benchmark identified 15 true capability gaps, 1 reporting defects, and 2 evidence limitations spanning 11 categories. Crucially, 5 candidate gaps were ruled out as genuine website deficiencies rather than engine defects. Top architectural evolution priorities for M11.5 include P0 Brand Entity Fallback Detection on schema-less sites, P0 Headless Browser DOM rendering in benchmark workers, P1 Entity Deduplication & Disambiguation, and P1 Multi-Class B2B Intent Modeling.

> [!IMPORTANT]
> **The Critical Epistemic Distinction**: RankIntel strictly separates **Website Deficiencies** (attributes a target website lacks in its own HTML/HTTP headers, e.g. missing `/llms.txt` or 0% image alt text) from **RankIntel Capability Gaps** (observable website evidence that RankIntel fails to detect, interpret, classify, or compare reliably). Never label a website deficiency as an engine defect.

## 2. Capability Gap Priority & Engine Distribution

| Priority Severity | Count | Architectural Description |
| :---: | :---: | :--- |
| **P0** | `2` | Critical architectural or detection gap causing total engine blindness |
| **P1** | `8` | Major semantic or extraction gap causing substantial analysis distortion |
| **P2** | `8` | Moderate heuristic, sanitization, or coverage limitation |
| **P3** | `0` | Minor cosmetic or peripheral reporting discrepancy |

### Engine Distribution

| Affected Engine / Subsystem | Discovered Gaps | Primary Gap Focus |
| :--- | :---: | :--- |
| `entity_engine` | 4 | Focused engine evolution target |
| `collector` | 2 | Focused engine evolution target |
| `multimodal_agent_engine` | 2 | Focused engine evolution target |
| `search_intent_engine` | 1 | Focused engine evolution target |
| `topic_engine` | 1 | Focused engine evolution target |
| `cannibalization_engine` | 1 | Focused engine evolution target |
| `answerability_engine` | 1 | Focused engine evolution target |
| `claim_grounding_engine` | 1 | Focused engine evolution target |
| `retrieval_readiness_engine` | 1 | Focused engine evolution target |
| `comparison_reporter` | 1 | Focused engine evolution target |
| `comparator` | 1 | Focused engine evolution target |
| `synthesis` | 1 | Focused engine evolution target |
| `external_visibility_engine` | 1 | Focused engine evolution target |

## 3. Discovered RankIntel Capability Gaps & Limitations Catalog

| Gap ID | Category | Engine | Severity | Title | Confidence |
| :--- | :--- | :--- | :---: | :--- | :---: |
| `GAP-ENT-001` | EXTRACTION_BLIND_SPOT | `entity_engine.py` | **P1** | Entity Duplication Across DOM Surfaces Without Canonical Disambiguation | 95% |
| `GAP-ENT-002` | DETECTION_BLIND_SPOT | `entity_engine.py` | **P0** | Primary Business Organization Entity Missed on Schema-less Websites | 98% |
| `GAP-ENT-003` | EXTRACTION_BLIND_SPOT | `entity_engine.py` | **P2** | Character Encoding Artifacts Corrupting Entity and Topic Tokens | 95% |
| `GAP-ENT-004` | SEMANTIC_INTERPRETATION | `entity_engine.py` | **P1** | Navigation Menus, Slogans, and Addresses Ingested as Entity Names | 92% |
| `GAP-INTENT-001` | SEARCH_INTENT | `search_intent_engine.py` | **P1** | Coarse Search Intent Classification Skewed Heavily Toward Transactional | 90% |
| `GAP-TOPIC-001` | TOPIC_DIFFERENTIATION | `topic_engine.py` | **P1** | Unigram Topic Fragmentation Lacking Multi-Word Technical Domain Keyphrases | 94% |
| `GAP-TOPIC-002` | TOPIC_DIFFERENTIATION | `cannibalization_engine.py` | **P2** | Single-Page Cannibalization Engine Execution Reporting False Clean Pass | 93% |
| `GAP-ANSWER-001` | EXTRACTION_BLIND_SPOT | `answerability_engine.py` | **P1** | Rigid Syntax Heuristics Missing Modern Web Card and List Answer Structures | 92% |
| `GAP-GROUND-001` | ENTITY_CLAIM_GROUNDING | `claim_grounding_engine.py` | **P1** | Tautological On-Page Lexical Matching in Claim Grounding Verification | 91% |
| `GAP-RETRIEVAL-001` | DETECTION_BLIND_SPOT | `collector.py` | **P0** | Benchmark Collection Pipeline Bypassed Headless Browser JS DOM Rendering | 99% |
| `GAP-RETRIEVAL-002` | AI_GEO_INTERPRETATION | `retrieval_readiness_engine.py` | **P2** | Passive Cloudflare Reverse Proxy Headers Conflated with Active Access Blocking | 89% |
| `GAP-MM-001` | MULTIMODAL_AGENT | `multimodal_agent_engine.py` | **P2** | Images Missing Alt Attributes Heuristically Defaulted to Decorative | 88% |
| `GAP-MM-002` | EXTRACTION_BLIND_SPOT | `multimodal_agent_engine.py` | **P2** | Absence of Visual OCR for Text Embedded in Lab Certificates & Technical Charts | 93% |
| `GAP-AGENT-001` | SEMANTIC_INTERPRETATION | `comparison_reporter.py` | **P1** | Interactive Action Buttons and Web Forms Conflated Under 'Forms' Column | 97% |
| `GAP-COMP-001` | CROSS_SITE_COMPARISON | `comparator.py` | **P2** | Static Hardcoded Void Rules Failing to Discover Open-Domain Competitor Capabilities | 88% |
| `GAP-REC-001` | RECOMMENDATION_QUALITY | `synthesis` | **P2** | Generic SEO Recommendation Templates Disconnected from B2B Industrial Context | 90% |
| `LIM-EVID-001` | EVIDENCE_PROVENANCE | `collector.py` | **P1** | Single-Landing-Page Crawl Scope Extrapolated to Whole-Site Assessment | 96% |
| `LIM-EVID-002` | EVIDENCE_PROVENANCE | `external_visibility_engine.py` | **P2** | External AI Visibility Measurement Disabled by Design in Benchmark Pass | 99% |

### Detailed Forensic Gap Specifications

#### `GAP-ENT-001`: Entity Duplication Across DOM Surfaces Without Canonical Disambiguation
- **Category:** `EXTRACTION_BLIND_SPOT` | **Severity:** `P1` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/entity_engine.py` | **Confidence:** `95%`
- **Observed Evidence:** On alephindia.in: 'Aleph INDIA' extracted 4 duplicate times, phone '+911234567890' 2 times. On standphillindia.in: 'Standphill India' extracted 4 times, phone '+919667674225' 3 times, email 2 times. On umspcs.in: 'UMSPCS' extracted 4 times, phone '+917011067811' 3 times. On sunrisetesting.vercel.app: phone '+919326048829' extracted 3 times, email 'sunqms@gmail.com' 2 times.
- **Why Current Output is Insufficient:** Raw entities parsed from header, main body, footer, contact widgets, and meta tags are appended directly to the entity array without canonical deduplication, surface merging, or entity ID resolution. This artificially inflates entity counts and distorts knowledge-graph entity density metrics.
- **Supporting Benchmark Sites:** `alephindia.in`, `www.standphillindia.in`, `umspcs.in`, `sunrisetesting.vercel.app`, `www.ascgroup.in`, `www.tcreng.com`
- **Expected Behavior:** Multi-surface entity deduplication where occurrences of the same normalized name, phone (E.164), and email are unified into a single canonical entity record preserving multi-surface provenance tags.
- **Recommended Future Direction:** Implement a canonical Entity Deduplication & Resolution pipeline in entity_engine.py that clusters mentions by canonical key (type + normalized_value) before passing to synthesis.

#### `GAP-ENT-002`: Primary Business Organization Entity Missed on Schema-less Websites
- **Category:** `DETECTION_BLIND_SPOT` | **Severity:** `P0` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/entity_engine.py` | **Confidence:** `98%`
- **Observed Evidence:** On yadavmeasurements.com: 0 entities detected (total_entities_detected=0), despite title stating 'India's Leading Private Testing, Calibration Company - Yadav Measurements'. On qualityinternational.org: 0 organization entities detected (only 2 email addresses). On uniquemeasurement.com: 0 organization entities detected (only 3 phone numbers). On sunrisetesting.vercel.app: 'Sunrise Testing & Calibration Centre' is absent from entity_names (only an address string and contact details were detected).
- **Why Current Output is Insufficient:** If a website lacks Schema.org JSON-LD and its copyright footer does not match rigid regex patterns, RankIntel fails completely to identify the primary business or brand name as an entity, even when prominently declared in the title tag, H1 heading, and page copy.
- **Supporting Benchmark Sites:** `www.yadavmeasurements.com`, `qualityinternational.org`, `www.uniquemeasurement.com`, `sunrisetesting.vercel.app`
- **Expected Behavior:** Multi-signal brand/organization fallback extraction combining title tag delimiter parsing (e.g. '[Name] | [Brand]'), H1 header heuristics, OpenGraph og:site_name, and domain lexical matching when structured JSON-LD is absent.
- **Recommended Future Direction:** Introduce a Deterministic Brand/Organization Heuristic Fallback in entity_engine.py to guarantee extraction of the primary organization entity for all reachable websites.

#### `GAP-ENT-003`: Character Encoding Artifacts Corrupting Entity and Topic Tokens
- **Category:** `EXTRACTION_BLIND_SPOT` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/entity_engine.py` | **Confidence:** `95%`
- **Observed Evidence:** On alephindia.in: Entity 'Aleph INDIA 2009 - 2026', Topic 'INDIA'. On ascgroup.in: Entity ' 2026 ASC', Topics 'ASC Group', 'Group'. On tcreng.com: Entity '19732026 TCR Engineering Services Pvt'. On zaubacorp.com: Entity ' 2026 Zauba Corp'. On yadavmeasurements.com: Topic 'Indias'.
- **Why Current Output is Insufficient:** Windows-1252 / ISO-8859-1 byte sequences (such as copyright symbols, en-dashes, and curly quotes) in raw HTML response bodies are decoded as replacement character '\ufffd' or mangled byte tokens, polluting downstream entity arrays, topic samples, and search intent signals.
- **Supporting Benchmark Sites:** `alephindia.in`, `www.ascgroup.in`, `www.tcreng.com`, `www.zaubacorp.com`, `www.yadavmeasurements.com`
- **Expected Behavior:** Clean text sanitization with HTML entity unescaping (html.unescape) and regex stripping of replacement characters (\ufffd) and orphaned control bytes prior to entity and topic tokenization.
- **Recommended Future Direction:** Add an encoding normalization and string sanitization pre-processor to AsyncDeepCrawler and engine tokenizers.

#### `GAP-ENT-004`: Navigation Menus, Slogans, and Addresses Ingested as Entity Names
- **Category:** `SEMANTIC_INTERPRETATION` | **Severity:** `P1` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/entity_engine.py` | **Confidence:** `92%`
- **Observed Evidence:** On umspcs.in: 'Registration CDSCO Approvals ISO Certification Privacy Polic' extracted as entity name. On sqccertification.com: 'SQC Certification Provides Globally recognized ISO Certifications' extracted as entity name. On tcreng.com: 'Documents: Materials fail. Evidence doesn\'t.' extracted as entity name. On sunrisetesting.vercel.app: 'B-501, Harshit Jewels, Hirapur Road, Mohba Bazar, Raipur (C.' extracted as the LOCAL_BUSINESS entity name itself rather than as its postalAddress property.
- **Why Current Output is Insufficient:** Entity parsing lacks phrase boundary validation and structural container awareness. Concatenated navigation links, marketing slogans, and multiline address blocks are treated as singular named entities, producing severe noise.
- **Supporting Benchmark Sites:** `umspcs.in`, `sqccertification.com`, `www.tcreng.com`, `sunrisetesting.vercel.app`
- **Expected Behavior:** Strict length bounds, punctuation filters, and semantic phrase filters that reject concatenated menu items and separate address components from entity names.
- **Recommended Future Direction:** Implement entity boundary validation filters and structural context validation in entity_engine.py.

#### `GAP-INTENT-001`: Coarse Search Intent Classification Skewed Heavily Toward Transactional
- **Category:** `SEARCH_INTENT` | **Severity:** `P1` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/search_intent_engine.py` | **Confidence:** `90%`
- **Observed Evidence:** 7 out of 11 benchmark sites (ascgroup.in, qualityinternational.org, sqccertification.com, standphillindia.in, uniquemeasurement.com, yadavmeasurements.com, zaubacorp.com) are classified as dominant_intent: transactional. zaubacorp.com is a commercial company database/registry (informational/investigative lookup), yet classified as transactional. tcreng.com is classified as navigational solely due to brand term repetition.
- **Why Current Output is Insufficient:** The intent engine uses simple unweighted keyword frequency matchers. Generic commercial terms common to all business websites ('services', 'contact', 'enquiry', 'apply', 'quote') overwhelm informational and reference signals, conflating B2B service consultation with consumer e-commerce transactional intent.
- **Supporting Benchmark Sites:** `www.zaubacorp.com`, `www.tcreng.com`, `www.yadavmeasurements.com`, `sqccertification.com`, `www.uniquemeasurement.com`
- **Expected Behavior:** Hierarchical multi-class intent classification distinguishing B2B Service Lead-Generation from direct E-Commerce Cart/Checkout, Navigational Brand Search, and Informational Knowledge/Directory Lookup.
- **Recommended Future Direction:** Refactor search_intent_engine.py to use contextual intent scoring with distinct B2B Lead-Gen and Directory Lookup intent tiers.

#### `GAP-TOPIC-001`: Unigram Topic Fragmentation Lacking Multi-Word Technical Domain Keyphrases
- **Category:** `TOPIC_DIFFERENTIATION` | **Severity:** `P1` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/topic_engine.py` | **Confidence:** `94%`
- **Observed Evidence:** On sunrisetesting.vercel.app, topics sample consists of isolated unigrams: 'Calibration', 'Testing', 'Instruments', 'Sunrise', 'Inspection', 'Results', 'Services', 'Centre', 'Accurate', 'Precision'. On ascgroup.in: 'Advisory', 'Consulting', 'Taxation', 'ASC', 'Audit'. Across all sites, 100-227 flat unigrams are extracted without collocation or domain phrase structure.
- **Why Current Output is Insufficient:** Stopword-filtered unigram extraction produces generic tokens ('Results', 'Accurate', 'Precision', 'Services') that lack topical differentiation. Real search queries and AI retrieval match domain multi-word keyphrases (e.g. 'pressure calibration services', 'BIS FMCS certification', 'NABL accredited calibration').
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `www.ascgroup.in`, `www.tcreng.com`, `alephindia.in`, `sqccertification.com`
- **Expected Behavior:** N-gram collocation and noun-phrase keyphrase extraction (e.g. Rapid Automatic Keyword Extraction or C-value) yielding high-intent 2-4 word technical domain phrases.
- **Recommended Future Direction:** Upgrade topic_engine.py to extract multi-word technical keyphrases alongside ranked unigrams.

#### `GAP-TOPIC-002`: Single-Page Cannibalization Engine Execution Reporting False Clean Pass
- **Category:** `TOPIC_DIFFERENTIATION` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/cannibalization_engine.py` | **Confidence:** `93%`
- **Observed Evidence:** Across all 11 benchmark sites in benchmarks/packages/*.json, cannibalization_search_gaps records: potential_cannibalization_signals_count: 0, observable_gaps_count: 0, status: AVAILABLE.
- **Why Current Output is Insufficient:** Cannibalization is inherently a multi-page phenomenon requiring pairwise URL comparison across a domain. Executing the engine on a single URL and reporting status AVAILABLE with 0 signals creates a false impression of clean site-wide keyword hygiene, rather than acknowledging that cannibalization was unobservable.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `alephindia.in`, `www.tcreng.com`, `umspcs.in`
- **Expected Behavior:** The cannibalization engine should report status NOT_APPLICABLE or INSUFFICIENT_EVIDENCE when fewer than 2 URLs are evaluated, explicitly documenting that multi-page crawl evidence is required.
- **Recommended Future Direction:** Add page-count guardrails in cannibalization_engine.py to emit INSUFFICIENT_EVIDENCE on single-page runs.

#### `GAP-ANSWER-001`: Rigid Syntax Heuristics Missing Modern Web Card and List Answer Structures
- **Category:** `EXTRACTION_BLIND_SPOT` | **Severity:** `P1` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/answerability_engine.py` | **Confidence:** `92%`
- **Observed Evidence:** On sqccertification.com: 0 answer units detected (total_units_detected=0) across 963 words detailing ISO certification standards. On qualityinternational.org: 0 answer units detected across 578 words. On yadavmeasurements.com: Only 1 unit detected across 1059 words of technical testing descriptions.
- **Why Current Output is Insufficient:** The answerability engine relies on explicit question marks (?), <dl>/<dt> definition tags, or rigid regex triggers ('is defined as', 'steps to'). Modern industrial websites format services, capabilities, and procedural steps in CSS grid cards, icon feature blocks, or heading-paragraph pairs without question punctuation, resulting in false zero answerability.
- **Supporting Benchmark Sites:** `sqccertification.com`, `qualityinternational.org`, `www.yadavmeasurements.com`
- **Expected Behavior:** Structural DOM-layout recognition that identifies card grids, accordion modules, heading-paragraph semantic pairs, and process lists as observable answerability structures.
- **Recommended Future Direction:** Expand answerability_engine.py pattern matchers to recognize visual container blocks and card grids.

#### `GAP-GROUND-001`: Tautological On-Page Lexical Matching in Claim Grounding Verification
- **Category:** `ENTITY_CLAIM_GROUNDING` | **Severity:** `P1` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/claim_grounding_engine.py` | **Confidence:** `91%`
- **Observed Evidence:** On sunrisetesting.vercel.app: 16 out of 17 claims (94%) classified as SUPPORTED. On sqccertification.com: 21 out of 21 claims (100%) classified as SUPPORTED. On alephindia.in: 19 out of 20 claims (95%) classified as SUPPORTED.
- **Why Current Output is Insufficient:** Claims are extracted from the page text and then evaluated against that same page text via token matching. Because the source and verification target are identical, on-site grounding is almost universally 90-100%, creating a circular validation loop that verifies text self-consistency rather than factual grounding.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `sqccertification.com`, `alephindia.in`, `www.tcreng.com`, `www.standphillindia.in`
- **Expected Behavior:** Epistemic differentiation between internal text self-consistency, structured JSON-LD corroboration, and third-party/external authoritative reference corroboration.
- **Recommended Future Direction:** Restructure claim_grounding_engine.py to report separate scores for Internal Consistency, Structured Corroboration, and External Reference Grounding.

#### `GAP-RETRIEVAL-001`: Benchmark Collection Pipeline Bypassed Headless Browser JS DOM Rendering
- **Category:** `DETECTION_BLIND_SPOT` | **Severity:** `P0` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/benchmark/collector.py` | **Confidence:** `99%`
- **Observed Evidence:** Across all 11 benchmark sites in benchmarks/packages/*.json: static_words: 957, rendered_words: 0, word_count_delta: 0. rendering_impact_summary: 'Static HTML observed (957 words); browser DOM was not rendered in this pass.'
- **Why Current Output is Insufficient:** Headless browser DOM rendering was uncollected or bypassed in worker subprocesses during Phase 11.1 collection. As a result, RankIntel was completely blind to client-rendered JavaScript content, SPA frameworks, dynamically injected JSON-LD schema, and post-hydration layout shifts across the permanent benchmark cohort.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `alephindia.in`, `www.tcreng.com`, `www.ascgroup.in`, `umspcs.in`, `www.standphillindia.in`, `sqccertification.com`, `qualityinternational.org`, `www.uniquemeasurement.com`, `www.yadavmeasurements.com`, `www.zaubacorp.com`
- **Expected Behavior:** Subprocess benchmark workers that successfully execute headless browser DOM rendering (via crawl4ai/Playwright) alongside static fetching, capturing true rendered_words and computing meaningful word_count_delta.
- **Recommended Future Direction:** Harden collector.py worker process lifecycle to ensure headless browser DOM capture is reliably executed for all benchmark sites.

#### `GAP-RETRIEVAL-002`: Passive Cloudflare Reverse Proxy Headers Conflated with Active Access Blocking
- **Category:** `AI_GEO_INTERPRETATION` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/retrieval_readiness_engine.py` | **Confidence:** `89%`
- **Observed Evidence:** 5 sites (alephindia.in, sqccertification.com, tcreng.com, yadavmeasurements.com, zaubacorp.com) were flagged with waf_or_challenge_detected: True or marked with WAF barriers in reports, even though all 5 returned full HTTP 200 OK responses with complete HTML content.
- **Why Current Output is Insufficient:** Presence of standard CDN response headers (cf-ray, server: cloudflare) is conflated with active bot-blocking interstitials (Cloudflare Turnstile, 403 Forbidden, 503 challenge). This causes clean sites behind CDNs to be reported as blocked or challenged for AI search agents.
- **Supporting Benchmark Sites:** `www.tcreng.com`, `sqccertification.com`, `alephindia.in`, `www.yadavmeasurements.com`, `www.zaubacorp.com`
- **Expected Behavior:** Tri-state WAF taxonomy: PASSIVE_CDN_PRESENT (200 OK with CDN headers), CHALLENGE_INTERSTITIAL_ACTIVE (200/503 with JS challenge DOM), and ACCESS_BLOCKED (403/429 status code).
- **Recommended Future Direction:** Update retrieval_readiness_engine.py to distinguish passive CDN presence from active challenge interstitials and hard blocks.

#### `GAP-MM-001`: Images Missing Alt Attributes Heuristically Defaulted to Decorative
- **Category:** `MULTIMODAL_AGENT` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/multimodal_agent_engine.py` | **Confidence:** `88%`
- **Observed Evidence:** On sunrisetesting.vercel.app: 34 images detected, 3 marked informational, 31 marked decorative_assets_count. On umspcs.in: 211 images marked decorative. On qualityinternational.org: 7 images marked decorative.
- **Why Current Output is Insufficient:** When an image lacks an alt attribute and does not meet specific size or semantic container rules, the heuristic defaults it to 'decorative'. This masks critical accessibility and SEO failures where substantive diagrams, facility photos, or accreditation logos are unindexed because they lack alt metadata.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `umspcs.in`, `qualityinternational.org`
- **Expected Behavior:** Explicit classification: distinguish between confirmed decorative (aria-hidden='true', role='presentation', CSS background) versus un-annotated image with unknown semantic role (UNLABELED_UNKNOWN).
- **Recommended Future Direction:** Adopt an UNLABELED_UNKNOWN state in multimodal_agent_engine.py instead of defaulting un-alt'd images to decorative.

#### `GAP-MM-002`: Absence of Visual OCR for Text Embedded in Lab Certificates & Technical Charts
- **Category:** `EXTRACTION_BLIND_SPOT` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/engines/multimodal_agent_engine.py` | **Confidence:** `93%`
- **Observed Evidence:** Technical testing sites (sunrisetesting.vercel.app, tcreng.com, standphillindia.in) embed NABL accreditation certificates, ISO scopes of accreditation, and calibration capability charts directly as JPG/PNG raster images. RankIntel extracts 0 text, 0 entities, and 0 claims from these visual assets.
- **Why Current Output is Insufficient:** Core domain credentials, scope ranges, and regulatory compliance evidence locked in raster images are completely invisible to RankIntel, leading the engine to underestimate the site's factual authority and expertise.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `www.standphillindia.in`, `www.tcreng.com`
- **Expected Behavior:** Optional OCR or vision pipeline extracting visible text, accreditation numbers, and calibration scopes from high-resolution images.
- **Recommended Future Direction:** Plan an offline OCR / document intelligence pipeline in Phase 12 for certificate and diagram analysis.

#### `GAP-AGENT-001`: Interactive Action Buttons and Web Forms Conflated Under 'Forms' Column
- **Category:** `SEMANTIC_INTERPRETATION` | **Severity:** `P1` | **Classification:** `REPORTING_DEFECT`
- **Affected Engine:** `src/rankintel/reporters/comparison_reporter.py` | **Confidence:** `97%`
- **Observed Evidence:** In benchmarks/comparisons/benchmark_comparison_phase11.md Table 2, column header 'Forms' displayed: alephindia.in: 87 (actual: 3 forms, 84 buttons); standphillindia.in: 37 (actual: 6 forms, 31 buttons); zaubacorp.com: 32 (actual: 1 form, 31 buttons); umspcs.in: 24 (actual: 8 forms, 16 buttons).
- **Why Current Output is Insufficient:** comparator.py populated action_surfaces_count (forms + buttons) into the matrix, but comparison_reporter.py labeled the column 'Forms'. Users and automated parsers conclude the site has 87 full HTML web forms, which is factually false.
- **Supporting Benchmark Sites:** `alephindia.in`, `www.standphillindia.in`, `www.zaubacorp.com`, `umspcs.in`
- **Expected Behavior:** Clear reporting separation: label the combined column 'Action Surfaces (Forms + Buttons)' or present separate columns for 'Forms' and 'Buttons'.
- **Recommended Future Direction:** Update comparison_reporter.py table rendering to split Forms and Buttons into separate columns.

#### `GAP-COMP-001`: Static Hardcoded Void Rules Failing to Discover Open-Domain Competitor Capabilities
- **Category:** `CROSS_SITE_COMPARISON` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/benchmark/comparator.py` | **Confidence:** `88%`
- **Observed Evidence:** The 12 observable voids in Phase 11.3 are restricted to fixed hardcoded IDs (VOID-SCHEMA-001, VOID-A11Y-001, VOID-AGENT-001, VOID-ANSWER-001, VOID-SEC-001, VOID-TOPIC-001, VOID-GEO-001, etc.). Unique competitor features (e.g. online certificate verification lookup, customer sample status portals, dynamic quotation calculators) are never identified as voids.
- **Why Current Output is Insufficient:** Void discovery is bounded by static heuristic templates. Competitor innovations outside the pre-programmed rules remain entirely unextracted.
- **Supporting Benchmark Sites:** `www.tcreng.com`, `alephindia.in`, `www.zaubacorp.com`, `umspcs.in`
- **Expected Behavior:** Dynamic cluster-based void discovery comparing structural feature vectors, interactive element roles, and semantic service taxonomies across competitors without fixed rule templates.
- **Recommended Future Direction:** Develop dynamic cross-site void discovery algorithms in Phase 11.5 / Phase 12.

#### `GAP-REC-001`: Generic SEO Recommendation Templates Disconnected from B2B Industrial Context
- **Category:** `RECOMMENDATION_QUALITY` | **Severity:** `P2` | **Classification:** `TRUE_CAPABILITY_GAP`
- **Affected Engine:** `src/rankintel/synthesis` | **Confidence:** `90%`
- **Observed Evidence:** Recommendations across all benchmark sites repetitively suggest: 'Optimize Title Tag Length & CTR Hook (50-60 chars)', 'Rewrite Meta Description with Active Call-to-Action', 'Publish Standard /llms.txt AI Agent Manifest', 'Deploy JSON-LD Structured Data'.
- **Why Current Output is Insufficient:** For a B2B testing/calibration laboratory, title tag length truncation is a minor cosmetic concern compared to missing NABL accreditation numbers, absent ISO/IEC 17025 schema, or missing calibration parameter tables. The recommendations lack industry-specific impact weighting and business relevance.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `www.yadavmeasurements.com`, `www.uniquemeasurement.com`, `qualityinternational.org`
- **Expected Behavior:** Domain-contextual recommendation prioritization where high-value industrial trust and technical capability remediations outrank generic cosmetic character count optimizations.
- **Recommended Future Direction:** Implement industry-specific recommendation prioritization heuristics in synthesis engine.

#### `LIM-EVID-001`: Single-Landing-Page Crawl Scope Extrapolated to Whole-Site Assessment
- **Category:** `EVIDENCE_PROVENANCE` | **Severity:** `P1` | **Classification:** `EVIDENCE_LIMITATION`
- **Affected Engine:** `src/rankintel/benchmark/collector.py` | **Confidence:** `96%`
- **Observed Evidence:** The permanent 11-site benchmark collection evaluated only the root homepage (/) for each domain. Internal link architecture depth (>1 click), sitewide orphan pages, internal PageRank flow, and deep service specifications residing on subpages (/services, /calibration) were entirely uncollected.
- **Why Current Output is Insufficient:** Assessing a multi-department industrial company (like Yadav Measurements or TCR Engineering) solely on its homepage produces an incomplete and artificially depressed representation of its true content depth and technical authority.
- **Supporting Benchmark Sites:** `www.yadavmeasurements.com`, `www.tcreng.com`, `www.ascgroup.in`, `alephindia.in`
- **Expected Behavior:** Multi-page crawl capability (e.g. 5-15 key pages per site) for benchmark collection, or explicit whole-site uncertainty caveats attached to all single-page audit outputs.
- **Recommended Future Direction:** Support configurable multi-page depth sampling in collector.py for future benchmark phases.

#### `LIM-EVID-002`: External AI Visibility Measurement Disabled by Design in Benchmark Pass
- **Category:** `EVIDENCE_PROVENANCE` | **Severity:** `P2` | **Classification:** `EVIDENCE_LIMITATION`
- **Affected Engine:** `src/rankintel/engines/external_visibility_engine.py` | **Confidence:** `99%`
- **Observed Evidence:** Across all 11 benchmark sites in Phase 11.1, external_ai recorded status: DISABLED with 0 queries executed and 0 citations observed.
- **Why Current Output is Insufficient:** External AI measurement is strictly opt-in via --external-ai to prevent uncontrolled API quota consumption and network flakiness. Consequently, live LLM citability and grounded answer citations across the 11 sites were unobserved.
- **Supporting Benchmark Sites:** `sunrisetesting.vercel.app`, `alephindia.in`, `www.tcreng.com`
- **Expected Behavior:** Controlled opt-in benchmark runs with deterministic mock providers or cached external responses to enable reproducible comparative AI citability benchmarking.
- **Recommended Future Direction:** Introduce cached or mocked external AI evaluation mode for offline benchmark comparisons.

## 4. False-Gap Exclusions (Genuine Website Deficiencies)

The following candidate gaps were investigated during the forensic review and confirmed to be **genuine website deficiencies** rather than RankIntel engine defects. RankIntel's reporting is factually accurate and preserved.

| Exclusion ID | Candidate Finding | Website Reality | Classification |
| :--- | :--- | :--- | :---: |
| `EXCL-WEBSITE-001` | RankIntel reports /llms.txt missing on all 11 benchmark sites | The websites genuinely do not publish an /llms.txt file (all return HTTP 404). RankIntel's... | `WEBSITE_DEFICIENCY` |
| `EXCL-WEBSITE-002` | RankIntel reports 0 Schema.org types on 6 benchmark sites | The source HTML of these 6 sites genuinely contains zero <script type='application/ld+json... | `WEBSITE_DEFICIENCY` |
| `EXCL-WEBSITE-003` | RankIntel reports 0.0% image alt-text coverage on target site sunrisetesting.vercel.app | The target landing page HTML genuinely contains 34 <img> elements that have either no alt ... | `WEBSITE_DEFICIENCY` |
| `EXCL-WEBSITE-004` | RankIntel flags missing Content-Security-Policy (CSP) headers on 6 sites | The web servers for these domains genuinely omit the Content-Security-Policy header from t... | `WEBSITE_DEFICIENCY` |
| `EXCL-WEBSITE-005` | RankIntel reports 0 interactive web forms on target site | The landing page DOM genuinely contains zero <form> elements, relying exclusively on tel: ... | `WEBSITE_DEFICIENCY` |

#### `EXCL-WEBSITE-001`: RankIntel reports /llms.txt missing on all 11 benchmark sites
- **Observed Evidence:** retrieval_readiness.llms_txt_present is False across all 11 benchmark sites.
- **Why Not an Engine Defect:** The websites genuinely do not publish an /llms.txt file (all return HTTP 404). RankIntel's retrieval_readiness_engine correctly probed the RFC path and accurately recorded its absence. The finding is a genuine website deficiency, not an engine flaw.
- **Affected Sites:** `sunrisetesting.vercel.app`, `alephindia.in`, `www.tcreng.com`, `www.ascgroup.in`, `umspcs.in`, `www.standphillindia.in`, `sqccertification.com`, `qualityinternational.org`, `www.uniquemeasurement.com`, `www.yadavmeasurements.com`, `www.zaubacorp.com`

#### `EXCL-WEBSITE-002`: RankIntel reports 0 Schema.org types on 6 benchmark sites
- **Observed Evidence:** technical_seo.detected_schema_types is [] on sunrisetesting.vercel.app, qualityinternational.org, uniquemeasurement.com, yadavmeasurements.com, zaubacorp.com, and ascgroup.in (partial).
- **Why Not an Engine Defect:** The source HTML of these 6 sites genuinely contains zero <script type='application/ld+json'> blocks or microdata. RankIntel's parser accurately inspected the DOM and factually reported 0 schema types. This is a website deficiency.
- **Affected Sites:** `sunrisetesting.vercel.app`, `qualityinternational.org`, `www.uniquemeasurement.com`, `www.yadavmeasurements.com`, `www.zaubacorp.com`

#### `EXCL-WEBSITE-003`: RankIntel reports 0.0% image alt-text coverage on target site sunrisetesting.vercel.app
- **Observed Evidence:** multimodal.alt_coverage_ratio is 0.0 across 34 visual assets.
- **Why Not an Engine Defect:** The target landing page HTML genuinely contains 34 <img> elements that have either no alt attribute or empty alt=''. RankIntel's multimodal_agent_engine faithfully recorded 0% coverage. This is a website deficiency.
- **Affected Sites:** `sunrisetesting.vercel.app`

#### `EXCL-WEBSITE-004`: RankIntel flags missing Content-Security-Policy (CSP) headers on 6 sites
- **Observed Evidence:** security.csp_present is False on 6 benchmark sites.
- **Why Not an Engine Defect:** The web servers for these domains genuinely omit the Content-Security-Policy header from their HTTP responses. RankIntel's passive security observation is factually correct. This is a technical website deficiency.
- **Affected Sites:** `sunrisetesting.vercel.app`, `alephindia.in`, `www.standphillindia.in`, `qualityinternational.org`, `www.uniquemeasurement.com`, `www.yadavmeasurements.com`

#### `EXCL-WEBSITE-005`: RankIntel reports 0 interactive web forms on target site
- **Observed Evidence:** agent_readiness.total_forms_detected is 0 on sunrisetesting.vercel.app.
- **Why Not an Engine Defect:** The landing page DOM genuinely contains zero <form> elements, relying exclusively on tel: and mailto: anchor links. The engine reported 0 forms accurately. This is a website structural design choice / deficiency, not an engine defect.
- **Affected Sites:** `sunrisetesting.vercel.app`

## 5. Architectural Recommendations & Roadmap for Phase 11.5

- 1. Implement Deterministic Brand Organization Entity Fallback (GAP-ENT-002, P0): Guarantee primary brand entity extraction from title/H1/og:site_name when Schema.org JSON-LD is absent.
- 2. Harden Benchmark Headless Browser DOM Execution (GAP-RETRIEVAL-001, P0): Ensure worker subprocesses in collector.py reliably capture post-JS DOM and word counts.
- 3. Implement Multi-Surface Entity Deduplication & Resolution (GAP-ENT-001, P1): Cluster raw DOM mentions by canonical key to prevent duplicate count inflation.
- 4. Refine Search Intent Engine for B2B Service Inquiry vs E-Commerce (GAP-INTENT-001, P1): Distinguish commercial lead-gen inquiries from consumer shopping cart transactional intent.
- 5. Upgrade Topic Engine to Extract Multi-Word Domain Keyphrases (GAP-TOPIC-001, P1): Move beyond stopword-filtered unigrams to extract 2-4 word technical domain phrases.
- 6. DOM-Layout Aware Answerability Pattern Recognition (GAP-ANSWER-001, P1): Recognize card grids, accordions, and heading-paragraph pairs as answer structures.
- 7. Decouple On-Page Self-Consistency from External Claim Grounding (GAP-GROUND-001, P1): Separate circular DOM token matching from structured and reference corroboration.
- 8. Split Action Surfaces Column into Forms and Buttons (GAP-AGENT-001, P1): Fix reporting conflation in comparison_reporter.py.
- 9. Tri-State WAF Classification (GAP-RETRIEVAL-002, P2): Separate passive Cloudflare CDN reverse proxy presence from active challenge interstitials.
- 10. Distinguish Unlabeled Images from Confirmed Decorative Assets (GAP-MM-001, P2): Replace default-decorative with UNLABELED_UNKNOWN state.

## 6. Epistemic Boundaries & Provenance Verification

### Facts (Observable Benchmark Artifacts)
- Permanent 11-site benchmark populated with 11 normalized SiteIntelligencePackages.
- Zero headless browser DOM words captured across all 11 benchmark packages (rendered_words=0).
- 0 entities detected on yadavmeasurements.com; 0 organization entities on qualityinternational.org and uniquemeasurement.com.
- 4 duplicate instances of 'Aleph INDIA' and 4 of 'Standphill India' present in entity extraction arrays.
- 7 of 11 sites classified as dominant_intent: transactional.
- Comparison summary table reported 87 forms for alephindia.in by summing 3 forms + 84 buttons.
- All 11 benchmark sites return HTTP 404 for /llms.txt.
- 6 benchmark sites have 0 declared JSON-LD schema blocks.

### Analyses (RankIntel Gap Deductions)
- Identified 14 true capability gaps and reporting defects across entity, topic, intent, answerability, grounding, retrieval, multimodal, and comparator engines.
- Identified 3 evidence limitations stemming from single-landing-page crawl scope and disabled external AI.
- Verified 5 false-gap exclusions representing factual website deficiencies rather than engine bugs.
- RankIntel health score formulas remain strictly invariant (Δ=0).

### Formula Invariance Verification
$$\Delta_{\text{overall}} = 0, \quad \Delta_{\text{technical}} = 0, \quad \Delta_{\text{geo}} = 0$$
Formula invariance bit-identical across all 11 benchmark sites: `True`.
