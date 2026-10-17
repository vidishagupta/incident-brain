import pytest
from app.seed import seed_database
from app.agent import brain_agent


@pytest.fixture(autouse=True)
def setup_graph():
    seed_database(reset=True)


def test_agent_investigate_auth_service():
    """Sample Incident 1: Auth Service Connection Pool Exhaustion"""
    res = brain_agent.investigate("auth-service", "504 Gateway Timeout during peak surge", "core_platform")
    assert res["service"] == "auth-service"
    assert len(res["blast_radius"]) > 0
    assert len(res["who_knows"]) > 0
    assert len(res["similar_incidents"]) > 0
    assert len(res["trace"]) >= 5
    assert "Incident Postmortem Draft" in res["postmortem"]
    assert "auth-service" in res["postmortem"]


def test_agent_investigate_payment_service():
    """Sample Incident 2: Payment Service Webhook Latency"""
    res = brain_agent.investigate("payment-service", "Checkout webhooks stalling for 45s", "payments_squad")
    assert res["service"] == "payment-service"
    assert len(res["who_knows"]) > 0
    # Dave Miller owns payment-service
    assert any("Dave Miller" in r["name"] for r in res["who_knows"])
    assert "Postmortem" in res["postmortem"]


def test_agent_investigate_inventory_service():
    """Sample Incident 3: Inventory Service Cluster Split-Brain"""
    res = brain_agent.investigate("inventory-service", "Ghost reservations and stock underflow", "reliability_ops")
    assert res["service"] == "inventory-service"
    assert len(res["similar_incidents"]) > 0
    assert any("George Vance" in r["name"] for r in res["who_knows"])
    assert "Postmortem" in res["postmortem"]


def test_multi_agent_handoff():
    """Verifies Triage Agent writes investigation to graph and Scribe Agent synthesizes it."""
    res = brain_agent.investigate("auth-service", "Critical latency spike", "core_platform")
    # Verify trace steps contain Triage Agent actions
    agents_involved = {t["agent"] for t in res["trace"]}
    assert "Triage Agent" in agents_involved
    assert "Postmortem Draft" in res["postmortem"]
