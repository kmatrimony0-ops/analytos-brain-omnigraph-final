from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from pipeline.graph_store import LocalGraphStore
from pipeline.ingest import default_state_path

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_blog(topic: str, store: LocalGraphStore | None = None) -> str:
    store = store or LocalGraphStore(default_state_path(REPO_ROOT))
    hits = store.search(topic, actor="content-agent", limit=20)
    products = [h for h in hits if h["type"] == "Product"]
    facts = [h for h in hits if h["type"] in {"Feature", "ProofPoint", "Metric"}]
    if len(facts) < 3:
        # Broaden safely but still stay inside content-agent policy.
        facts = [n for n in store.nodes(actor="content-agent") if n["type"] in {"Feature", "ProofPoint", "Metric"}][:6]
    facts = facts[:6]
    title = f"How {topic.title()} Turns Approved Knowledge Into Action"
    product_names = ", ".join(p["data"].get("name", p["id"]) for p in products[:2]) or "Analytos products"
    lines = [
        f"# {title}",
        "",
        f"Modern teams need product stories grounded in approved knowledge, not stale snippets. For {product_names}, the Analytos Brain provides a governed source of truth that keeps product facts, features, and proof points traceable.",
        "",
        "## What the approved graph says",
    ]
    for fact in facts[:3]:
        data = fact["data"]
        label = data.get("claim") or data.get("name") or data.get("label") or data.get("description")
        lines.append(f"- {label} (`{fact['id']}`)")
    lines.extend([
        "",
        "## Why this matters",
        "Because every fact above comes from the approved `main` branch, a content agent can draft useful material without copying internal email threads or leaking client-sensitive information.",
        "",
        "## Draft conclusion",
        "The result is a safer content workflow: teams get fast drafts, reviewers get traceable citations, and agents stay inside governed access boundaries.",
        "",
        "## Facts used",
    ])
    for fact in facts[:6]:
        label = fact["data"].get("claim") or fact["data"].get("name") or fact["data"].get("label") or fact["id"]
        lines.append(f"- `{fact['id']}`: {label}")
    blocked = store.search("email thread internal client", actor="content-agent")
    leaked = [b for b in blocked if b["type"] == "EmailThread"]
    lines.extend(["", f"Access-control check: content-agent EmailThread results = {len(leaked)}."])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Content agent using approved graph knowledge only")
    parser.add_argument("topic")
    args = parser.parse_args()
    print(write_blog(args.topic))


if __name__ == "__main__":
    main()
