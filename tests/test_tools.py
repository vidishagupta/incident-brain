import pytest
from app.seed import seed_database
from app.tools import (
    blast_radius,
    risk_rank,
    who_knows,
    similar_incidents,
    explain_path,
    log_incident,
    get_docs,
    fuzzy_match_service
)


@pytest.fixture(autouse=True)
def setup_graph():
    seed_database(reset=True)


def test_fuzzy_match():
    assert fuzzy_match_service("auth") == "auth-service"
    assert fuzzy_match_service("payments") == "payment-service"
    assert fuzzy_match_service("orders") == "order-service"
    assert fuzzy_match_service("gateway") == "api-gateway"


def test_blast_radius():
    res = blast_radius("auth-service")
    assert res["service"] == "auth-service"
    assert len(res["result"]) > 0
    services = [b["service"] for b in res["result"]]
    # api-gateway or order-service depend on auth-service
    assert "api-gateway" in services or "order-service" in services
    assert res["nodes"]
    assert res["cypher"]
    assert "length(path)" in res["cypher"]


def test_risk_rank():
    res = risk_rank()
    assert len(res["result"]) > 0
    top = res["result"][0]
    assert "service" in top
    assert "score" in top
    assert "algorithm" in top


def test_who_knows():
    res = who_knows("auth-service")
    assert len(res["result"]) > 0
    # Alice Chen is the primary owner
    assert any("Alice Chen" in r["name"] for r in res["result"])
    assert res["cypher"]


def test_similar_incidents():
    res = similar_incidents("auth-service", "connection pool")
    assert len(res["result"]) > 0
    inc = res["result"][0]
    assert "root_cause" in inc
    assert "fix" in inc
    assert "severity" in inc


def test_explain_path():
    res = explain_path("auth-service", "web-frontend")
    assert res["result"]["hops"] >= 1
    assert "auth-service" in res["result"]["path"]


def test_get_docs():
    res = get_docs("auth-service")
    assert len(res["result"]) > 0
    assert any("Runbook" in d.get("title", "") or "Pool" in d.get("title", "") for d in res["result"])


def test_log_incident():
    res = log_incident(
        title="Test Incident Connection Spike",
        service="auth-service",
        root_cause="HikariCP thread exhaustion",
        fix="Scaled max pool size to 50",
        team="core_platform",
        severity="P1"
    )
    assert res["result"]["status"] == "persisted"
    assert "INC-" in res["result"]["incident_id"]
