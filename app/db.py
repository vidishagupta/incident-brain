"""Database connection and abstraction layer for Incident Brain.
Supports official FalkorDB client with parameterized Cypher queries,
multi-graph tenancy ('company_graph' + 'memory_<team>'), and an in-memory
Cypher-compatible fallback when no FalkorDB server is reachable.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import re
from falkordb import FalkorDB, Node, Edge
from falkordb.query_result import QueryResult
import redis.exceptions
from app.config import settings

logger = logging.getLogger("incident_brain.db")


class InMemoryQueryResult:
    """Mock QueryResult matching falkordb.query_result.QueryResult interface."""
    def __init__(self, header: List[str], result_set: List[List[Any]]):
        self.header = header
        self.result_set = result_set
        self.nodes_created = 0
        self.relationships_created = 0
        self.run_time_ms = 1.0


class InMemoryGraph:
    """In-memory Graph engine implementing the subset of Cypher needed by Incident Brain."""
    def __init__(self, name: str):
        self.name = name
        self.nodes: Dict[str, Dict[str, Any]] = {}  # key: label:name or id -> data
        self.edges: List[Dict[str, Any]] = []  # list of {src, dst, rel, props}

    def delete(self):
        self.nodes.clear()
        self.edges.clear()

    def query(self, q: str, params: Optional[Dict[str, Any]] = None) -> InMemoryQueryResult:
        params = params or {}
        q_strip = q.strip()

        # Handle CALL algo.PageRank
        if "algo.PageRank" in q_strip:
            return self._algo_pagerank()

        # Handle MERGE / CREATE write queries
        if "MERGE" in q_strip or "CREATE" in q_strip:
            return self._handle_write(q_strip, params)

        # Handle MATCH queries
        return self._handle_match(q_strip, params)

    def _algo_pagerank(self) -> InMemoryQueryResult:
        # In-memory PageRank calculation for Service nodes
        service_names = [n["props"].get("name") for n in self.nodes.values() if "Service" in n["labels"]]
        in_degrees = {s: 0.15 for s in service_names}
        for e in self.edges:
            if e["rel"] == "DEPENDS_ON":
                # If A DEPENDS_ON B, B is critical/upstream
                dst_node = self.nodes.get(e["dst"])
                if dst_node and dst_node["props"].get("name") in in_degrees:
                    in_degrees[dst_node["props"]["name"]] += 0.85

        result_set = []
        for name, score in sorted(in_degrees.items(), key=lambda x: x[1], reverse=True):
            node_dict = next((n for n in self.nodes.values() if n["props"].get("name") == name), None)
            if node_dict:
                result_set.append([name, round(score, 4)])
        return InMemoryQueryResult(["node.name", "score"], result_set)

    def _handle_write(self, q: str, params: Dict[str, Any]) -> InMemoryQueryResult:
        # 1. First process any node creations/merges so nodes exist for edge binding
        node_matches = re.findall(r"MERGE\s*\(([a-zA-Z0-9_]+):([a-zA-Z0-9_]+)", q)
        for var_name, label in node_matches:
            name = params.get("name") or params.get("inc_id") or params.get("title") or params.get("team")
            if name:
                node_id = f"{label}:{name}"
                if node_id not in self.nodes:
                    node_props = dict(params)
                    if "name" not in node_props:
                        node_props["name"] = name
                    self.nodes[node_id] = {
                        "id": len(self.nodes) + 1,
                        "labels": [label],
                        "props": node_props
                    }
                else:
                    self.nodes[node_id]["props"].update(params)

        # 2. Next process all relationships created in this query
        for rel_match in re.finditer(r"-\[.*?[:]([A-Za-z0-9_]+).*?\]->", q):
            rel_type = rel_match.group(1)
            src_name = None
            dst_name = None

            if rel_type == "DEPENDS_ON":
                src_name = params.get("src")
                dst_name = params.get("dst")
            elif rel_type == "MEMBER_OF":
                src_name = params.get("name")
                dst_name = params.get("team")
            elif rel_type == "OWNS":
                src_name = params.get("person")
                dst_name = params.get("service")
            elif rel_type == "AFFECTED":
                src_name = params.get("name") or params.get("inc_id")
                dst_name = params.get("service")
            elif rel_type == "WORKED_ON":
                src_name = params.get("person")
                dst_name = params.get("name") or params.get("inc_id")
            elif rel_type == "SIMILAR_TO":
                src_name = params.get("src")
                dst_name = params.get("dst")
            elif rel_type == "ABOUT":
                src_name = params.get("name")
                dst_name = params.get("service")
            elif rel_type == "DOCUMENTED_IN":
                src_name = params.get("service")
                dst_name = params.get("name")
            elif rel_type == "SHAPED":
                src_name = params.get("name")
                dst_name = params.get("service")
            else:
                src_name = params.get("src") or params.get("source") or params.get("person")
                dst_name = params.get("dst") or params.get("target") or params.get("service")

            src_id = self._find_node_id_by_name(src_name)
            dst_id = self._find_node_id_by_name(dst_name)

            if src_id and dst_id:
                exists = any(e["src"] == src_id and e["dst"] == dst_id and e["rel"] == rel_type for e in self.edges)
                if not exists:
                    self.edges.append({
                        "src": src_id,
                        "dst": dst_id,
                        "rel": rel_type,
                        "props": dict(params)
                    })

        return InMemoryQueryResult([], [])

    def _find_node_id_by_name(self, name: Any) -> Optional[str]:
        if not name:
            return None
        for nid, data in self.nodes.items():
            if data["props"].get("name") == name or data["props"].get("title") == name:
                return nid
        return None

    def _handle_match(self, q: str, params: Dict[str, Any]) -> InMemoryQueryResult:
        # 1. blast_radius: (s:Service {name: $service_name})<-[:DEPENDS_ON*1..4]-(downstream:Service)
        if "<-[:DEPENDS_ON" in q:
            service_name = params.get("service_name")
            start_nid = self._find_node_id_by_name(service_name)
            if not start_nid:
                return InMemoryQueryResult(["downstream.name", "downstream.tier", "hop"], [])
            
            # BFS downstream (nodes that depend on start_nid)
            # Edge: (downstream)-[:DEPENDS_ON]->(service)
            visited = {}
            queue = [(start_nid, 0)]
            while queue:
                curr_id, hop = queue.pop(0)
                if hop >= 4:
                    continue
                for e in self.edges:
                    if e["rel"] == "DEPENDS_ON" and e["dst"] == curr_id:
                        src_id = e["src"]
                        if src_id not in visited and src_id != start_nid:
                            visited[src_id] = hop + 1
                            queue.append((src_id, hop + 1))
            
            rows = []
            for nid, hop in sorted(visited.items(), key=lambda x: x[1]):
                node = self.nodes.get(nid)
                if node:
                    s_name = node["props"].get("name", "")
                    s_tier = node["props"].get("tier", "tier-2")
                    rows.append([s_name, s_tier, hop])
            return InMemoryQueryResult(["downstream.name", "downstream.tier", "hop"], rows)

        # 2. who_knows query
        if "OWNS" in q or "WORKED_ON" in q:
            service_name = params.get("service_name")
            target_nid = self._find_node_id_by_name(service_name)
            if not target_nid:
                return InMemoryQueryResult(["person.name", "person.role", "person.slack", "reason", "score"], [])
            
            candidates = {}  # name -> {role, slack, reason, score}
            # Check OWNS
            for e in self.edges:
                if e["rel"] == "OWNS" and e["dst"] == target_nid:
                    p_node = self.nodes.get(e["src"])
                    if p_node:
                        p_name = p_node["props"].get("name", "")
                        candidates[p_name] = {
                            "name": p_name,
                            "role": p_node["props"].get("role", "Engineer"),
                            "slack": p_node["props"].get("slack", f"@{p_name.lower().replace(' ', '')}"),
                            "reason": f"Primary Owner of {service_name}",
                            "score": 10
                        }
            
            # Check past incidents worked on
            for e in self.edges:
                if e["rel"] == "AFFECTED" and e["dst"] == target_nid:
                    inc_id = e["src"]
                    for e2 in self.edges:
                        if e2["rel"] == "WORKED_ON" and e2["dst"] == inc_id:
                            p_node = self.nodes.get(e2["src"])
                            if p_node:
                                p_name = p_node["props"].get("name", "")
                                if p_name in candidates:
                                    candidates[p_name]["score"] += 5
                                    candidates[p_name]["reason"] += " + Resolved past incident"
                                else:
                                    candidates[p_name] = {
                                        "name": p_name,
                                        "role": p_node["props"].get("role", "Engineer"),
                                        "slack": p_node["props"].get("slack", f"@{p_name.lower().replace(' ', '')}"),
                                        "reason": f"Resolved past incident on {service_name}",
                                        "score": 7
                                    }
            
            sorted_candidates = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)
            rows = [[c["name"], c["role"], c["slack"], c["reason"], c["score"]] for c in sorted_candidates]
            return InMemoryQueryResult(["person.name", "person.role", "person.slack", "reason", "score"], rows)

        # 3. similar_incidents query
        if "Incident" in q and ("SIMILAR_TO" in q or "AFFECTED" in q or "RETURN" in q):
            service_name = params.get("service_name")
            target_nid = self._find_node_id_by_name(service_name)
            
            inc_records = []
            for nid, node in self.nodes.items():
                if "Incident" in node["labels"]:
                    props = node["props"]
                    # Check if directly affected or similar
                    affected_this = any(e["rel"] == "AFFECTED" and e["src"] == nid and e["dst"] == target_nid for e in self.edges)
                    is_similar = False
                    for e in self.edges:
                        if e["rel"] == "SIMILAR_TO" and (e["src"] == nid or e["dst"] == nid):
                            is_similar = True

                    if affected_this or is_similar or not service_name:
                        inc_records.append([
                            props.get("title", "Incident"),
                            props.get("root_cause", "Unknown"),
                            props.get("fix", "No fix documented"),
                            props.get("severity", "P2"),
                            props.get("resolved_at", "2026-09-15")
                        ])
            return InMemoryQueryResult(["i.title", "i.root_cause", "i.fix", "i.severity", "i.resolved_at"], inc_records)

        # 4. get_docs query
        if "Doc" in q or "DOCUMENTED_IN" in q or "Decision" in q:
            service_name = params.get("service_name")
            target_nid = self._find_node_id_by_name(service_name)
            docs = []
            for e in self.edges:
                if e["rel"] in ["DOCUMENTED_IN", "ABOUT", "SHAPED"] and (e["src"] == target_nid or e["dst"] == target_nid):
                    other_id = e["src"] if e["dst"] == target_nid else e["dst"]
                    node = self.nodes.get(other_id)
                    if node:
                        docs.append([
                            node["props"].get("title", "Doc"),
                            node["labels"][0],
                            node["props"].get("url", "#"),
                            node["props"].get("summary", "")
                        ])
            return InMemoryQueryResult(["d.title", "type", "d.url", "d.summary"], docs)

        # 5. explain_path: shortest path between source and target
        if "shortestPath" in q or "path" in q:
            source = params.get("source") or params.get("source_name")
            target = params.get("target") or params.get("target_name")
            src_nid = self._find_node_id_by_name(source)
            dst_nid = self._find_node_id_by_name(target)
            
            # Simple BFS to find shortest path
            if src_nid and dst_nid:
                queue = [[src_nid]]
                visited = {src_nid}
                found_path = None
                while queue:
                    curr_path = queue.pop(0)
                    last_node = curr_path[-1]
                    if last_node == dst_nid:
                        found_path = curr_path
                        break
                    for e in self.edges:
                        nxt = None
                        if e["src"] == last_node and e["dst"] not in visited:
                            nxt = e["dst"]
                        elif e["dst"] == last_node and e["src"] not in visited:
                            nxt = e["src"]
                        if nxt:
                            visited.add(nxt)
                            queue.append(curr_path + [nxt])
                
                if found_path:
                    path_names = [self.nodes[n]["props"].get("name", n) for n in found_path]
                    return InMemoryQueryResult(["path_nodes"], [[path_names]])
            return InMemoryQueryResult(["path_nodes"], [])

        # Default fallback: return all nodes or general match
        if "RETURN n" in q or "RETURN s" in q:
            rows = []
            for nid, node in self.nodes.items():
                rows.append([Node(node_id=node["id"], labels=node["labels"], properties=node["props"])])
            return InMemoryQueryResult(["node"], rows)

        return InMemoryQueryResult([], [])


class DatabaseManager:
    """Manages connections to FalkorDB or gracefully falls back to InMemoryGraph."""
    def __init__(self):
        self._client: Optional[FalkorDB] = None
        self._is_falkordb_connected: bool = False
        self._in_memory_graphs: Dict[str, InMemoryGraph] = {}
        self._init_connection()

    def _init_connection(self):
        try:
            if settings.FALKORDB_URL:
                self._client = FalkorDB.from_url(settings.FALKORDB_URL)
            else:
                self._client = FalkorDB(
                    host=settings.FALKORDB_HOST,
                    port=settings.FALKORDB_PORT,
                    password=settings.FALKORDB_PASSWORD
                )
            # Test connection with a quick query or ping
            test_graph = self._client.select_graph(settings.COMPANY_GRAPH)
            test_graph.query("RETURN 1")
            self._is_falkordb_connected = True
            logger.info("Connected to native FalkorDB successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to FalkorDB at {settings.FALKORDB_URL} ({e}). Using in-memory graph simulator.")
            self._is_falkordb_connected = False
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._is_falkordb_connected

    def select_graph(self, graph_name: str):
        if self._is_falkordb_connected and self._client:
            return self._client.select_graph(graph_name)
        
        if graph_name not in self._in_memory_graphs:
            self._in_memory_graphs[graph_name] = InMemoryGraph(graph_name)
        return self._in_memory_graphs[graph_name]

    def query(self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None):
        graph = self.select_graph(graph_name)
        return graph.query(cypher, params)

    def get_snapshot(self, graph_name: str) -> Dict[str, Any]:
        """Returns nodes and links formatted for force-graph visualization."""
        if not self._is_falkordb_connected:
            mem_g = self.select_graph(graph_name)
            nodes = []
            for nid, n in mem_g.nodes.items():
                nodes.append({
                    "id": n["props"].get("name") or n["props"].get("title") or nid,
                    "label": n["labels"][0] if n["labels"] else "Node",
                    "properties": n["props"]
                })
            links = []
            for e in mem_g.edges:
                src_node = mem_g.nodes.get(e["src"])
                dst_node = mem_g.nodes.get(e["dst"])
                if src_node and dst_node:
                    src_id = src_node["props"].get("name") or src_node["props"].get("title") or e["src"]
                    dst_id = dst_node["props"].get("name") or dst_node["props"].get("title") or e["dst"]
                    links.append({
                        "source": src_id,
                        "target": dst_id,
                        "type": e["rel"],
                        "properties": e["props"]
                    })
            return {"nodes": nodes, "links": links}

        # Native FalkorDB query for all nodes and edges
        cypher = """
        MATCH (s)-[r]->(t)
        RETURN s.name, labels(s), properties(s), type(r), t.name, labels(t), properties(t)
        """
        try:
            graph = self.select_graph(graph_name)
            res = graph.query(cypher)
            nodes_dict = {}
            links = []
            for row in res.result_set:
                s_name, s_labels, s_props, r_type, t_name, t_labels, t_props = row
                s_id = s_name or s_props.get("title", "Unknown")
                t_id = t_name or t_props.get("title", "Unknown")
                if s_id not in nodes_dict:
                    nodes_dict[s_id] = {
                        "id": s_id,
                        "label": s_labels[0] if s_labels else "Node",
                        "properties": s_props
                    }
                if t_id not in nodes_dict:
                    nodes_dict[t_id] = {
                        "id": t_id,
                        "label": t_labels[0] if t_labels else "Node",
                        "properties": t_props
                    }
                links.append({
                    "source": s_id,
                    "target": t_id,
                    "type": r_type
                })
            return {"nodes": list(nodes_dict.values()), "links": links}
        except Exception as e:
            logger.error(f"Error fetching snapshot from FalkorDB: {e}")
            return {"nodes": [], "links": []}


db_manager = DatabaseManager()
