"""
Deterministic unit and integration tests for RankIntel Milestone M6.4:
Internal Link Graph & Equity Intelligence Engine.
Offline execution — zero live HTTP requests.
"""
import pytest
import networkx as nx

from rankintel.models.schema import (
    CrawlStatus,
    CrawlRecord,
    SiteCrawlResult,
    LinkClassification,
    NodeOrphanStatus,
    NodeCrawlState,
    ReachabilityInGraph,
    LinkGraphNode,
    InternalLinkGraphSummary,
    SynthesisReport,
    OnPageEvidence,
    RobotsEvidence,
    SchemaEvidence,
    GeoAeoEvidence,
    TrustStackResult,
    PerformanceEvidence,
)
from rankintel.crawler.normalizer import UrlNormalizer
from rankintel.analyzers.record_lookup import RecordLookupIndex
from rankintel.analyzers.link_graph_engine import InternalLinkGraphEngine
from rankintel.reporters.markdown import MarkdownReporter


# ---------------------------------------------------------------------------
# Helpers for synthetic record generation
# ---------------------------------------------------------------------------

def make_record(
    url: str,
    status_code: int = 200,
    crawl_status: CrawlStatus = CrawlStatus.FETCHED,
    discovered_links: list = None,
    depth: int = 1,
    discovery_source: str = "internal_link",
) -> CrawlRecord:
    clean_url = url.strip()
    return CrawlRecord(
        url=clean_url,
        normalized_url=UrlNormalizer.normalize_for_crawl(clean_url),
        identity_url=UrlNormalizer.get_url_identity(clean_url),
        crawl_status=crawl_status,
        depth=depth,
        status_code=status_code,
        discovery_source=discovery_source,
        discovered_links=discovered_links or [],
    )


# ===========================================================================
# 1. LINK CLASSIFICATION TESTS
# ===========================================================================

def test_classify_internal_links():
    base = "https://example.com"
    # Root relative
    assert InternalLinkGraphEngine.classify_link("/about", base) == LinkClassification.INTERNAL
    # Full same domain
    assert InternalLinkGraphEngine.classify_link("https://example.com/about", base) == LinkClassification.INTERNAL
    # With query parameter
    assert InternalLinkGraphEngine.classify_link("https://example.com/item?id=42", base) == LinkClassification.INTERNAL
    # Default port
    assert InternalLinkGraphEngine.classify_link("https://example.com:443/contact", base) == LinkClassification.INTERNAL


def test_classify_external_links():
    base = "https://example.com"
    assert InternalLinkGraphEngine.classify_link("https://google.com", base) == LinkClassification.EXTERNAL
    assert InternalLinkGraphEngine.classify_link("https://competitor.com/blog", base) == LinkClassification.EXTERNAL
    assert InternalLinkGraphEngine.classify_link("http://other.org", base) == LinkClassification.EXTERNAL


def test_classify_special_schemes():
    base = "https://example.com"
    assert InternalLinkGraphEngine.classify_link("mailto:support@example.com", base) == LinkClassification.SPECIAL
    assert InternalLinkGraphEngine.classify_link("tel:+1234567890", base) == LinkClassification.SPECIAL
    assert InternalLinkGraphEngine.classify_link("javascript:void(0);", base) == LinkClassification.SPECIAL
    assert InternalLinkGraphEngine.classify_link("data:text/plain;base64,SGVsbG8=", base) == LinkClassification.SPECIAL
    assert InternalLinkGraphEngine.classify_link("#anchor", base) == LinkClassification.SPECIAL
    assert InternalLinkGraphEngine.classify_link("", base) == LinkClassification.SPECIAL


# ===========================================================================
# 2. URL NORMALIZATION & CONTENT PARAMETER PRESERVATION
# ===========================================================================

def test_url_normalization_preserves_content_params():
    """Content-defining query parameters like ?id=1 vs ?id=2 must remain distinct nodes."""
    u1 = "https://example.com/product?id=1"
    u2 = "https://example.com/product?id=2"

    n1 = InternalLinkGraphEngine.normalize_node_url(u1)
    n2 = InternalLinkGraphEngine.normalize_node_url(u2)

    assert n1 != n2
    assert "id=1" in n1
    assert "id=2" in n2


