from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import Edge, ExtractionResult, Node


def node_to_jsonl(node: Node) -> str:
    payload = {"type": node.type, "id": node.id, "data": node.data}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def edge_to_jsonl(edge: Edge) -> str:
    payload = {"edge": edge.type, "id": edge.id, "from": edge.src, "to": edge.dst, "data": edge.data}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def write_jsonl(result: ExtractionResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for node in sorted(result.nodes, key=lambda n: n.id):
            fh.write(node_to_jsonl(node) + "\n")
        for edge in sorted(result.edges, key=lambda e: e.id):
            fh.write(edge_to_jsonl(edge) + "\n")
