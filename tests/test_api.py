import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed_database

client = TestClient(app)


@pytest.fixture(autouse=True)
def init_db():
    seed_database(reset=True)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "falkordb_connected" in data
    assert "agent_mode" in data


def test_serve_index():
    res = client.get("/")
    assert res.status_code == 200
    assert "Incident Brain" in res.text


def test_api_investigate():
    payload = {
        "service": "auth-service",
        "symptoms": "504 Gateway Timeout and connection leaks",
        "team": "core_platform"
    }
    res = client.post("/api/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "auth-service"
    assert "blast_radius" in data
    assert "who_knows" in data
    assert "postmortem" in data
    assert "trace" in data


def test_api_incidents():
    payload = {
        "title": "Auth Token Expiry Skew",
        "service": "auth-service",
        "root_cause": "NTP clock skew",
        "fix": "Synced chrony NTP servers",
        "team": "core_platform",
        "severity": "P2"
    }
    res = client.post("/api/incidents", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["result"]["status"] == "persisted"


def test_api_graph():
    res = client.get("/api/graph")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) > 0


def test_api_memory():
    res = client.get("/api/memory?team=core_platform")
    assert res.status_code == 200
    data = res.json()
    assert data["team"] == "core_platform"
    assert "snapshot" in data


def test_api_reset_demo():
    res = client.post("/api/reset-demo")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "reset_complete"