def test_url_normalization_strips_tracking_and_fragments():
    """Marketing tracking parameters and fragments must be stripped."""
    u = "https://example.com/about/?utm_source=twitter&utm_medium=social#team"
    norm = InternalLinkGraphEngine.normalize_node_url(u)
    assert norm == "https://example.com/about"
    assert "utm_source" not in norm
    assert "#team" not in norm


def test_url_normalization_with_record_lookup_alignment():
    """When a RecordLookupIndex is provided, normalize_node_url aligns with the record's identity."""
    rec = make_record("https://example.com/services/?sort=name&category=tools")
    lookup = RecordLookupIndex([rec])

    # Incoming link with unsorted query params and trailing slash
    link = "https://example.com/services?category=tools&sort=name"
    norm = InternalLinkGraphEngine.normalize_node_url(link, lookup_index=lookup)
    assert norm == rec.identity_url


# ===========================================================================
# 3. GRAPH CONSTRUCTION & TOPOLOGY TESTS
# ===========================================================================

def test_graph_construction_basic():
    """Test directed graph construction with root, children, and discovered uncrawled pages."""
    rec_home = make_record("https://example.com/", depth=0, discovered_links=[
        "/about",
        "/services",
        "https://external.com/partner",
        "mailto:info@example.com",
    ])
    rec_about = make_record("https://example.com/about", depth=1, discovered_links=[
        "/services",
        "/team",
    ])
    rec_services = make_record("https://example.com/services", depth=1, discovered_links=[
        "/",
    ])

    site_crawl = SiteCrawlResult(
        pages_crawled=3,
        crawl_records=[rec_home, rec_about, rec_services],
    )

    G, root, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    assert root == "https://example.com/"
    # Nodes: home, about, services (crawled), team (discovered uncrawled)
    assert G.number_of_nodes() == 4
    assert summary.crawled_nodes_count == 3
    assert summary.discovered_uncrawled_count == 1
    assert summary.nodes["https://example.com/team"].crawl_state == NodeCrawlState.DISCOVERED_UNCRAWLED
    assert summary.total_external_links_found == 1


def test_self_links_handling():
    """Self-links must be tracked in self_links_count and not counted as separate inbound pages."""
    rec_home = make_record("https://example.com/", depth=0, discovered_links=[
        "/",                   # Self-link
        "https://example.com/#top",  # Self-link with fragment
        "/about",
    ])
    rec_about = make_record("https://example.com/about", depth=1, discovered_links=[
        "/about",              # Self-link on about
    ])

    site_crawl = SiteCrawlResult(crawl_records=[rec_home, rec_about])
    G, root, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    home_node = summary.nodes["https://example.com/"]
    about_node = summary.nodes["https://example.com/about"]

    assert home_node.self_links_count == 2
    assert about_node.self_links_count == 1
    # home has 0 other pages linking to it
    assert home_node.inbound_internal_count == 0
    # about has home linking to it (excluding self-link)
    assert about_node.inbound_internal_count == 1


def test_duplicate_links_weighting():
    """
    Multiple links between page A and page B increase edge weight and total links,
    while unique inbound/outbound counts remain 1.
    """
    rec_home = make_record("https://example.com/", depth=0, discovered_links=[
        "/about",  # link 1 in nav
        "/about",  # link 2 in body
        "/about",  # link 3 in footer
    ])
    rec_about = make_record("https://example.com/about", depth=1, discovered_links=[])

    site_crawl = SiteCrawlResult(crawl_records=[rec_home, rec_about])
    G, root, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    home_node = summary.nodes["https://example.com/"]
    about_node = summary.nodes["https://example.com/about"]

    # Edge weight in DiGraph
    assert G["https://example.com/"]["https://example.com/about"]["weight"] == 3

    # Counts
    assert home_node.outbound_internal_count == 1
    assert home_node.total_outbound_links == 3
    assert about_node.inbound_internal_count == 1
    assert about_node.total_inbound_links == 3


# ===========================================================================
# 4. CLICK DEPTH TESTS
# ===========================================================================

