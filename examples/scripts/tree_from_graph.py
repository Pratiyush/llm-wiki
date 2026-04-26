"""Print sessions as a tree from `site/graph.jsonld`.

Demonstrates programmatic access to the AI-consumable JSON-LD graph
that `llmwiki build` emits. Stdlib-only, runs anywhere.

Usage:
    python3 examples/scripts/tree_from_graph.py [path/to/graph.jsonld]

Default path: site/graph.jsonld (relative to cwd).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main(graph_path: str = "site/graph.jsonld") -> int:
    path = Path(graph_path)
    if not path.is_file():
        print(f"error: {path} not found — run `llmwiki build` first", file=sys.stderr)
        return 1

    nodes = json.loads(path.read_text(encoding="utf-8"))["@graph"]

    root = next((n for n in nodes if n["@id"] == "llmwiki"), {})
    projects = {n["@id"]: n for n in nodes if n["@id"].startswith("project/")}
    sessions = [n for n in nodes if n["@id"].startswith("session/")]

    by_proj: dict[str, list[dict]] = defaultdict(list)
    for s in sessions:
        by_proj[s["isPartOf"]["@id"]].append(s)

    total = sum(p.get("numberOfItems", 0) for p in projects.values())
    print()
    print(f"📚 {total} sessions across {len(projects)} projects")
    print(f"   ({path} v{root.get('version', '?')})")
    print()

    print(f"{root.get('name', 'llmwiki')}/")
    proj_items = sorted(projects.items(), key=lambda kv: -kv[1].get("numberOfItems", 0))
    for pi, (pid, p) in enumerate(proj_items):
        last_proj = pi == len(proj_items) - 1
        proj_prefix = "└──" if last_proj else "├──"
        proj_sessions = sorted(by_proj[pid], key=lambda s: s.get("dateCreated", ""))
        n = len(proj_sessions)
        print(f"{proj_prefix} {p['name']}/  ({n} session{'s' if n != 1 else ''})")
        leg = "    " if last_proj else "│   "
        for i, s in enumerate(proj_sessions):
            child_prefix = "└──" if i == n - 1 else "├──"
            date = s.get("dateCreated", "")[:10]
            title = s.get("name", "").replace("Session: ", "").split(" — ")[0]
            print(f"{leg}{child_prefix} {date}  {title}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "site/graph.jsonld"))
