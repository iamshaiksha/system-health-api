"""
DAG Visualizer — generates a PNG of the dependency graph
with unhealthy nodes highlighted in red.

Uses matplotlib + networkx (lightweight, no graphviz binary needed).
"""

import base64
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")  # headless backend — no display needed
    import matplotlib.pyplot as plt
    import networkx as nx

    _VIZ_AVAILABLE = True
except ImportError:
    _VIZ_AVAILABLE = False
    logger.warning("matplotlib/networkx not available; DAG visualization disabled")


def generate_dag_image(nodes: list, edges: list, health_map: dict) -> Optional[str]:
    """
    Build a directed graph, lay it out hierarchically, render it,
    and return a base64-encoded PNG string.

    Healthy nodes → green, Unhealthy → red, Unknown → grey.
    """
    if not _VIZ_AVAILABLE:
        return None

    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node.id, label=node.name)
    for edge in edges:
        G.add_edge(edge.source, edge.target)

    # Hierarchical layout via topological sort
    try:
        pos = _hierarchical_layout(G)
    except Exception:
        pos = nx.spring_layout(G, seed=42)

    node_colors = []
    for node in G.nodes():
        status = health_map.get(node, "unknown")
        status_val = status.value if hasattr(status, "value") else str(status)
        if status_val == "healthy":
            node_colors.append("#4CAF50")   # green
        elif status_val == "unhealthy":
            node_colors.append("#F44336")   # red
        else:
            node_colors.append("#9E9E9E")   # grey

    labels = {n.id: f"{n.name}\n({n.id})" for n in nodes}

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_facecolor("#1E1E2E")
    fig.patch.set_facecolor("#1E1E2E")

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=2200, ax=ax, alpha=0.95)
    nx.draw_networkx_labels(G, pos, labels=labels, font_color="white", font_size=8, ax=ax)
    nx.draw_networkx_edges(
        G, pos, edge_color="#AAAAAA", arrows=True,
        arrowstyle="-|>", arrowsize=20, ax=ax,
        connectionstyle="arc3,rad=0.05", width=1.5,
    )

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4CAF50", label="Healthy"),
        Patch(facecolor="#F44336", label="Unhealthy"),
        Patch(facecolor="#9E9E9E", label="Unknown"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", facecolor="#2D2D3E", labelcolor="white")
    ax.set_title("System Dependency DAG — Health Status", color="white", fontsize=13, pad=15)
    ax.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _hierarchical_layout(G: "nx.DiGraph") -> dict:
    """Assign (x, y) positions based on topological layers."""
    layers: dict[str, int] = {}
    for node in nx.topological_sort(G):
        preds = list(G.predecessors(node))
        layers[node] = max((layers[p] for p in preds), default=-1) + 1

    layer_nodes: dict[int, list] = {}
    for node, layer in layers.items():
        layer_nodes.setdefault(layer, []).append(node)

    pos = {}
    for layer, nodes_in_layer in layer_nodes.items():
        n = len(nodes_in_layer)
        for i, node in enumerate(nodes_in_layer):
            pos[node] = (layer * 2.5, -(i - (n - 1) / 2) * 2.0)

    return pos
