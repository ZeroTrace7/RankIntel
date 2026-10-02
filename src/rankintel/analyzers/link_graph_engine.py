"""
Internal Link Graph & Equity Intelligence Engine for RankIntel (Milestone M6.4).
Constructs a NetworkX directed graph (nx.DiGraph) from crawl evidence to compute:
- Internal vs external link classification
- Internal URL node identity preservation (preserving content query params like ?id=1)
- Click depth from the crawl root via shortest path
- Inbound and outbound internal link counts (unique vs total)
- Disconnected components and graph connectivity
- Internal PageRank-style graph authority/equity metrics
- Potential orphan detection with strict partial-crawl semantics

TERMINOLOGY GUARDRAILS:
- Metrics are strictly named "Internal Link Equity", "Internal PageRank", or "Internal Graph Authority".
- Never termed "Google PageRank" and does not claim to replicate search engine ranking algorithms.
- Unreachable pages in partial crawls are termed "UNREACHABLE_IN_OBSERVED_GRAPH", not definitively unreachable.
- Potential orphans are strictly crawled non-root pages with zero observed inbound links in the crawl.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qsl, urlencode

import networkx as nx

from rankintel.models.schema import (
    CrawlRecord,
    SiteCrawlResult,
    LinkClassification,
    NodeOrphanStatus,
    NodeCrawlState,
    ReachabilityInGraph,
    LinkGraphNode,
    LinkGraphEdge,
    InternalLinkGraphSummary,
)
from rankintel.crawler.normalizer import UrlNormalizer, TRACKING_QUERY_PARAMS
from rankintel.analyzers.record_lookup import RecordLookupIndex

SPECIAL_SCHEMES: Set[str] = {
    "mailto", "tel", "javascript", "data", "sms", "callto", "ftp", "file"
}


class InternalLinkGraphEngine:
    """
    Production-grade NetworkX directed graph engine for internal link topology
    and internal link equity distribution.
    Completely decoupled from search eligibility, crawler frontier internals, and scoring.
    """

    @classmethod
    def normalize_node_url(
        cls,
        url: str,
        base_url: Optional[str] = None,
        lookup_index: Optional[RecordLookupIndex] = None,
    ) -> str:
        """
        Normalize an internal URL for link graph node representation.
        - Resolves relative URLs against base_url
        - Strips URL fragments (#...)
        - Strips marketing tracking parameters (utm_*, gclid, etc.)
        - Normalizes default ports (:80, :443) and lowercases scheme/host
        - Normalizes non-root trailing slashes (/about/ -> /about)
        - Preserves and deterministically sorts content-defining query parameters (?id=1 vs ?id=2)
        - If lookup_index contains a matching CrawlRecord, uses its identity_url
        """
        if not url:
            return ""

        clean_url = url.strip()
        if base_url:
            clean_url = urljoin(base_url, clean_url)

        parsed = urlsplit(clean_url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return clean_url

        netloc = parsed.netloc.lower()
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        # Filter tracking query parameters while preserving content-defining parameters
        filtered_q: List[Tuple[str, str]] = []
        if parsed.query:
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            for k, v in query_pairs:
                if k.lower() not in TRACKING_QUERY_PARAMS:
                    filtered_q.append((k, v))
            filtered_q.sort(key=lambda item: (item[0], item[1]))

        new_query = urlencode(filtered_q) if filtered_q else ""
        normalized = urlunsplit((scheme, netloc, path, new_query, ""))

        if lookup_index is not None:
            matched_rec = lookup_index.lookup(normalized)
            if matched_rec:
                return matched_rec.identity_url or matched_rec.url

        return normalized

    @classmethod
    def classify_link(
        cls,
        target_url: str,
        base_url: str,
        allow_subdomains: bool = False,
    ) -> LinkClassification:
        """
        Classify a hyperlink target as INTERNAL, EXTERNAL, or SPECIAL.
        """
        if not target_url:
            return LinkClassification.SPECIAL

        t = target_url.strip()
        if t.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "sms:", "callto:")):
            return LinkClassification.SPECIAL

        parsed = urlsplit(t)
        scheme = parsed.scheme.lower()
        if scheme in SPECIAL_SCHEMES:
            return LinkClassification.SPECIAL

        if scheme and scheme not in ("http", "https"):
            return LinkClassification.SPECIAL

        if UrlNormalizer.is_same_domain(t, base_url, allow_subdomains=allow_subdomains):
            return LinkClassification.INTERNAL

        return LinkClassification.EXTERNAL

    @classmethod
    def compute_click_depth(
        cls,
        G: nx.DiGraph,
        root_node: str,
    ) -> Dict[str, Optional[int]]:
        """
        Compute shortest path click depth from root node using directed shortest paths.
        Returns dict mapping node URL to click depth (int) or None if unreachable in observed graph.
        """
        depths: Dict[str, Optional[int]] = {node: None for node in G.nodes()}
        if not root_node or root_node not in G:
            return depths

        try:
            shortest_lengths = nx.single_source_shortest_path_length(G, root_node)
            for node, length in shortest_lengths.items():
                depths[node] = length
        except Exception:
            pass

        return depths

    @classmethod
    def compute_internal_equity(
        cls,
        G: nx.DiGraph,
        alpha: float = 0.85,
        max_iter: int = 100,
        tol: float = 1e-06,
    ) -> Dict[str, float]:
        """
        Compute internal PageRank equity distribution across the internal link graph.

        DESIGN DECISION:
        - Internal PageRank uses the observed link_count edge weight, meaning repeated links
          between the same source and target contribute proportionally to graph weight.
        - Self-loops (page linking to itself) are removed prior to computing PageRank
          so pages do not artificially inflate their own equity.
        - Returns a dictionary mapping node URLs to equity scores (summing to ~1.0).
        """
        num_nodes = G.number_of_nodes()
        if num_nodes == 0:
            return {}
        if num_nodes == 1:
            node = next(iter(G.nodes()))
            return {node: 1.0}

        # Build clean copy without self-loops for PageRank calculation
        G_clean = G.copy()
        self_loops = list(nx.selfloop_edges(G_clean))
        if self_loops:
            G_clean.remove_edges_from(self_loops)

        try:
            scores = nx.pagerank(
                G_clean,
                alpha=alpha,
                weight="weight",
                max_iter=max_iter,
                tol=tol,
            )
            return {k: round(float(v), 6) for k, v in scores.items()}
        except Exception:
            # Fallback to uniform distribution if power iteration fails
            uniform = round(1.0 / num_nodes, 6)
            return {node: uniform for node in G.nodes()}

    @classmethod
    def build_graph(
        cls,
        records: Union[RecordLookupIndex, List[CrawlRecord], SiteCrawlResult],
        root_url: Optional[str] = None,
        allow_subdomains: bool = False,
    ) -> Tuple[nx.DiGraph, str, InternalLinkGraphSummary]:
        """
        Construct NetworkX directed graph from crawl records.
        """
        if isinstance(records, RecordLookupIndex):
            lookup = records
            rec_list = records.all_records()
        elif isinstance(records, SiteCrawlResult):
            lookup = RecordLookupIndex(records.crawl_records)
            rec_list = records.crawl_records
        elif isinstance(records, list):
            lookup = RecordLookupIndex(records)
            rec_list = records
        else:
            lookup = RecordLookupIndex([])
            rec_list = []

        # Determine root node URL
        resolved_root = ""
        if root_url:
            resolved_root = cls.normalize_node_url(root_url, base_url=root_url, lookup_index=lookup)
        else:
            # Look for depth == 0 or seed record
            seed_rec = next((r for r in rec_list if r.depth == 0 or r.discovery_source == "seed"), None)
            if seed_rec and seed_rec.url:
                resolved_root = cls.normalize_node_url(seed_rec.url, lookup_index=lookup)
            elif rec_list and rec_list[0].url:
                resolved_root = cls.normalize_node_url(rec_list[0].url, lookup_index=lookup)

        G = nx.DiGraph()

        # Temporary node data storage
        node_metadata: Dict[str, Dict[str, Any]] = {}
        total_external_links = 0

        # Step 1: Register all crawled records as CRAWLED nodes
        for rec in rec_list:
            if not rec.url:
                continue
            node_id = cls.normalize_node_url(rec.url, base_url=resolved_root, lookup_index=lookup)
            if not node_id:
                continue

            if node_id not in node_metadata:
                node_metadata[node_id] = {
                    "url": rec.url,
                    "identity_url": node_id,
                    "crawl_state": NodeCrawlState.CRAWLED,
                    "status_code": rec.status_code,
                    "self_links_count": 0,
                    "external_outbound_count": 0,
                }
            else:
                # Upgrade to crawled if previously seen as discovered
                node_metadata[node_id]["crawl_state"] = NodeCrawlState.CRAWLED
                if rec.status_code:
                    node_metadata[node_id]["status_code"] = rec.status_code

            if not G.has_node(node_id):
                G.add_node(node_id)

        # Step 2: Traverse discovered links to build directed edges and register discovered uncrawled nodes
        for rec in rec_list:
            if not rec.url:
                continue
            source_id = cls.normalize_node_url(rec.url, base_url=resolved_root, lookup_index=lookup)
            if not source_id:
                continue

            for raw_link in rec.discovered_links:
                if not raw_link:
                    continue

                classification = cls.classify_link(
                    raw_link,
                    base_url=rec.url or resolved_root,
                    allow_subdomains=allow_subdomains,
                )

                if classification == LinkClassification.EXTERNAL:
                    total_external_links += 1
                    if source_id in node_metadata:
                        node_metadata[source_id]["external_outbound_count"] += 1

                elif classification == LinkClassification.INTERNAL:
                    target_id = cls.normalize_node_url(
                        raw_link,
                        base_url=rec.url or resolved_root,
                        lookup_index=lookup,
                    )
                    if not target_id:
                        continue

                    # Register target node if unseen (discovered uncrawled)
                    if target_id not in node_metadata:
                        node_metadata[target_id] = {
                            "url": raw_link,
                            "identity_url": target_id,
                            "crawl_state": NodeCrawlState.DISCOVERED_UNCRAWLED,
                            "status_code": None,
                            "self_links_count": 0,
                            "external_outbound_count": 0,
                        }
                    if not G.has_node(target_id):
                        G.add_node(target_id)

                    # Edge handling
                    if source_id == target_id:
                        node_metadata[source_id]["self_links_count"] += 1
                        # Track self-loop in graph with weight
                        if G.has_edge(source_id, target_id):
                            G[source_id][target_id]["weight"] += 1
                        else:
                            G.add_edge(source_id, target_id, weight=1)
                    else:
                        if G.has_edge(source_id, target_id):
                            G[source_id][target_id]["weight"] += 1
                        else:
                            G.add_edge(source_id, target_id, weight=1)

        # If resolved_root wasn't added yet, add it
        if resolved_root and not G.has_node(resolved_root):
            G.add_node(resolved_root)
            if resolved_root not in node_metadata:
                node_metadata[resolved_root] = {
                    "url": resolved_root,
                    "identity_url": resolved_root,
                    "crawl_state": NodeCrawlState.CRAWLED,
                    "status_code": 200,
                    "self_links_count": 0,
                    "external_outbound_count": 0,
                }

        # Step 3: Compute click depths
        click_depths = cls.compute_click_depth(G, resolved_root)

        # Step 4: Compute internal PageRank equity
        equity_scores = cls.compute_internal_equity(G)

        # Compute percentile ranks (0.0 to 100.0%)
        sorted_equity = sorted(equity_scores.items(), key=lambda item: item[1])
        n_nodes = len(sorted_equity)
        percentile_map: Dict[str, float] = {}
        for rank_idx, (node_id, _) in enumerate(sorted_equity):
            if n_nodes <= 1:
                percentile_map[node_id] = 100.0
            else:
                percentile_map[node_id] = round((rank_idx / (n_nodes - 1)) * 100.0, 1)

        # Step 5: Build typed LinkGraphNode models
        nodes_dict: Dict[str, LinkGraphNode] = {}
        potential_orphans: List[str] = []
        unreachable_pages: List[str] = []
        deep_pages: List[str] = []
        dead_ends: List[str] = []

        total_internal_edges_count = 0

        for node_id in G.nodes():
            meta = node_metadata.get(node_id, {})
            crawl_state = meta.get("crawl_state", NodeCrawlState.DISCOVERED_UNCRAWLED)
            status_code = meta.get("status_code")
            self_count = meta.get("self_links_count", 0)
            ext_count = meta.get("external_outbound_count", 0)

            # Inbound / Outbound counts (excluding self)
            in_preds = [p for p in G.predecessors(node_id) if p != node_id]
            out_succs = [s for s in G.successors(node_id) if s != node_id]

            inbound_internal_count = len(in_preds)
            outbound_internal_count = len(out_succs)

            # Total observed links (sum of weights)
            total_inbound = sum(G[p][node_id].get("weight", 1) for p in in_preds) + self_count
            total_outbound = sum(G[node_id][s].get("weight", 1) for s in out_succs) + self_count

            # Count internal directed edges between distinct nodes
            total_internal_edges_count += outbound_internal_count

            # Reachability
            depth = click_depths.get(node_id)
            if depth is not None:
                reachability = ReachabilityInGraph.REACHABLE_FROM_ROOT
                if depth > 3:
                    deep_pages.append(node_id)
            else:
                reachability = ReachabilityInGraph.UNREACHABLE_IN_OBSERVED_GRAPH
                unreachable_pages.append(node_id)

            # Orphan Status:
            # Potential orphan = crawled non-root page with 0 observed inbound internal links
            # Strictly distinguished from unreachable_in_observed_graph
            is_root = bool(resolved_root and node_id == resolved_root)
            if is_root:
                orphan_status = NodeOrphanStatus.ROOT
            elif crawl_state == NodeCrawlState.CRAWLED and inbound_internal_count == 0:
                orphan_status = NodeOrphanStatus.POTENTIAL_ORPHAN
                potential_orphans.append(node_id)
            else:
                orphan_status = NodeOrphanStatus.CONNECTED

            is_dead_end = bool(crawl_state == NodeCrawlState.CRAWLED and outbound_internal_count == 0)
            if is_dead_end:
                dead_ends.append(node_id)

            equity_val = equity_scores.get(node_id, 0.0)
            percentile_val = percentile_map.get(node_id, 0.0)

            node_model = LinkGraphNode(
                url=meta.get("url", node_id),
                identity_url=node_id,
                crawl_state=crawl_state,
                orphan_status=orphan_status,
                reachability=reachability,
                status_code=status_code,
                click_depth=depth,
                inbound_internal_count=inbound_internal_count,
                outbound_internal_count=outbound_internal_count,
                total_inbound_links=total_inbound,
                total_outbound_links=total_outbound,
                self_links_count=self_count,
                external_outbound_count=ext_count,
                internal_equity_score=equity_val,
                equity_percentile=percentile_val,
                is_dead_end=is_dead_end,
            )
            nodes_dict[node_id] = node_model

        # Graph connectivity
        try:
            scc_count = nx.number_strongly_connected_components(G)
        except Exception:
            scc_count = 0

        try:
            wcc_count = nx.number_weakly_connected_components(G)
        except Exception:
            wcc_count = 0

        max_depth = max((d for d in click_depths.values() if d is not None), default=0)

        # Top & bottom equity rankings (descending for top, ascending for bottom)
        crawled_nodes = [n for n in nodes_dict.values() if n.crawl_state == NodeCrawlState.CRAWLED]
        sorted_by_equity = sorted(crawled_nodes or nodes_dict.values(), key=lambda n: n.internal_equity_score, reverse=True)
        top_equity_pages = [n.identity_url for n in sorted_by_equity[:10]]
        lowest_equity_pages = [n.identity_url for n in sorted_by_equity[-10:] if n.identity_url not in top_equity_pages]

        crawled_count = sum(1 for n in nodes_dict.values() if n.crawl_state == NodeCrawlState.CRAWLED)
        uncrawled_count = sum(1 for n in nodes_dict.values() if n.crawl_state == NodeCrawlState.DISCOVERED_UNCRAWLED)

        summary = InternalLinkGraphSummary(
            root_url=resolved_root,
            total_nodes=len(nodes_dict),
            crawled_nodes_count=crawled_count,
            discovered_uncrawled_count=uncrawled_count,
            total_internal_edges=total_internal_edges_count,
            total_external_links_found=total_external_links,
            strongly_connected_components=scc_count,
            weakly_connected_components=wcc_count,
            max_click_depth=max_depth,
            deep_pages_count=len(deep_pages),
            potential_orphan_count=len(potential_orphans),
            unreachable_in_observed_graph_count=len(unreachable_pages),
            dead_ends_count=len(dead_ends),
            nodes=nodes_dict,
            potential_orphans=potential_orphans,
            unreachable_in_observed_graph=unreachable_pages,
            deep_pages=deep_pages,
            dead_ends=dead_ends,
            top_equity_pages=top_equity_pages,
            lowest_equity_pages=lowest_equity_pages,
        )

        return G, resolved_root, summary

    @classmethod
    def analyze_site(
        cls,
        site_crawl: SiteCrawlResult,
        root_url: Optional[str] = None,
        allow_subdomains: bool = False,
    ) -> SiteCrawlResult:
        """
        Analyze internal link graph on a completed SiteCrawlResult.
        Populates site_crawl.link_graph and site_crawl.orphan_pages without mutating scores.
        """
        if not site_crawl:
            return site_crawl

        _, _, summary = cls.build_graph(
            records=site_crawl,
            root_url=root_url,
            allow_subdomains=allow_subdomains,
        )

        site_crawl.link_graph = summary
        site_crawl.orphan_pages = list(summary.potential_orphans)

        # Synthesize structural findings into site_wide_issues without creating duplicates
        if summary.potential_orphans:
            msg = f"{len(summary.potential_orphans)} potential orphan page(s) detected (0 observed internal inbound links)"
            if msg not in site_crawl.site_wide_issues:
                site_crawl.site_wide_issues.append(msg)

        if summary.deep_pages:
            msg = f"{len(summary.deep_pages)} deep page(s) require >3 clicks from root"
            if msg not in site_crawl.site_wide_issues:
                site_crawl.site_wide_issues.append(msg)

        if summary.weakly_connected_components > 1:
            msg = f"{summary.weakly_connected_components} disconnected link graph components detected"
            if msg not in site_crawl.site_wide_issues:
                site_crawl.site_wide_issues.append(msg)

        # Ensure site_wide_issues remains unique
        site_crawl.site_wide_issues = list(dict.fromkeys(site_crawl.site_wide_issues))
        return site_crawl
