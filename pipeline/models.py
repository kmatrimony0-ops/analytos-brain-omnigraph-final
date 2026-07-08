from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Node:
    id: str
    type: str
    data: Dict[str, Any]


@dataclass
class Edge:
    id: str
    type: str
    src: str
    dst: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    nodes: List[Node]
    edges: List[Edge]
    source_files: List[str]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [{"id": n.id, "type": n.type, "data": n.data} for n in self.nodes],
            "edges": [{"id": e.id, "type": e.type, "src": e.src, "dst": e.dst, "data": e.data} for e in self.edges],
            "source_files": self.source_files,
            "warnings": self.warnings,
        }
