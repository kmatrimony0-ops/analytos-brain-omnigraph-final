from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class LocalGraphStore:
    """Small governed graph store used for local verification and demo fallback.

    The repository still includes Omnigraph schema/query/policy artifacts and emits Omnigraph-compatible JSONL.
    This class makes tests and the dashboard runnable without requiring evaluator secrets or a remote server.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"branches": {"main": {"nodes": {}, "edges": {}}}, "commits": [], "reviews": []})

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, state: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def create_branch(self, branch: str, from_branch: str = "main") -> None:
        state = self._read()
        if branch not in state["branches"]:
            state["branches"][branch] = deepcopy(state["branches"].get(from_branch, {"nodes": {}, "edges": {}}))
        self._write(state)

    def delete_branch(self, branch: str) -> None:
        if branch == "main":
            raise ValueError("cannot delete main")
        state = self._read()
        state["branches"].pop(branch, None)
        self._write(state)

    def load_jsonl(self, branch: str, jsonl_path: Path, actor: str = "ingest-agent") -> None:
        if branch == "main" and actor != "human-reviewer":
            raise PermissionError("ingest writes to main are forbidden; use ingest/<run-id> and review merge")
        state = self._read()
        state["branches"].setdefault(branch, deepcopy(state["branches"].get("main", {"nodes": {}, "edges": {}})))
        target = state["branches"][branch]
        for raw in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            record = json.loads(raw)
            if "type" in record:
                target["nodes"][record["id"]] = {"id": record["id"], "type": record["type"], "data": record.get("data", {})}
            elif "edge" in record:
                target["edges"][record["id"]] = {"id": record["id"], "type": record["edge"], "src": record["from"], "dst": record["to"], "data": record.get("data", {})}
        self._write(state)

    def diff(self, branch: str, against: str = "main") -> Dict[str, Any]:
        state = self._read()
        base = state["branches"].get(against, {"nodes": {}, "edges": {}})
        head = state["branches"].get(branch, {"nodes": {}, "edges": {}})
        def compare(kind: str):
            added, changed = [], []
            for key, value in head[kind].items():
                if key not in base[kind]:
                    added.append(value)
                elif base[kind][key] != value:
                    changed.append({"before": base[kind][key], "after": value})
            return added, changed
        added_nodes, changed_nodes = compare("nodes")
        added_edges, changed_edges = compare("edges")
        return {
            "branch": branch,
            "against": against,
            "nodes_added": added_nodes,
            "nodes_changed": changed_nodes,
            "edges_added": added_edges,
            "edges_changed": changed_edges,
        }

    def merge(self, branch: str, actor: str = "human-reviewer", target: str = "main") -> Dict[str, Any]:
        if actor != "human-reviewer":
            raise PermissionError("only human-reviewer can merge branches")
        if not branch.startswith("ingest/"):
            raise PermissionError("only ingest/* branches can be merged through review flow")
        state = self._read()
        if branch not in state["branches"]:
            raise KeyError(f"branch not found: {branch}")
        diff = self.diff(branch, target)
        state["branches"][target] = deepcopy(state["branches"][branch])
        commit = {
            "id": f"commit:{len(state['commits']) + 1:04d}",
            "branch": branch,
            "target": target,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nodes_added": len(diff["nodes_added"]),
            "nodes_changed": len(diff["nodes_changed"]),
            "edges_added": len(diff["edges_added"]),
            "edges_changed": len(diff["edges_changed"]),
        }
        state["commits"].append(commit)
        state["reviews"].append({"branch": branch, "status": "approved", "actor": actor, "timestamp": commit["timestamp"]})
        self._write(state)
        return commit

    def reject(self, branch: str, actor: str = "human-reviewer") -> None:
        if actor != "human-reviewer":
            raise PermissionError("only human-reviewer can reject branches")
        state = self._read()
        state["reviews"].append({"branch": branch, "status": "rejected", "actor": actor, "timestamp": datetime.now(timezone.utc).isoformat()})
        state["branches"].pop(branch, None)
        self._write(state)

    def nodes(self, branch: str = "main", node_type: Optional[str] = None, actor: str = "human-reviewer") -> List[Dict[str, Any]]:
        state = self._read()
        rows = list(state["branches"].get(branch, {"nodes": {}})["nodes"].values())
        if node_type:
            rows = [r for r in rows if r["type"] == node_type]
        return [r for r in rows if self.can_read(actor, r)]

    def edges(self, branch: str = "main") -> List[Dict[str, Any]]:
        state = self._read()
        return list(state["branches"].get(branch, {"edges": {}})["edges"].values())

    def branches(self) -> List[str]:
        return sorted(self._read()["branches"].keys())

    def commits(self) -> List[Dict[str, Any]]:
        return list(reversed(self._read()["commits"]))

    @staticmethod
    def can_read(actor: str, node: Dict[str, Any]) -> bool:
        visibility = node.get("data", {}).get("visibility")
        if actor == "content-agent":
            return node.get("type") in {"Product", "Feature", "ProofPoint", "Metric", "SourceDocument"} and visibility != "internal_only"
        if actor == "gtm-agent":
            return node.get("type") in {"Product", "Feature", "ProofPoint", "Metric", "ICPSegment", "Persona", "SourceDocument"} and visibility != "internal_only"
        return True

    def search(self, query: str, branch: str = "main", actor: str = "human-reviewer", limit: int = 10) -> List[Dict[str, Any]]:
        q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored = []
        for node in self.nodes(branch=branch, actor=actor):
            text = json.dumps(node, sort_keys=True).lower()
            score = sum(1 for term in q_terms if term in text)
            if score:
                scored.append({"score": score, **node})
        return sorted(scored, key=lambda r: (-r["score"], r["id"]))[:limit]

    def product_context(self, product_name: str, branch: str = "main", actor: str = "content-agent") -> Dict[str, Any]:
        product_slug = product_name.lower()
        all_nodes = {n["id"]: n for n in self.nodes(branch=branch, actor=actor)}
        all_edges = self.edges(branch=branch)
        products = [n for n in all_nodes.values() if n["type"] == "Product" and product_slug in n["data"].get("name", "").lower()]
        product_ids = {p["id"] for p in products}
        related_ids = set(product_ids)
        for edge in all_edges:
            if edge["src"] in product_ids:
                related_ids.add(edge["dst"])
            if edge["dst"] in product_ids:
                related_ids.add(edge["src"])
        return {"product": products, "related": [all_nodes[i] for i in sorted(related_ids) if i in all_nodes], "edges": [e for e in all_edges if e["src"] in related_ids or e["dst"] in related_ids]}