def test_click_depth_calculation():
    """Verify shortest path click depth from root (0, 1, 2, 3, 4) and deep pages (>3)."""
    rec_root = make_record("https://example.com/", depth=0, discovered_links=["/level1"])
    rec_l1 = make_record("https://example.com/level1", depth=1, discovered_links=["/level2"])
    rec_l2 = make_record("https://example.com/level2", depth=2, discovered_links=["/level3"])
    rec_l3 = make_record("https://example.com/level3", depth=3, discovered_links=["/level4"])
    rec_l4 = make_record("https://example.com/level4", depth=4, discovered_links=[])

    site_crawl = SiteCrawlResult(crawl_records=[rec_root, rec_l1, rec_l2, rec_l3, rec_l4])
    _, _, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    assert summary.nodes["https://example.com/"].click_depth == 0
    assert summary.nodes["https://example.com/level1"].click_depth == 1
    assert summary.nodes["https://example.com/level2"].click_depth == 2
    assert summary.nodes["https://example.com/level3"].click_depth == 3
    assert summary.nodes["https://example.com/level4"].click_depth == 4

    assert summary.max_click_depth == 4
    assert summary.deep_pages_count == 1
    assert "https://example.com/level4" in summary.deep_pages


def test_click_depth_shortcuts():
    """A direct link from root to a deep page must give it shortest-path click depth = 1."""
    rec_root = make_record("https://example.com/", depth=0, discovered_links=["/level1", "/deep"])
    rec_l1 = make_record("https://example.com/level1", depth=1, discovered_links=["/level2"])
    rec_l2 = make_record("https://example.com/level2", depth=2, discovered_links=["/deep"])
    rec_deep = make_record("https://example.com/deep", depth=3, discovered_links=[])

    site_crawl = SiteCrawlResult(crawl_records=[rec_root, rec_l1, rec_l2, rec_deep])
    _, _, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    assert summary.nodes["https://example.com/deep"].click_depth == 1


# ===========================================================================
# 5. DISCONNECTED COMPONENTS & REACHABILITY VS ORPHANS
# ===========================================================================

def test_disconnected_subgraphs_reachability_vs_orphans():
    """
    CRITICAL USER CORRECTION TEST:
    Separate signals:
    - Potential orphan = crawled page + zero observed internal inbound links
    - Unreachable in observed graph = no observed path from root
    A disconnected page (C) with an inbound link from another disconnected page (B)
    is UNREACHABLE_IN_OBSERVED_GRAPH, but NOT a POTENTIAL_ORPHAN!
    """
    # Component 1 (connected to root): Root -> A
    rec_root = make_record("https://example.com/", depth=0, discovered_links=["/page-a"])
    rec_a = make_record("https://example.com/page-a", depth=1, discovered_links=[])

    # Component 2 (disconnected): Page B -> Page C
    # Page B has no inbound links.
    # Page C has an inbound link from Page B.
    rec_b = make_record("https://example.com/page-b", depth=99, discovered_links=["/page-c"])
    rec_c = make_record("https://example.com/page-c", depth=99, discovered_links=[])

    site_crawl = SiteCrawlResult(crawl_records=[rec_root, rec_a, rec_b, rec_c])
    _, _, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    assert summary.weakly_connected_components == 2

    node_b = summary.nodes["https://example.com/page-b"]
    node_c = summary.nodes["https://example.com/page-c"]

    # Both are unreachable from root in the observed graph
    assert node_b.click_depth is None
    assert node_b.reachability == ReachabilityInGraph.UNREACHABLE_IN_OBSERVED_GRAPH
    assert node_c.click_depth is None
    assert node_c.reachability == ReachabilityInGraph.UNREACHABLE_IN_OBSERVED_GRAPH

    # BUT: Page B has 0 inbound links -> POTENTIAL_ORPHAN
    assert node_b.inbound_internal_count == 0
    assert node_b.orphan_status == NodeOrphanStatus.POTENTIAL_ORPHAN

    # AND: Page C has 1 inbound link (from B) -> NOT A POTENTIAL ORPHAN!
    assert node_c.inbound_internal_count == 1
    assert node_c.orphan_status == NodeOrphanStatus.CONNECTED

    # Verify summary lists
    assert "https://example.com/page-b" in summary.potential_orphans
    assert "https://example.com/page-c" not in summary.potential_orphans
    assert "https://example.com/page-b" in summary.unreachable_in_observed_graph
    assert "https://example.com/page-c" in summary.unreachable_in_observed_graph


def test_root_is_never_an_orphan():
    """The crawl root URL must never be classified as an orphan even with in-degree = 0."""
    rec_root = make_record("https://example.com/", depth=0, discovered_links=["/about"])
    rec_about = make_record("https://example.com/about", depth=1, discovered_links=[])

    site_crawl = SiteCrawlResult(crawl_records=[rec_root, rec_about])
    _, _, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    root_node = summary.nodes["https://example.com/"]
    assert root_node.inbound_internal_count == 0
    assert root_node.orphan_status == NodeOrphanStatus.ROOT
    assert "https://example.com/" not in summary.potential_orphans


