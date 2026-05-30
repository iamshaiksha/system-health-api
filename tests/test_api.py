"""
Tests for the System Health Check API.
Covers: DAG construction, BFS ordering, cycle detection,
health evaluation, and API endpoint contracts.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app, build_adjacency, bfs_order
from app.models import NodeInput, EdgeInput

client = TestClient(app)


# ─────────────────────────────────────────────
# Unit tests — DAG logic
# ─────────────────────────────────────────────

def _node(id_, name="Test", status="healthy"):
    return NodeInput(id=id_, name=name, status=status)


def _edge(src, tgt):
    return EdgeInput(source=src, target=tgt)


def test_build_adjacency_simple():
    nodes = [_node("a"), _node("b"), _node("c")]
    edges = [_edge("a", "b"), _edge("b", "c")]
    adj = build_adjacency(nodes, edges)
    assert adj["a"] == ["b"]
    assert adj["b"] == ["c"]
    assert adj["c"] == []


def test_build_adjacency_unknown_node():
    nodes = [_node("a")]
    with pytest.raises(ValueError, match="Unknown"):
        build_adjacency(nodes, [_edge("a", "z")])


def test_bfs_order_linear():
    adj = {"a": ["b"], "b": ["c"], "c": []}
    order = bfs_order(adj, ["a", "b", "c"])
    assert order == ["a", "b", "c"]


def test_bfs_order_diamond():
    # a → b, a → c, b → d, c → d
    adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
    order = bfs_order(adj, ["a", "b", "c", "d"])
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_bfs_order_cycle_detection():
    adj = {"a": ["b"], "b": ["a"]}
    with pytest.raises(ValueError, match="Cycle"):
        bfs_order(adj, ["a", "b"])


def test_bfs_order_disconnected():
    # Two independent chains: x→y and p→q
    adj = {"x": ["y"], "y": [], "p": ["q"], "q": []}
    order = bfs_order(adj, ["x", "y", "p", "q"])
    assert order.index("x") < order.index("y")
    assert order.index("p") < order.index("q")


# ─────────────────────────────────────────────
# Integration tests — API
# ─────────────────────────────────────────────

SAMPLE_PAYLOAD = {
    "nodes": [
        {"id": "db", "name": "Database", "status": "healthy"},
        {"id": "cache", "name": "Redis", "status": "healthy"},
        {"id": "api", "name": "API Server", "status": "unhealthy"},
        {"id": "web", "name": "Web Frontend", "status": "healthy"},
    ],
    "edges": [
        {"source": "db", "target": "api"},
        {"source": "cache", "target": "api"},
        {"source": "api", "target": "web"},
    ],
}


def test_health_check_endpoint_returns_200():
    resp = client.post("/health-check", json=SAMPLE_PAYLOAD)
    assert resp.status_code == 200


def test_health_check_overall_status_unhealthy():
    resp = client.post("/health-check", json=SAMPLE_PAYLOAD)
    data = resp.json()
    assert data["overall_status"] == "unhealthy"
    assert data["unhealthy_count"] == 1
    assert data["healthy_count"] == 3


def test_health_check_bfs_order_respected():
    resp = client.post("/health-check", json=SAMPLE_PAYLOAD)
    order = resp.json()["bfs_order"]
    # db and cache must appear before api; api before web
    assert order.index("db") < order.index("api")
    assert order.index("cache") < order.index("api")
    assert order.index("api") < order.index("web")


def test_health_check_all_healthy():
    payload = {
        "nodes": [
            {"id": "a", "name": "A", "status": "healthy"},
            {"id": "b", "name": "B", "status": "healthy"},
        ],
        "edges": [{"source": "a", "target": "b"}],
    }
    resp = client.post("/health-check", json=payload)
    data = resp.json()
    assert data["overall_status"] == "healthy"
    assert data["unhealthy_count"] == 0


def test_health_check_cycle_returns_422():
    payload = {
        "nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }
    resp = client.post("/health-check", json=payload)
    assert resp.status_code == 422


def test_health_check_single_node():
    payload = {
        "nodes": [{"id": "lone", "name": "Lone Service", "status": "healthy"}],
        "edges": [],
    }
    resp = client.post("/health-check", json=payload)
    assert resp.status_code == 200
    assert resp.json()["total_components"] == 1


def test_liveness_probe():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readiness_probe():
    resp = client.get("/ready")
    assert resp.status_code == 200


def test_metrics_endpoint():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"health_check_requests_total" in resp.content
