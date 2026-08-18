"""Render compiled LangGraph apps as Mermaid diagrams for architecture review.

Usage, from any module that builds a graph:

    from app.common.visualize import save_graph_diagram

    app = build_graph()
    save_graph_diagram(app, "supervisor_graph")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

DEFAULT_DIR = Path("graph_diagrams")


def save_graph_diagram(
    app: CompiledStateGraph,
    name: str,
    out_dir: Path = DEFAULT_DIR,
) -> None:
    """Save a compiled graph as ``.mmd`` and, when a renderer is reachable, ``.png``.

    Args:
        app: A compiled LangGraph app from ``StateGraph(...).compile()``.
        name: Filename stem, e.g. ``"supervisor_graph"``.
        out_dir: Directory to write into, created if missing.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph = app.get_graph()

    mmd_path = out_dir / f"{name}.mmd"
    mmd_path.write_text(graph.draw_mermaid())
    print(f"Saved {mmd_path} (paste into https://mermaid.live to view)")

    png_path = out_dir / f"{name}.png"
    try:
        png_path.write_bytes(graph.draw_mermaid_png())
        print(f"Saved {png_path}")
    except OSError as exc:
        print(
            f"Skipped PNG render ({type(exc).__name__}: {exc}). "
            f"The .mmd file above still works — paste it into https://mermaid.live.",
        )
