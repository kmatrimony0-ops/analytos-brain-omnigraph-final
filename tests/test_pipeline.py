from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agents.content_agent import write_blog
from agents.gtm_agent import prospecting_brief
from pipeline.graph_store import LocalGraphStore
from pipeline.ingest import ingest


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".local_graph", "runs", ".git", "node_modules", "__pycache__", ".pytest_cache")
    shutil.copytree(source, target, ignore=ignore)
    (target / "runs").mkdir(exist_ok=True)
    return target


def ingest_and_merge(repo: Path, run_id: str = "test-run") -> LocalGraphStore:
    state = repo / ".local_graph" / "state.json"
    manifest = ingest(repo / "seed-data", repo_root=repo, run_id=run_id, state_path=state)
    store = LocalGraphStore(state)
    assert manifest["branch"] == f"ingest/{run_id}"
    diff = store.diff(manifest["branch"])
    assert len(diff["nodes_added"]) > 0
    store.merge(manifest["branch"], actor="human-reviewer")
    return store


def test_ingestion_is_idempotent(repo_copy: Path):
    state = repo_copy / ".local_graph" / "state.json"
    first = ingest(repo_copy / "seed-data", repo_root=repo_copy, run_id="one", state_path=state)
    store = LocalGraphStore(state)
    store.merge(first["branch"], actor="human-reviewer")
    first_counts = (len(store.nodes()), len(store.edges()))

    second = ingest(repo_copy / "seed-data", repo_root=repo_copy, run_id="two", state_path=state)
    diff = store.diff(second["branch"])
    store.merge(second["branch"], actor="human-reviewer")
    second_counts = (len(store.nodes()), len(store.edges()))

    assert first_counts == second_counts
    assert len(diff["nodes_added"]) == 0
    assert len(diff["edges_added"]) == 0


def test_governance_blocks_direct_main_write(repo_copy: Path):
    state = repo_copy / ".local_graph" / "state.json"
    manifest = ingest(repo_copy / "seed-data", repo_root=repo_copy, run_id="blocked", state_path=state)
    store = LocalGraphStore(state)
    with pytest.raises(PermissionError):
        store.load_jsonl("main", Path(manifest["jsonl_path"]), actor="ingest-agent")
    with pytest.raises(PermissionError):
        store.merge(manifest["branch"], actor="ingest-agent")


def test_access_control_blocks_content_agent_email_threads(repo_copy: Path):
    store = ingest_and_merge(repo_copy, "acl")
    human_email = store.nodes(node_type="EmailThread", actor="human-reviewer")
    content_email = store.nodes(node_type="EmailThread", actor="content-agent")
    assert len(human_email) >= 2
    assert content_email == []


def test_content_agent_has_cited_facts_without_email_leak(repo_copy: Path):
    store = ingest_and_merge(repo_copy, "content")
    output = write_blog("Stockly inventory forecasting", store=store)
    assert "Facts used" in output
    assert output.count("`") >= 6
    assert "Northstar Retail" not in output
    assert "EmailThread results = 0" in output


def test_gtm_agent_outputs_prospecting_brief(repo_copy: Path):
    store = ingest_and_merge(repo_copy, "gtm")
    output = prospecting_brief("Stockly", store=store)
    assert "Target company profile" in output
    assert "Persona to contact" in output
    assert "Example companies" in output
    assert "Opening angle" in output
    assert "proof:" in output or "metric:" in output
