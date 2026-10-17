"""Idempotent database seeder for Incident Brain.
Seeds ~15 services (3-4 hop hierarchy), ~8 people, ~10 incidents (3+ similar),
~6 docs, ~4 decisions into 'company_graph' and isolated team memory graphs.
Uses Cypher MERGE commands for idempotent execution.
"""

import logging
from typing import Dict, Any, List
from app.db import db_manager
from app.config import settings

logger = logging.getLogger("incident_brain.seed")

SERVICES = [
    {"name": "web-frontend", "tier": "tier-1", "type": "frontend", "language": "TypeScript"},
    {"name": "api-gateway", "tier": "tier-1", "type": "gateway", "language": "Go"},
    {"name": "auth-service", "tier": "tier-1", "type": "core", "language": "Python"},
    {"name": "user-profile-service", "tier": "tier-2", "type": "backend", "language": "Go"},
    {"name": "order-service", "tier": "tier-1", "type": "backend", "language": "Java"},
    {"name": "payment-service", "tier": "tier-1", "type": "financial", "language": "Python"},
    {"name": "inventory-service", "tier": "tier-2", "type": "backend", "language": "Go"},
    {"name": "notification-service", "tier": "tier-3", "type": "async", "language": "Node.js"},
    {"name": "fraud-detector", "tier": "tier-2", "type": "ml", "language": "Python"},
    {"name": "billing-engine", "tier": "tier-2", "type": "financial", "language": "Java"},
    {"name": "shipping-coordinator", "tier": "tier-3", "type": "integration", "language": "Python"},
    {"name": "search-indexer", "tier": "tier-3", "type": "search", "language": "Java"},
    {"name": "recommendation-api", "tier": "tier-3", "type": "ml", "language": "Python"},
    {"name": "postgres-cluster", "tier": "tier-1", "type": "database", "engine": "PostgreSQL 16"},
    {"name": "redis-cache", "tier": "tier-1", "type": "cache", "engine": "Redis 7.2"},
    {"name": "kafka-broker", "tier": "tier-1", "type": "message_broker", "engine": "Kafka 3.6"},
]

DEPENDENCY_EDGES = [
    # (Downstream, Upstream) -> Downstream DEPENDS_ON Upstream
    ("web-frontend", "api-gateway"),
    ("api-gateway", "auth-service"),
    ("api-gateway", "order-service"),
    ("order-service", "auth-service"),
    ("order-service", "payment-service"),
    ("order-service", "inventory-service"),
    ("order-service", "kafka-broker"),
    ("payment-service", "fraud-detector"),
    ("payment-service", "billing-engine"),
    ("billing-engine", "postgres-cluster"),
    ("auth-service", "postgres-cluster"),
    ("auth-service", "redis-cache"),
    ("user-profile-service", "auth-service"),
    ("user-profile-service", "postgres-cluster"),
    ("notification-service", "kafka-broker"),
    ("shipping-coordinator", "order-service"),
    ("search-indexer", "inventory-service"),
    ("recommendation-api", "order-service"),
    ("recommendation-api", "redis-cache"),
]

TEAMS = [
    {"name": "core_platform", "lead": "Alice Chen", "slack_channel": "#team-core-platform"},
    {"name": "payments_squad", "lead": "Dave Miller", "slack_channel": "#team-payments"},
    {"name": "reliability_ops", "lead": "Elena Rostova", "slack_channel": "#team-sre"},
]

PEOPLE = [
    {"name": "Alice Chen", "role": "Staff Platform Engineer", "slack": "@alice.chen", "email": "alice@company.internal", "team": "core_platform"},
    {"name": "Bob Smith", "role": "Principal Security Engineer", "slack": "@bob.smith", "email": "bob@company.internal", "team": "core_platform"},
    {"name": "Carol Danvers", "role": "Senior Backend Engineer", "slack": "@carol.d", "email": "carol@company.internal", "team": "payments_squad"},
    {"name": "Dave Miller", "role": "Staff Payments Architect", "slack": "@dave.miller", "email": "dave@company.internal", "team": "payments_squad"},
    {"name": "Elena Rostova", "role": "Senior SRE Lead", "slack": "@elena.sre", "email": "elena@company.internal", "team": "reliability_ops"},
    {"name": "Fiona Gallagher", "role": "Database Reliability Engineer", "slack": "@fiona.db", "email": "fiona@company.internal", "team": "reliability_ops"},
    {"name": "George Vance", "role": "Senior DevOps Engineer", "slack": "@george.v", "email": "george@company.internal", "team": "core_platform"},
    {"name": "Hana Sato", "role": "Frontend & Gateway Lead", "slack": "@hana.sato", "email": "hana@company.internal", "team": "core_platform"},
]

