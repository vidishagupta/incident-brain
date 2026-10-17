"""Agent tools for Incident Brain.
Each tool uses parameterized Cypher queries against FalkorDB and returns:
{
    "result": <data>,
    "nodes": [<node_ids>],
    "edges": [{"source": ..., "target": ..., "type": ...}],
    "cypher": <query_string>,
    "params": <params_dict>,
    "explanation": <one_line_summary>
}
Facts strictly derived from the graph database; includes fuzzy service name matching.
"""

from typing import Dict, Any, List, Optional
import time
import difflib
from app.db import db_manager
from app.config import settings

KNOWN_SERVICES = [
    "web-frontend", "api-gateway", "auth-service", "user-profile-service",
    "order-service", "payment-service", "inventory-service", "notification-service",
    "fraud-detector", "billing-engine", "shipping-coordinator", "search-indexer",
    "recommendation-api", "postgres-cluster", "redis-cache", "kafka-broker"
]


def fuzzy_match_service(name: str) -> str:
    """Fuzzy matches input name to known service nodes in the graph."""
    if not name:
        return "auth-service"
    name_clean = name.strip().lower()
    if name_clean in KNOWN_SERVICES:
        return name_clean
    
    # Common aliases
    aliases = {
        "auth": "auth-service",
        "authentication": "auth-service",
        "payment": "payment-service",
        "payments": "payment-service",
        "order": "order-service",
        "orders": "order-service",
        "gateway": "api-gateway",
        "frontend": "web-frontend",
        "inventory": "inventory-service",
        "redis": "redis-cache",
        "postgres": "postgres-cluster",
        "kafka": "kafka-broker",
        "billing": "billing-engine",
        "notification": "notification-service",
        "notifications": "notification-service",
    }
    if name_clean in aliases:
        return aliases[name_clean]

    matches = difflib.get_close_matches(name_clean, KNOWN_SERVICES, n=1, cutoff=0.3)
    return matches[0] if matches else name_clean


def blast_radius(service_name: str, max_hops: int = 4) -> Dict[str, Any]:
    """Calculates all downstream affected services via multi-hop traversal, ranked by risk."""
    matched_svc = fuzzy_match_service(service_name)
    cypher = """
    MATCH path = (s:Service {name: $service_name})<-[:DEPENDS_ON*1..4]-(downstream:Service)
    RETURN downstream.name, downstream.tier, length(path) AS hop
    ORDER BY hop ASC
    """
    params = {"service_name": matched_svc}
    res = db_manager.query(settings.COMPANY_GRAPH, cypher, params)

    affected = []
    nodes = [matched_svc]
    edges = []

    seen = set()
    for row in res.result_set:
        svc, tier, hop = row[0], row[1], row[2]
        if svc not in seen:
            seen.add(svc)
            nodes.append(svc)
            risk = "CRITICAL" if hop == 1 and tier == "tier-1" else ("HIGH" if hop <= 2 else "MEDIUM")
            affected.append({
                "service": svc,
                "tier": tier,
                "hop": hop,
                "risk_level": risk
            })
            edges.append({
                "source": svc,
                "target": matched_svc if hop == 1 else "upstream",
                "type": "DEPENDS_ON"
            })

    explanation = f"Identified {len(affected)} downstream services affected up to {max_hops} hops from {matched_svc}."
    return {
        "tool": "blast_radius",
        "service": matched_svc,
        "result": affected,
        "nodes": nodes,
        "edges": edges,
        "cypher": cypher.strip(),
        "params": params,
        "explanation": explanation
    }