# ===========================================================================
# 6. INTERNAL PAGERANK / EQUITY CALCULATION
# ===========================================================================

def test_pagerank_deterministic_sum_and_weights():
    """
    Verify PageRank scores are mathematically valid, sum approximately to 1.0,
    and repeated links between source and target contribute proportionally.
    """
    # Symmetric 3-node cycle: A -> B -> C -> A
    rec_a = make_record("https://example.com/a", depth=0, discovered_links=["/b"])
    rec_b = make_record("https://example.com/b", depth=1, discovered_links=["/c"])
    rec_c = make_record("https://example.com/c", depth=1, discovered_links=["/a"])

    site_crawl = SiteCrawlResult(crawl_records=[rec_a, rec_b, rec_c])
    _, _, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    scores = [n.internal_equity_score for n in summary.nodes.values()]
    # Sum must be approximately 1.0
    assert sum(scores) == pytest.approx(1.0, abs=0.01)

    # In a symmetric 3-cycle, all three nodes must receive equal equity (~0.333333)
    for score in scores:
        assert score == pytest.approx(1.0 / 3.0, abs=0.01)


def test_pagerank_weighted_repeated_links():
    """Repeated links increase edge weight and influence equity proportionally."""
    # Node A links to Node B once, but to Node C 9 times
    # Node B links to A, Node C links to A
    rec_a = make_record("https://example.com/a", depth=0, discovered_links=[
        "/b",
        "/c", "/c", "/c", "/c", "/c", "/c", "/c", "/c", "/c"
    ])
    rec_b = make_record("https://example.com/b", depth=1, discovered_links=["/a"])
    rec_c = make_record("https://example.com/c", depth=1, discovered_links=["/a"])

    site_crawl = SiteCrawlResult(crawl_records=[rec_a, rec_b, rec_c])
    _, _, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    score_b = summary.nodes["https://example.com/b"].internal_equity_score
    score_c = summary.nodes["https://example.com/c"].internal_equity_score

    # Node C received 90% of A's outbound weight, so C must have higher equity than B
    assert score_c > score_b


def test_pagerank_self_loops_do_not_inflate_equity():
    """Adding self-links to a page must not inflate its internal PageRank."""
    # Graph 1 without self-loop
    rec_a1 = make_record("https://example.com/a", depth=0, discovered_links=["/b"])
    rec_b1 = make_record("https://example.com/b", depth=1, discovered_links=["/a"])
    site1 = SiteCrawlResult(crawl_records=[rec_a1, rec_b1])
    _, _, summary1 = InternalLinkGraphEngine.build_graph(site1)

    # Graph 2 with 10 self-loops on B
    rec_a2 = make_record("https://example.com/a", depth=0, discovered_links=["/b"])
    rec_b2 = make_record("https://example.com/b", depth=1, discovered_links=["/a"] + ["/b"] * 10)
    site2 = SiteCrawlResult(crawl_records=[rec_a2, rec_b2])
    _, _, summary2 = InternalLinkGraphEngine.build_graph(site2)

    score_b1 = summary1.nodes["https://example.com/b"].internal_equity_score
    score_b2 = summary2.nodes["https://example.com/b"].internal_equity_score

    # Because self-loops are filtered from PageRank copy, scores must match
    assert score_b1 == pytest.approx(score_b2, abs=0.001)


# ===========================================================================
# 7. EMPTY AND SMALL GRAPHS
# ===========================================================================

def test_empty_records_graph():
    """Empty crawl records must return empty summary without error."""
    site_crawl = SiteCrawlResult(crawl_records=[])
    G, root, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    assert G.number_of_nodes() == 0
    assert summary.total_nodes == 0
    assert summary.crawled_nodes_count == 0
    assert summary.potential_orphan_count == 0


def test_single_node_graph():
    """Single node graph has equity 1.0, depth 0, and 0 potential orphans."""
    rec = make_record("https://example.com/", depth=0, discovered_links=[])
    site_crawl = SiteCrawlResult(crawl_records=[rec])
    G, root, summary = InternalLinkGraphEngine.build_graph(site_crawl)

    assert summary.total_nodes == 1
    assert summary.nodes["https://example.com/"].internal_equity_score == 1.0
    assert summary.nodes["https://example.com/"].click_depth == 0
    assert summary.potential_orphan_count == 0


