"""Export the four Foothold LangGraph graphs as Mermaid source and PNG images.

    $FOOTHOLD_PY scripts/export_graph_images.py

Writes docs/images/langgraph-<name>.mmd (always) and docs/images/langgraph-<name>.png
(rendered through the mermaid.ink API by LangGraph's draw_mermaid_png). Graphs are
compiled on an in-memory checkpointer so the script never touches api/.runtime.
If PNG rendering fails for a graph, its .mmd is kept and the failure is reported.
"""

from __future__ import annotations

import base64
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
OUT = ROOT / "docs" / "images"
WIDTH_PX = 1600  # mermaid.ink output width; the default render is only ~400 px wide


def _render_hires(mermaid: str) -> bytes:
    """Same mermaid.ink API that draw_mermaid_png uses, with an explicit width."""
    import requests

    enc = base64.urlsafe_b64encode(mermaid.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{enc}?type=png&bgColor=!white&width={WIDTH_PX}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    if r.content[1:4] != b"PNG":
        raise ValueError("mermaid.ink did not return a PNG")
    return r.content


def main() -> int:
    from langgraph.checkpoint.memory import InMemorySaver

    import foothold.checkpoint as ckpt

    mem = InMemorySaver()
    ckpt.get_checkpointer = lambda *a, **k: mem  # keep the export off the live sqlite db

    from foothold.graphs import coach, employer, pathway, sim

    graphs = {
        "sim": sim.build_graph(mem),
        "pathway": pathway.build_graph(mem),
        "employer": employer.build_graph(mem),
        "coach": coach.build_graph(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for name, graph in graphs.items():
        g = graph.get_graph(xray=True)
        mmd = OUT / f"langgraph-{name}.mmd"
        mmd.write_text(g.draw_mermaid(), encoding="utf-8")
        print(f"wrote {mmd.relative_to(ROOT)}")
        png = OUT / f"langgraph-{name}.png"
        try:
            data = _render_hires(g.draw_mermaid())
        except Exception as exc:
            print(f"high-res render failed for {name} ({exc}); falling back to draw_mermaid_png", file=sys.stderr)
            data = None
        try:
            if data is None:
                from langchain_core.runnables.graph import MermaidDrawMethod

                data = g.draw_mermaid_png(
                    draw_method=MermaidDrawMethod.API,
                    background_color="white",
                    max_retries=3,
                    retry_delay=2.0,
                )
            png.write_bytes(data)
            w, h = struct.unpack(">II", data[16:24])
            print(f"wrote {png.relative_to(ROOT)} ({w}x{h}px, {len(data)} bytes)")
        except Exception as exc:  # network / renderer errors: keep the .mmd
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"PNG FAILED for {name}: {exc}", file=sys.stderr)
    if failures:
        print("PNG failures:\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
