from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def omnigraph_available() -> bool:
    return shutil.which("omnigraph") is not None


def run_omnigraph_ingest(graph_uri: str, branch: str, jsonl_path: Path) -> None:
    """Optional real Omnigraph execution path.

    The local POC always emits Omnigraph-compatible JSONL. If the CLI is installed, use this helper
    to create the branch and load into Omnigraph proper.
    """
    if not omnigraph_available():
        raise RuntimeError("omnigraph CLI not found. Install it from ModernRelay/omnigraph first.")
    subprocess.run(["omnigraph", "branch", "create", branch, graph_uri], check=True)
    subprocess.run(["omnigraph", "load", "--data", str(jsonl_path), "--mode", "merge", "--branch", branch, graph_uri], check=True)


def run_omnigraph_merge(graph_uri: str, branch: str, target: str = "main") -> None:
    if not omnigraph_available():
        raise RuntimeError("omnigraph CLI not found. Install it from ModernRelay/omnigraph first.")
    subprocess.run(["omnigraph", "branch", "merge", branch, "--into", target, graph_uri], check=True)