OWNERSHIP = [
    ("Alice Chen", "auth-service"),
    ("Alice Chen", "redis-cache"),
    ("Bob Smith", "api-gateway"),
    ("Carol Danvers", "order-service"),
    ("Dave Miller", "payment-service"),
    ("Dave Miller", "billing-engine"),
    ("Elena Rostova", "notification-service"),
    ("Elena Rostova", "kafka-broker"),
    ("Fiona Gallagher", "postgres-cluster"),
    ("George Vance", "inventory-service"),
    ("Hana Sato", "web-frontend"),
    ("Hana Sato", "user-profile-service"),
]

INCIDENTS = [
    {
        "name": "INC-101",
        "title": "Auth Service PostgreSQL Connection Pool Exhaustion",
        "service": "auth-service",
        "severity": "P1",
        "resolved_at": "2026-08-10",
        "root_cause": "HikariCP pool limit of 20 connections exhausted by unclosed session in JWT validation hook during traffic surge",
        "fix": "Increased max pool size to 60, added explicit connection release timeout in finally block, deployed hotfix v2.4.1",
        "resolvers": ["Alice Chen", "Fiona Gallagher"],
    },
    {
        "name": "INC-102",
        "title": "Order Service DB Connection Pool Depletion",
        "service": "order-service",
        "severity": "P1",
        "resolved_at": "2026-08-28",
        "root_cause": "Long-running read transactions holding connection pool locks without query timeouts",
        "fix": "Applied PgBouncer connection multiplexer and set query_timeout = 5s in SQLAlchemy session config",
        "resolvers": ["Carol Danvers", "Fiona Gallagher"],
    },
    {
        "name": "INC-103",
        "title": "Billing Engine Connection Leak in Batch Reconciliation",
        "service": "billing-engine",
        "severity": "P2",
        "resolved_at": "2026-09-04",
        "root_cause": "Celery task retries spawning orphan Postgres pool handles without closing dead sockets",
        "fix": "Enabled pool_pre_ping and TCP keepalives; reduced max worker concurrency from 32 to 16",
        "resolvers": ["Dave Miller"],
    },
    {
        "name": "INC-104",
        "title": "Redis Cache Out of Memory Eviction Storm",
        "service": "redis-cache",
        "severity": "P1",
        "resolved_at": "2026-09-12",
        "root_cause": "Session TTL missing on user permissions cache, triggering allkeys-lru eviction across auth and orders",
        "fix": "Added mandatory 1-hour TTL to permission keys and increased maxmemory to 8GB",
        "resolvers": ["Alice Chen"],
    },
    {
        "name": "INC-105",
        "title": "Stripe Webhook Delivery Latency in Payment Service",
        "service": "payment-service",
        "severity": "P1",
        "resolved_at": "2026-09-19",
        "root_cause": "Synchronous webhook processing blocked on downstream invoice generation",
        "fix": "Decoupled webhook ingestion with Kafka topic payment-events for async background handling",
        "resolvers": ["Dave Miller", "Carol Danvers"],
    },
    {
        "name": "INC-106",
        "title": "API Gateway Rate Limit Memory Saturation",
        "service": "api-gateway",
        "severity": "P2",
        "resolved_at": "2026-09-25",
        "root_cause": "Token bucket counter key explosion from bot traffic",
        "fix": "Migrated rate limiter to sliding window Redis script with ip-hash sharding",
        "resolvers": ["Bob Smith"],
    },
    {
        "name": "INC-107",
        "title": "Inventory Service Redis Cluster Split-Brain",
        "service": "inventory-service",
        "severity": "P1",
        "resolved_at": "2026-10-01",
        "root_cause": "Network partition between AWS us-east-1a and 1b causing conflicting master elections",
        "fix": "Enforced min-replicas-to-write 2 and adjusted cluster-node-timeout to 10s",
        "resolvers": ["George Vance", "Elena Rostova"],
    },
    {
        "name": "INC-108",
        "title": "Kafka Consumer Lag in Notification Service",
        "service": "notification-service",
        "severity": "P2",
        "resolved_at": "2026-10-05",
        "root_cause": "Poison pill payload in order-notifications topic causing crash loop",
        "fix": "Configured Dead Letter Queue (DLQ) with exponential backoff retry topic",
        "resolvers": ["Elena Rostova"],
    },
    {
        "name": "INC-109",
        "title": "Search Indexer Elastic Bulk Ingestion Throttle",
        "service": "search-indexer",
        "severity": "P3",
        "resolved_at": "2026-10-09",
        "root_cause": "429 Elasticsearch bulk queue depth exceeded during nightly catalog sync",
        "fix": "Scaled search worker buffer and tuned bulk size to 5MB batches",
        "resolvers": ["Hana Sato"],
    },
    {
        "name": "INC-110",
        "title": "User Profile Service JWT Clock Skew Authentication Rejections",
        "service": "user-profile-service",
        "severity": "P2",
        "resolved_at": "2026-10-12",
        "root_cause": "NTP drift on VM cluster node 04 caused clock skew exceeding 120s",
        "fix": "Synced chrony NTP servers and added 60-second leeway in jwt.decode()",
        "resolvers": ["Alice Chen", "Hana Sato"],
    },
]