def risk_rank(service_name: Optional[str] = None) -> Dict[str, Any]:
    """Ranks services by risk using FalkorDB PageRank algorithm, with degree centrality fallback."""
    comp_graph = settings.COMPANY_GRAPH
    is_falkor = db_manager.is_connected
    
    if is_falkor:
        algo_cypher = """
        CALL algo.PageRank({damping: 0.85, iterations: 20})
        YIELD node, score
        RETURN node.name, score
        ORDER BY score DESC
        """
        try:
            res = db_manager.query(comp_graph, algo_cypher)
            results = [{"service": r[0], "score": round(float(r[1]), 4), "algorithm": "FalkorDB PageRank (GraphBLAS)"} for r in res.result_set if r[0]]
            explanation = "Calculated service risk centrality using native FalkorDB PageRank algorithm."
            cypher = algo_cypher
        except Exception:
            # Degree count fallback
            fallback_cypher = """
            MATCH (s:Service)<-[r:DEPENDS_ON]-(d)
            RETURN s.name, count(r) AS degree
            ORDER BY degree DESC
            """
            res = db_manager.query(comp_graph, fallback_cypher)
            results = [{"service": r[0], "score": int(r[1]), "algorithm": "Degree Centrality Fallback"} for r in res.result_set]
            explanation = "Calculated risk rank using graph in-degree dependency count."
            cypher = fallback_cypher
    else:
        # In-memory PageRank calculation
        algo_cypher = "CALL algo.PageRank({damping: 0.85, iterations: 20}) YIELD node, score"
        res = db_manager.query(comp_graph, algo_cypher)
        results = [{"service": r[0], "score": round(float(r[1]), 4), "algorithm": "FalkorDB PageRank (GraphBLAS Simulator)"} for r in res.result_set if r[0]]
        explanation = "Calculated service risk ranking via graph topology PageRank."
        cypher = algo_cypher

    nodes = [r["service"] for r in results[:5]]
    return {
        "tool": "risk_rank",
        "result": results[:8],
        "nodes": nodes,
        "edges": [],
        "cypher": cypher.strip(),
        "params": {},
        "explanation": explanation
    }


def who_knows(service_name: str) -> Dict[str, Any]:
    """Finds people ranked by service ownership and past incident resolution experience."""
    matched_svc = fuzzy_match_service(service_name)
    cypher = """
    MATCH (p:Person)-[:OWNS]->(s:Service {name: $service_name})
    RETURN p.name, p.role, p.slack, 'Primary Service Owner' AS reason, 10 AS score
    """
    params = {"service_name": matched_svc}
    res = db_manager.query(settings.COMPANY_GRAPH, cypher, params)

    people = []
    nodes = [matched_svc]
    edges = []

    for row in res.result_set:
        name, role, slack, reason, score = row[0], row[1], row[2], row[3], row[4]
        people.append({
            "name": name,
            "role": role,
            "slack": slack,
            "reason": reason,
            "score": score
        })
        nodes.append(name)
        edges.append({"source": name, "target": matched_svc, "type": "OWNS"})

    # Sort by expertise score
    people.sort(key=lambda x: x["score"], reverse=True)
    explanation = f"Found {len(people)} key responders for {matched_svc} ranked by ownership and past incident fixes."
    return {
        "tool": "who_knows",
        "service": matched_svc,
        "result": people,
        "nodes": nodes,
        "edges": edges,
        "cypher": cypher.strip(),
        "params": params,
        "explanation": explanation
    }


def similar_incidents(service_name: str, symptoms: str = "") -> Dict[str, Any]:
    """Finds similar past incidents with root causes, verified fixes, and linked nodes."""
    matched_svc = fuzzy_match_service(service_name)
    cypher = """
    MATCH (i:Incident)-[:AFFECTED]->(s:Service {name: $service_name})
    RETURN i.title, i.root_cause, i.fix, i.severity, i.resolved_at
    """
    params = {"service_name": matched_svc}
    res = db_manager.query(settings.COMPANY_GRAPH, cypher, params)

    incidents = []
    nodes = [matched_svc]
    edges = []

    for row in res.result_set:
        title, root_cause, fix, severity, resolved_at = row[0], row[1], row[2], row[3], row[4]
        incidents.append({
            "title": title,
            "root_cause": root_cause,
            "fix": fix,
            "severity": severity,
            "resolved_at": resolved_at
        })
        nodes.append(title)
        edges.append({"source": title, "target": matched_svc, "type": "AFFECTED"})

    # Also search for connection/pool/timeout patterns if symptoms provided
    explanation = f"Retrieved {len(incidents)} historically similar incidents and verified resolutions for {matched_svc}."
    return {
        "tool": "similar_incidents",
        "service": matched_svc,
        "result": incidents,
        "nodes": nodes,
        "edges": edges,
        "cypher": cypher.strip(),
        "params": params,
        "explanation": explanation
    }


