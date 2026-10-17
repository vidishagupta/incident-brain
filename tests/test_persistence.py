import pytest
from app.seed import seed_database
from app.tools import log_incident
from app.db import db_manager


@pytest.fixture(autouse=True)
def init_db():
    seed_database(reset=True)


def test_team_isolation():
    """Verifies that an incident logged in memory_core_platform is isolated from memory_payments_squad."""
    # Log incident for core_platform
    res1 = log_incident(
        title="Core Platform Secret Rotation Blocker",
        service="auth-service",
        root_cause="Vault token expired",
        fix="Refreshed AppRole lease",
        team="core_platform",
        severity="P2"
    )
    inc_id = res1["result"]["incident_id"]

    # Check core_platform memory graph
    core_snap = db_manager.get_snapshot("memory_core_platform")
    core_node_ids = [n["id"] for n in core_snap["nodes"]]
    assert inc_id in core_node_ids

    # Check payments_squad memory graph
    payments_snap = db_manager.get_snapshot("memory_payments_squad")
    payments_node_ids = [n["id"] for n in payments_snap["nodes"]]
    # Should NOT be in payments_squad memory graph
    assert inc_id not in payments_node_ids


def test_persistence_across_queries():
    """Verifies that logged incidents remain searchable by similar_incidents tools."""
    from app.tools import similar_incidents

    res = log_incident(
        title="Database Connection Pool Starvation Incident",
        service="auth-service",
        root_cause="HikariCP pool locked by deadlock",
        fix="Terminated rogue backend process",
        team="core_platform",
        severity="P1"
    )

    sim = similar_incidents("auth-service", "deadlock")
    titles = [i["title"] for i in sim["result"]]
    assert any("Database Connection Pool Starvation" in t for t in titles)