SIMILAR_INCIDENT_LINKS = [
    ("INC-101", "INC-102"),
    ("INC-102", "INC-103"),
    ("INC-101", "INC-103"),
    ("INC-104", "INC-107"),
]

DOCS = [
    {
        "name": "DOC-001",
        "title": "Runbook: Auth & Database Connection Pool Recovery",
        "url": "https://wiki.internal/runbooks/auth-db-pool",
        "summary": "Step-by-step procedure to diagnose HikariCP connection leaks, dump thread traces, and tune pool size.",
        "service": "auth-service"
    },
    {
        "name": "DOC-002",
        "title": "Runbook: Redis Cache Memory & Cluster Failover",
        "url": "https://wiki.internal/runbooks/redis-failover",
        "summary": "Emergency response guide for Redis OOM evictions, key TTL audits, and replica failover.",
        "service": "redis-cache"
    },
    {
        "name": "DOC-003",
        "title": "Standard Operating Procedure: P1 Incident Triage & Escalation",
        "url": "https://wiki.internal/sop/p1-triage",
        "summary": "Protocol for incident commander assignment, status page updates, and Slack bridge orchestration.",
        "service": "api-gateway"
    },
    {
        "name": "DOC-004",
        "title": "Runbook: Payment Webhook Latency & DLQ Replay",
        "url": "https://wiki.internal/runbooks/payment-webhooks",
        "summary": "How to inspect stalled webhook pipelines, drain dead letter queues, and verify idempotency keys.",
        "service": "payment-service"
    },
    {
        "name": "DOC-005",
        "title": "Architecture Guide: Zero-Downtime Database Maintenance",
        "url": "https://wiki.internal/arch/db-maintenance",
        "summary": "Guidelines on PgBouncer pooling, lock timeouts, and zero-downtime schema migrations.",
        "service": "postgres-cluster"
    },
    {
        "name": "DOC-006",
        "title": "Runbook: Kafka Consumer Lag & Poison Pill Isolation",
        "url": "https://wiki.internal/runbooks/kafka-dlq",
        "summary": "Detecting partition skew, skipping poisoned consumer records, and replaying to staging topics.",
        "service": "kafka-broker"
    },
]

DECISIONS = [
    {
        "name": "ADR-001",
        "title": "ADR-001: Connection Pool Sizing and PgBouncer Multiplexing",
        "summary": "Caps microservice HikariCP pools to 30 per pod with centralized PgBouncer to prevent DB starvation.",
        "service": "auth-service"
    },
    {
        "name": "ADR-002",
        "title": "ADR-002: Asynchronous Payment Webhook Ingestion via Kafka",
        "summary": "Prohibits synchronous 3rd party processing during HTTP requests to safeguard SLA.",
        "service": "payment-service"
    },
    {
        "name": "ADR-003",
        "title": "ADR-003: Redis Sentinel Topology with Enforced Key TTL",
        "summary": "Mandates explicit TTLs on all cache writes and sentinel auto-failover in < 3 seconds.",
        "service": "redis-cache"
    },
    {
        "name": "ADR-004",
        "title": "ADR-004: JWT Clock Skew Leeway and Distributed Revocation",
        "summary": "Defines 60s validation leeway for VM clock drift and Redis bloom filter for instant token invalidation.",
        "service": "auth-service"
    },
]


