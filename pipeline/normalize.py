from __future__ import annotations

import hashlib
import re
from pathlib import Path


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"


def short_hash(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def doc_id_for_path(path: Path) -> str:
    return f"doc:{slugify(path.stem)}"


def content_hash(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def node_id(node_type: str, *parts: str) -> str:
    return f"{slugify(node_type)}:" + ":".join(slugify(p) for p in parts if p)


def proof_id(product: str, claim: str, source_doc_id: str) -> str:
    return f"proof:{slugify(product)}:{short_hash(claim + source_doc_id)}"


def metric_id(product: str, label: str, source_doc_id: str) -> str:
    return f"metric:{slugify(product)}:{short_hash(label + source_doc_id)}"


def edge_id(edge_type: str, src: str, dst: str, source_doc_id: str) -> str:
    return f"edge:{slugify(edge_type)}:{short_hash(src + dst + source_doc_id, 16)}"
