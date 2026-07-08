from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .extract import extract_with_optional_llm
from .graph_store import LocalGraphStore
from .make_jsonl import write_jsonl


def default_state_path(repo_root: Path) -> Path:
    return repo_root / ".local_graph" / "state.json"


def ingest(input_path: Path, repo_root: Path, actor: str = "ingest-agent", run_id: Optional[str] = None, state_path: Optional[Path] = None) -> dict:
    if actor != "ingest-agent":
        raise PermissionError("ingestion must run as ingest-agent")
    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"ingest/{run_id}"
    run_dir = repo_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    result = extract_with_optional_llm(input_path)
    extracted_path = run_dir / "extracted.json"
    jsonl_path = run_dir / "graph.jsonl"
    manifest_path = run_dir / "manifest.json"

    extracted_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    write_jsonl(result, jsonl_path)

    store = LocalGraphStore(state_path or default_state_path(repo_root))
    store.create_branch(branch, from_branch="main")
    store.load_jsonl(branch, jsonl_path, actor=actor)
    diff = store.diff(branch)

    manifest = {
        "run_id": run_id,
        "branch": branch,
        "actor": actor,
        "input": str(input_path),
        "source_files": result.source_files,
        "jsonl_path": str(jsonl_path),
        "extracted_path": str(extracted_path),
        "nodes_extracted": len(result.nodes),
        "edges_extracted": len(result.edges),
        "nodes_added": len(diff["nodes_added"]),
        "nodes_changed": len(diff["nodes_changed"]),
        "edges_added": len(diff["edges_added"]),
        "edges_changed": len(diff["edges_changed"]),
        "status": "pending_review",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest seed docs into an isolated reviewed branch")
    parser.add_argument("--input", required=True, help="Markdown file or directory")
    parser.add_argument("--actor", default="ingest-agent")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--state", default=None, help="Path to local graph state JSON")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    manifest = ingest(Path(args.input), repo_root=repo_root, actor=args.actor, run_id=args.run_id, state_path=Path(args.state) if args.state else None)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