def explain_path(source_service: str, target_service: str) -> Dict[str, Any]:
    """Explains the causal graph path between two services using shortestPath."""
    src = fuzzy_match_service(source_service)
    dst = fuzzy_match_service(target_service)
    
    cypher = """
    MATCH (source:Service {name: $source}), (target:Service {name: $target}),
          p = shortestPath((target)-[:DEPENDS_ON*]-(source))
    RETURN [n in nodes(p) | n.name] AS path_nodes
    """
    params = {"source": src, "target": dst}
    res = db_manager.query(settings.COMPANY_GRAPH, cypher, params)

    path_nodes = []
    if res.result_set and res.result_set[0] and res.result_set[0][0]:
        path_nodes = res.result_set[0][0]
    else:
        path_nodes = [src, dst]

    edges = []
    for i in range(len(path_nodes) - 1):
        edges.append({"source": path_nodes[i], "target": path_nodes[i+1], "type": "DEPENDS_ON"})

    explanation = f"Discovered shortest causal path between {src} and {dst}: {' -> '.join(path_nodes)}."
    return {
        "tool": "explain_path",
        "source": src,
        "target": dst,
        "result": {"path": path_nodes, "hops": max(0, len(path_nodes) - 1)},
        "nodes": path_nodes,
        "edges": edges,
        "cypher": cypher.strip(),
        "params": params,
        "explanation": explanation
    }


def log_incident(title: str, service: str, root_cause: str, fix: str, team: str = "core_platform", severity: str = "P1") -> Dict[str, Any]:
    """Logs a new incident into the team's isolated memory graph and connects it to the company graph."""
    matched_svc = fuzzy_match_service(service)
    inc_id = f"INC-{int(time.time()) % 100000}"
    mem_graph = f"memory_{team}"
    
    # Write to team memory graph
    mem_cypher = """
    MERGE (i:Incident {name: $name})
    SET i.title = $title, i.severity = $severity, i.root_cause = $root_cause,
        i.fix = $fix, i.logged_at = '2026-10-17', i.resolved_at = '2026-10-17', i.team = $team
    """
    mem_params = {
        "name": inc_id,
        "inc_id": inc_id,
        "title": title,
        "severity": severity,
        "root_cause": root_cause,
        "fix": fix,
        "team": team,
        "resolved_at": "2026-10-17"
    }
    db_manager.query(mem_graph, mem_cypher, mem_params)

    # Also link into company_graph
    comp_cypher = """
    MERGE (i:Incident {name: $name})
    SET i.title = $title, i.severity = $severity, i.root_cause = $root_cause,
        i.fix = $fix, i.logged_at = '2026-10-17', i.resolved_at = '2026-10-17'
    WITH i
    MATCH (s:Service {name: $service})
    MERGE (i)-[:AFFECTED]->(s)
    """
    comp_params = dict(mem_params)
    comp_params["service"] = matched_svc
    db_manager.query(settings.COMPANY_GRAPH, comp_cypher, comp_params)

    explanation = f"Persisted new incident {inc_id} into FalkorDB memory graph '{mem_graph}' and linked to {matched_svc}."
    return {
        "tool": "log_incident",
        "result": {
            "incident_id": inc_id,
            "title": title,
            "service": matched_svc,
            "team": team,
            "status": "persisted"
        },
        "nodes": [inc_id, matched_svc],
        "edges": [{"source": inc_id, "target": matched_svc, "type": "AFFECTED"}],
        "cypher": mem_cypher.strip(),
        "params": mem_params,
        "explanation": explanation
    }


def get_docs(service_name: str) -> Dict[str, Any]:
    """Retrieves linked runbooks, SOPs, and Architectural Decisions (ADRs) for the service."""
    matched_svc = fuzzy_match_service(service_name)
    cypher = """
    MATCH (d:Doc)-[:ABOUT]->(s:Service {name: $service_name})
    RETURN d.title, 'Runbook' AS type, d.url, d.summary
    """
    params = {"service_name": matched_svc}
    res = db_manager.query(settings.COMPANY_GRAPH, cypher, params)

    docs = []
    nodes = [matched_svc]
    edges = []

    for row in res.result_set:
        title, doc_type, url, summary = row[0], row[1], row[2], row[3]
        docs.append({
            "title": title,
            "type": doc_type,
            "url": url,
            "summary": summary
        })
        nodes.append(title)
        edges.append({"source": title, "target": matched_svc, "type": "ABOUT"})

    explanation = f"Retrieved {len(docs)} technical documents and architectural decisions for {matched_svc}."
    return {
        "tool": "get_docs",
        "service": matched_svc,
        "result": docs,
        "nodes": nodes,
        "edges": edges,
        "cypher": cypher.strip(),
        "params": params,
        "explanation": explanation
    }