# ===========================================================================
# 8. SITE INTEGRATION & JSON SERIALIZATION
# ===========================================================================

def test_analyze_site_integration_and_serialization():
    """Verify analyze_site attaches link_graph, updates orphan_pages, and serializes roundtrip."""
    rec_home = make_record("https://example.com/", depth=0, discovered_links=["/about", "/contact"])
    rec_about = make_record("https://example.com/about", depth=1, discovered_links=[])
    rec_orphan = make_record("https://example.com/orphan", depth=99, discovered_links=[])

    site_crawl = SiteCrawlResult(
        pages_crawled=3,
        crawl_records=[rec_home, rec_about, rec_orphan],
    )

    analyzed = InternalLinkGraphEngine.analyze_site(site_crawl)
    assert analyzed.link_graph is not None
    assert analyzed.orphan_pages == ["https://example.com/orphan"]
    assert any("potential orphan" in issue for issue in analyzed.site_wide_issues)

    # JSON roundtrip serialization
    json_str = analyzed.model_dump_json()
    assert "link_graph" in json_str
    assert "internal_equity_score" in json_str

    deserialized = SiteCrawlResult.model_validate_json(json_str)
    assert deserialized.link_graph is not None
    assert deserialized.link_graph.total_nodes == 4  # home, about, orphan (crawled), contact (discovered)
    assert deserialized.link_graph.potential_orphan_count == 1
    assert deserialized.orphan_pages == ["https://example.com/orphan"]


# ===========================================================================
# 9. MARKDOWN REPORTING TESTS
# ===========================================================================

def test_markdown_report_renders_link_graph():
    """Markdown reporter renders internal link graph with proper terminology and without vanity scores."""
    rec_home = make_record("https://example.com/", depth=0, discovered_links=["/about"])
    rec_about = make_record("https://example.com/about", depth=1, discovered_links=[])

    site_crawl = SiteCrawlResult(
        pages_crawled=2,
        crawl_records=[rec_home, rec_about],
    )
    site_crawl = InternalLinkGraphEngine.analyze_site(site_crawl)

    report = SynthesisReport(
        url="https://example.com",
        domain="example.com",
        timestamp="2026-10-02",
        overall_health_score=85,
        site_crawl=site_crawl,
        unified_on_page=OnPageEvidence(),
        unified_robots=RobotsEvidence(),
        unified_schema=SchemaEvidence(),
        unified_geo=GeoAeoEvidence(),
        unified_trust=TrustStackResult(),
        unified_performance=PerformanceEvidence(),
    )

    md = MarkdownReporter.render(report)

    assert "Internal Link Graph & Equity Intelligence" in md
    assert "Internal Hyperlink Edges" in md
    assert "Max Click Depth from Root" in md
    assert "Top Pages by Internal Link Equity (Internal PageRank)" in md
    # Must NOT claim Google PageRank
    assert "Google PageRank" not in md


def test_frontier_build_result_populates_link_graph():
    """Verify that CrawlFrontier.build_result automatically builds and attaches link_graph."""
    from rankintel.crawler.frontier import CrawlFrontier
    from rankintel.models.schema import CrawlConfig

    frontier = CrawlFrontier("https://example.com", config=CrawlConfig(max_pages=10, max_depth=3))
    frontier.add_url("https://example.com", depth=0, parent_url=None, discovery_source="seed")
    frontier.mark_fetched(
        norm_url="https://example.com/",
        status_code=200,
        content_type="text/html",
        response_bytes=500,
        fetch_time_sec=0.1,
        discovered_links=["https://example.com/about", "https://example.com/services"],
    )
    frontier.add_url("https://example.com/about", depth=1, parent_url="https://example.com")
    frontier.mark_fetched(
        norm_url="https://example.com/about",
        status_code=200,
        content_type="text/html",
        response_bytes=400,
        fetch_time_sec=0.05,
        discovered_links=["https://example.com/services"],
    )

    result = frontier.build_result(duration_sec=0.25)
    assert result.link_graph is not None
    assert result.link_graph.crawled_nodes_count == 2
    assert result.link_graph.discovered_uncrawled_count == 1  # /services
    assert result.link_graph.total_nodes == 3
    assert result.link_graph.root_url == "https://example.com/"