def seed_database(reset: bool = False):
    """Idempotently populates the company graph and team memory graphs with synthetic knowledge."""
    logger.info("Starting database seed...")
    comp_graph = settings.COMPANY_GRAPH
    
    if reset:
        try:
            g = db_manager.select_graph(comp_graph)
            g.delete()
        except Exception as e:
            logger.warning(f"Could not delete graph {comp_graph}: {e}")

    # 1. Services
    for s in SERVICES:
        cypher = "MERGE (s:Service {name: $name}) SET s.tier = $tier, s.type = $type, s.language = $language"
        params = {
            "name": s["name"],
            "tier": s.get("tier", "tier-2"),
            "type": s.get("type", "service"),
            "language": s.get("language", s.get("engine", "Python"))
        }
        db_manager.query(comp_graph, cypher, params)

    # 2. Dependencies
    for src, dst in DEPENDENCY_EDGES:
        cypher = """
        MATCH (src:Service {name: $src}), (dst:Service {name: $dst})
        MERGE (src)-[r:DEPENDS_ON]->(dst)
        """
        db_manager.query(comp_graph, cypher, {"src": src, "dst": dst})

    # 3. Teams
    for t in TEAMS:
        cypher = "MERGE (tm:Team {name: $name}) SET tm.lead = $lead, tm.slack_channel = $slack_channel"
        db_manager.query(comp_graph, cypher, t)

    # 4. People and Team Membership
    for p in PEOPLE:
        cypher = """
        MERGE (person:Person {name: $name})
        SET person.role = $role, person.slack = $slack, person.email = $email
        WITH person
        MATCH (tm:Team {name: $team})
        MERGE (person)-[:MEMBER_OF]->(tm)
        """
        db_manager.query(comp_graph, cypher, p)

    # 5. Service Ownership
    for person_name, service_name in OWNERSHIP:
        cypher = """
        MATCH (p:Person {name: $person}), (s:Service {name: $service})
        MERGE (p)-[:OWNS]->(s)
        """
        db_manager.query(comp_graph, cypher, {"person": person_name, "service": service_name})

    # 6. Incidents & Affected Services & Resolvers
    for inc in INCIDENTS:
        cypher = """
        MERGE (i:Incident {name: $name})
        SET i.title = $title, i.severity = $severity, i.resolved_at = $resolved_at,
            i.root_cause = $root_cause, i.fix = $fix
        WITH i
        MATCH (s:Service {name: $service})
        MERGE (i)-[:AFFECTED]->(s)
        """
        params = {
            "name": inc["name"],
            "title": inc["title"],
            "severity": inc["severity"],
            "resolved_at": inc["resolved_at"],
            "root_cause": inc["root_cause"],
            "fix": inc["fix"],
            "service": inc["service"]
        }
        db_manager.query(comp_graph, cypher, params)

        # Resolvers (WORKED_ON)
        for resolver in inc["resolvers"]:
            r_cypher = """
            MATCH (p:Person {name: $person}), (i:Incident {name: $name})
            MERGE (p)-[:WORKED_ON]->(i)
            """
            db_manager.query(comp_graph, r_cypher, {"person": resolver, "name": inc["name"]})

    # 7. Similar Incident Links (:SIMILAR_TO)
    for inc1, inc2 in SIMILAR_INCIDENT_LINKS:
        cypher = """
        MATCH (i1:Incident {name: $src}), (i2:Incident {name: $dst})
        MERGE (i1)-[:SIMILAR_TO]->(i2)
        """
        db_manager.query(comp_graph, cypher, {"src": inc1, "dst": inc2})

    # 8. Docs (:DOCUMENTED_IN, :ABOUT)
    for d in DOCS:
        cypher = """
        MERGE (doc:Doc {name: $name})
        SET doc.title = $title, doc.url = $url, doc.summary = $summary
        WITH doc
        MATCH (s:Service {name: $service})
        MERGE (doc)-[:ABOUT]->(s)
        MERGE (s)-[:DOCUMENTED_IN]->(doc)
        """
        db_manager.query(comp_graph, cypher, d)

    # 9. Decisions (:SHAPED)
    for dec in DECISIONS:
        cypher = """
        MERGE (d:Decision {name: $name})
        SET d.title = $title, d.summary = $summary
        WITH d
        MATCH (s:Service {name: $service})
        MERGE (d)-[:SHAPED]->(s)
        """
        db_manager.query(comp_graph, cypher, dec)

    # 10. Team Memory Graphs (Track 2: Agent memory across sessions)
    for t in TEAMS:
        mem_graph = f"memory_{t['name']}"
        init_cypher = """
        MERGE (tm:TeamMemory {team: $team})
        SET tm.created_at = '2026-10-01', tm.incident_count = 0
        """
        db_manager.query(mem_graph, init_cypher, {"team": t["name"]})

    logger.info("Database seeding completed successfully.")


if __name__ == "__main__":
    seed_database(reset=True)
    print("Seed finished.")
