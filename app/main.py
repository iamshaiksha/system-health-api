"""
System Health Check API
Evaluates health of interdependent components modeled as a DAG.
Author: Abdul Rahiman Shaik
"""

import asyncio
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.models import SystemInput, SystemHealthReport, ComponentHealth, HealthStatus
from app.visualizer import generate_dag_image
from app.observability import setup_logging

logger = logging.getLogger(__name__)

# Prometheus metrics
HEALTH_CHECK_REQUESTS = Counter(
    "health_check_requests_total", "Total health check API requests"
)
HEALTH_CHECK_DURATION = Histogram(
    "health_check_duration_seconds", "Time spent evaluating system health"
)
COMPONENT_STATUS = Counter(
    "component_health_status_total",
    "Component health check outcomes",
    ["component", "status"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("System Health Check API starting up")
    yield
    logger.info("System Health Check API shutting down")


app = FastAPI(
    title="System Health Check API",
    description="Evaluates health of interdependent system components modeled as a DAG",
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# DAG construction & BFS traversal
# ─────────────────────────────────────────────

def build_adjacency(nodes: list, edges: list) -> dict[str, list[str]]:
    """Build adjacency list from node/edge input."""
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for edge in edges:
        if edge.source not in adj:
            raise ValueError(f"Unknown source node: {edge.source}")
        if edge.target not in adj:
            raise ValueError(f"Unknown target node: {edge.target}")
        adj[edge.source].append(edge.target)
    return adj


def bfs_order(adj: dict[str, list[str]], node_ids: list[str]) -> list[str]:
    """Return BFS traversal order starting from root nodes (nodes with no incoming edges)."""
    in_degree = {n: 0 for n in node_ids}
    for src, targets in adj.items():
        for t in targets:
            in_degree[t] += 1

    queue = deque(n for n in node_ids if in_degree[n] == 0)
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in adj.get(node, []):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(node_ids):
        raise ValueError("Cycle detected in graph — input must be a DAG")

    return order


# ─────────────────────────────────────────────
# Async health evaluation
# ─────────────────────────────────────────────

async def evaluate_component(component, client: httpx.AsyncClient) -> ComponentHealth:
    """
    Asynchronously probe a single component's health.

    Strategy:
    - If the component has a health_url, perform an HTTP GET and treat 2xx as healthy.
    - Otherwise simulate based on the component's reported status field (for demo/testing).
    """
    start = time.monotonic()
    try:
        if component.health_url:
            resp = await client.get(component.health_url, timeout=5.0)
            elapsed = time.monotonic() - start
            if resp.status_code < 300:
                status = HealthStatus.HEALTHY
                message = f"HTTP {resp.status_code}"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"HTTP {resp.status_code}"
        else:
            # No URL provided — use declared status for demo purposes
            await asyncio.sleep(0.01)  # simulate async I/O
            elapsed = time.monotonic() - start
            declared = (component.status or "healthy").lower()
            status = HealthStatus.HEALTHY if declared == "healthy" else HealthStatus.UNHEALTHY
            message = f"Declared status: {declared}"

    except Exception as exc:
        elapsed = time.monotonic() - start
        status = HealthStatus.UNHEALTHY
        message = f"Error: {exc}"

    COMPONENT_STATUS.labels(component=component.id, status=status.value).inc()
    logger.info(
        "component_health_evaluated",
        extra={"component": component.id, "status": status.value, "latency_ms": round(elapsed * 1000, 2)},
    )

    return ComponentHealth(
        id=component.id,
        name=component.name,
        status=status,
        message=message,
        latency_ms=round(elapsed * 1000, 2),
    )


async def evaluate_all(components_in_bfs_order: list, node_map: dict) -> list[ComponentHealth]:
    """Run all health checks concurrently, respecting BFS layer grouping."""
    async with httpx.AsyncClient() as client:
        tasks = [
            evaluate_component(node_map[cid], client)
            for cid in components_in_bfs_order
        ]
        results = await asyncio.gather(*tasks)
    return list(results)


# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@app.post("/health-check", response_model=SystemHealthReport, summary="Evaluate system health")
async def health_check(payload: SystemInput):
    """
    Accept a DAG-shaped JSON payload, traverse it via BFS,
    asynchronously evaluate each component, and return an aggregated report.
    """
    HEALTH_CHECK_REQUESTS.inc()

    with HEALTH_CHECK_DURATION.time():
        try:
            node_map = {n.id: n for n in payload.nodes}
            adj = build_adjacency(payload.nodes, payload.edges)
            order = bfs_order(adj, list(node_map.keys()))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        results = await evaluate_all(order, node_map)

    healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
    total = len(results)
    overall = HealthStatus.HEALTHY if healthy_count == total else HealthStatus.UNHEALTHY

    logger.info(
        "system_health_summary",
        extra={"total": total, "healthy": healthy_count, "overall": overall.value},
    )

    return SystemHealthReport(
        overall_status=overall,
        total_components=total,
        healthy_count=healthy_count,
        unhealthy_count=total - healthy_count,
        components=results,
        bfs_order=order,
    )


@app.post("/health-check/visualize", summary="Evaluate and visualize DAG")
async def health_check_visualize(payload: SystemInput):
    """
    Same as /health-check but additionally returns a base64-encoded PNG
    of the DAG with unhealthy nodes highlighted in red.
    """
    report_response = await health_check(payload)
    result_map = {c.id: c.status for c in report_response.components}

    img_b64 = generate_dag_image(
        nodes=payload.nodes,
        edges=payload.edges,
        health_map=result_map,
    )

    return {
        "report": report_response,
        "dag_image_base64": img_b64,
    }


@app.get("/health", summary="Liveness probe")
async def liveness():
    return {"status": "ok"}


@app.get("/ready", summary="Readiness probe")
async def readiness():
    return {"status": "ready"}


@app.get("/metrics", summary="Prometheus metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ─────────────────────────────────────────────
# Global exception handler
# ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
