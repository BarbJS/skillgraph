"""Optional, dependency-free SkillGraph visualization for Streamlit."""

from __future__ import annotations

import html
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def graph_enabled() -> bool:
    return os.getenv("SKILLGRAPH_GRAPH_ENABLED", "true").casefold() == "true"


def build_graph_data(data_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Build public graph data from synthetic competency/training catalogs."""
    root = Path(data_dir)
    competencies = pd.read_csv(root / "competencias.csv")
    trainings = pd.read_csv(root / "treinamentos.csv")
    nodes: list[dict[str, Any]] = []
    related: dict[str, list[str]] = {}
    for row in trainings.to_dict("records"):
        competency_id = str(row.get("competencia_relacionada", ""))
        title = str(row.get("titulo", ""))
        if competency_id and title:
            related.setdefault(competency_id, []).append(title)
    for index, row in enumerate(competencies.to_dict("records")):
        competency_id = str(row.get("competencia_id", ""))
        name = str(row.get("nome", ""))
        if not competency_id or not name:
            continue
        nodes.append(
            {
                "id": competency_id,
                "label": name,
                "category": str(row.get("categoria", "")),
                "minimum": str(row.get("nivel_obrigatorio_minimo", "")),
                "trainings": related.get(competency_id, []),
                "index": index,
            }
        )
    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    by_category: dict[str, list[str]] = {}
    for node in nodes:
        by_category.setdefault(node["category"], []).append(node["id"])
    for ids in by_category.values():
        for left, right in zip(ids, ids[1:]):
            key = tuple(sorted((left, right)))
            if key not in seen:
                seen.add(key)
                edges.append({"source": key[0], "target": key[1]})
    return {"nodes": nodes, "edges": edges}


def _svg(data: dict[str, list[dict[str, Any]]]) -> str:
    nodes = data["nodes"]
    edges = data["edges"]
    width, height = 920, 470
    center_x, center_y = width / 2, height / 2
    radius = min(180, max(100, len(nodes) * 8))
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        angle = (2 * math.pi * index / max(len(nodes), 1)) - math.pi / 2
        positions[node["id"]] = (
            center_x + radius * math.cos(angle),
            center_y + radius * math.sin(angle),
        )
    colors = {"Técnica": "#60a5fa", "Comportamental": "#fbbf24", "Gestão": "#c084fc"}
    lines = []
    for edge in edges:
        x1, y1 = positions[edge["source"]]
        x2, y2 = positions[edge["target"]]
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" />'
        )
    circles = []
    for node in nodes:
        x, y = positions[node["id"]]
        degree = sum(node["id"] in (edge["source"], edge["target"]) for edge in edges)
        size = 13 + min(degree, 4) * 2
        color = colors.get(node["category"], "#94a3b8")
        title = html.escape(
            f"{node['label']} | {node['category']} | mínimo {node['minimum']} | "
            f"{len(node['trainings'])} treinamento(s)"
        )
        label = html.escape(node["label"])
        circles.append(
            f'<g class="node"><title>{title}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="{size}" fill="{color}" />'
            f'<text x="{x:.1f}" y="{y + size + 16:.1f}">{label}</text></g>'
        )
    return f"""
    <div class="skillgraph-wrap">
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="Grafo de competências">
        <g class="edges">{''.join(lines)}</g><g class="nodes">{''.join(circles)}</g>
      </svg>
      <div class="legend"><span><i class="tech"></i>Técnica</span><span><i class="behavior"></i>Comportamental</span><span><i class="management"></i>Gestão</span></div>
    </div>
    <style>
      .skillgraph-wrap {{ background:#111827; border:1px solid #263246; border-radius:16px; padding:10px; overflow:hidden; }}
      svg {{ width:100%; height:auto; min-height:360px; }}
      .edges line {{ stroke:#64748b; stroke-opacity:.42; stroke-width:1.5; }}
      .node circle {{ stroke:#f8fafc; stroke-opacity:.8; stroke-width:1.2; cursor:pointer; transition:transform .2s, stroke-width .2s; }}
      .node:hover circle {{ stroke-width:3; transform:scale(1.12); transform-origin:center; }}
      .node text {{ fill:#e5e7eb; font:11px sans-serif; text-anchor:middle; pointer-events:none; }}
      .legend {{ display:flex; gap:18px; flex-wrap:wrap; color:#cbd5e1; font:12px sans-serif; padding:4px 8px 8px; }}
      .legend i {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; }}
      .tech {{ background:#60a5fa; }} .behavior {{ background:#fbbf24; }} .management {{ background:#c084fc; }}
    </style>
    """


def render_skill_graph(data_dir: str | Path) -> None:
    if not graph_enabled():
        return
    try:
        data = build_graph_data(data_dir)
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        st.caption("Visualização do grafo indisponível nesta sessão.")
        return
    st.subheader("Mapa visual de competências")
    st.caption(
        "Uma visão exploratória das competências e suas relações no catálogo SkillGraph."
    )
    components.html(_svg(data), height=540, scrolling=False)
