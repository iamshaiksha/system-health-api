"""
Data models for the System Health Check API.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class NodeInput(BaseModel):
    id: str = Field(..., description="Unique identifier for this component")
    name: str = Field(..., description="Human-readable component name")
    health_url: Optional[str] = Field(
        None, description="Optional HTTP endpoint to probe for health"
    )
    status: Optional[str] = Field(
        None, description="Declared status used when health_url is absent (demo mode)"
    )

    model_config = {"json_schema_extra": {"example": {"id": "db", "name": "Database", "health_url": None, "status": "healthy"}}}


class EdgeInput(BaseModel):
    source: str = Field(..., description="ID of the upstream (dependency) node")
    target: str = Field(..., description="ID of the downstream (dependent) node")

    model_config = {"json_schema_extra": {"example": {"source": "db", "target": "api"}}}


class SystemInput(BaseModel):
    nodes: list[NodeInput] = Field(..., description="List of system components")
    edges: list[EdgeInput] = Field(..., description="Directed dependency edges")

    model_config = {
        "json_schema_extra": {
            "example": {
                "nodes": [
                    {"id": "db", "name": "Database", "status": "healthy"},
                    {"id": "cache", "name": "Redis Cache", "status": "healthy"},
                    {"id": "api", "name": "API Server", "status": "unhealthy"},
                    {"id": "web", "name": "Web Frontend", "status": "healthy"},
                ],
                "edges": [
                    {"source": "db", "target": "api"},
                    {"source": "cache", "target": "api"},
                    {"source": "api", "target": "web"},
                ],
            }
        }
    }


class ComponentHealth(BaseModel):
    id: str
    name: str
    status: HealthStatus
    message: str
    latency_ms: float


class SystemHealthReport(BaseModel):
    overall_status: HealthStatus
    total_components: int
    healthy_count: int
    unhealthy_count: int
    components: list[ComponentHealth]
    bfs_order: list[str] = Field(..., description="BFS traversal order of component IDs")
