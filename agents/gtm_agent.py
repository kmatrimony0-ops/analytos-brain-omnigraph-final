from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.graph_store import LocalGraphStore
from pipeline.ingest import default_state_path


def prospecting_brief(product: str, store: LocalGraphStore | None = None) -> str:
    store = store or LocalGraphStore(default_state_path(REPO_ROOT))
    context = store.product_context(product, actor="gtm-agent")
    nodes = context["related"]
    segments = [n for n in nodes if n["type"] == "ICPSegment"]
    personas = [n for n in nodes if n["type"] == "Persona"]
    proofs = [n for n in nodes if n["type"] in {"ProofPoint", "Metric"}]
    if not segments:
        segments = [n for n in store.nodes(actor="gtm-agent", node_type="ICPSegment")]
    if not personas:
        personas = [n for n in store.nodes(actor="gtm-agent", node_type="Persona")]
    if not proofs:
        proofs = [n for n in store.nodes(actor="gtm-agent") if n["type"] in {"ProofPoint", "Metric"}]
    companies = [
        "PlausibleCo Retail Group",
        "Northstar Distribution",
        "Meridian Operations Inc.",
    ] if product.lower().startswith("stock") else [
        "Apex Medical Devices",
        "Carewell Diagnostics",
        "Regent Quality Systems",
    ]
    lines = [
        f"# Prospecting Brief: {product}",
        "",
        "## Target company profile",
    ]
    for seg in segments[:3]:
        lines.append(f"- {seg['data'].get('name')}: {seg['data'].get('description') or '; '.join(seg['data'].get('firmographics', []))} (`{seg['id']}`)")
    lines.extend(["", "## Persona to contact"])
    for persona in personas[:3]:
        lines.append(f"- {persona['data'].get('title')}: {', '.join(persona['data'].get('pain_points', []))} (`{persona['id']}`)")
    lines.extend(["", "## Example companies", *[f"- {c}" for c in companies], "", "## Opening angle grounded in graph proof points"])
    for proof in proofs[:3]:
        label = proof["data"].get("claim") or proof["data"].get("label") or proof["id"]
        lines.append(f"- Lead with: {label} (`{proof['id']}`)")
    lines.append("\nUse only the approved main-branch graph context; do not cite internal email content.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="GTM agent using approved ICP and product graph")
    parser.add_argument("product")
    args = parser.parse_args()
    print(prospecting_brief(args.product))


if __name__ == "__main__":
    main()
