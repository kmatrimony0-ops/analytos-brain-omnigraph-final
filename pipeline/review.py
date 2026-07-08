from __future__ import annotations

import argparse
import json
from pathlib import Path

from .graph_store import LocalGraphStore
from .ingest import default_state_path


def review_diff(branch: str, repo_root: Path, state_path: Path | None = None) -> dict:
    store = LocalGraphStore(state_path or default_state_path(repo_root))
    return store.diff(branch)


def approve(branch: str, repo_root: Path, actor: str = "human-reviewer", state_path: Path | None = None) -> dict:
    store = LocalGraphStore(state_path or default_state_path(repo_root))
    return store.merge(branch, actor=actor)


def reject(branch: str, repo_root: Path, actor: str = "human-reviewer", state_path: Path | None = None) -> None:
    store = LocalGraphStore(state_path or default_state_path(repo_root))
    store.reject(branch, actor=actor)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review, approve, or reject ingest branches")
    sub = parser.add_subparsers(dest="command", required=True)
    p_diff = sub.add_parser("diff")
    p_diff.add_argument("branch")
    p_approve = sub.add_parser("approve")
    p_approve.add_argument("branch")
    p_approve.add_argument("--actor", default="human-reviewer")
    p_reject = sub.add_parser("reject")
    p_reject.add_argument("branch")
    p_reject.add_argument("--actor", default="human-reviewer")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    if args.command == "diff":
        print(json.dumps(review_diff(args.branch, repo_root), indent=2))
    elif args.command == "approve":
        print(json.dumps(approve(args.branch, repo_root, actor=args.actor), indent=2))
    elif args.command == "reject":
        reject(args.branch, repo_root, actor=args.actor)
        print(json.dumps({"status": "rejected", "branch": args.branch}, indent=2))


if __name__ == "__main__":
    main()
