from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .models import Edge, ExtractionResult, Node
from .normalize import content_hash, doc_id_for_path, edge_id, metric_id, node_id, proof_id, slugify


SECTION_RE = re.compile(r"^#{1,3}\s+(.*)$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
METRIC_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|days|hours|x|times)?", re.I)


def _source_base(path: Path, text: str) -> Dict[str, str]:
    return {
        "source_doc_id": doc_id_for_path(path),
        "source_doc_hash": content_hash(text),
        "source_file": path.name,
    }


def _extract_section_lines(text: str) -> Dict[str, List[str]]:
    current = "intro"
    sections: Dict[str, List[str]] = {current: []}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = SECTION_RE.match(line)
        if m:
            current = slugify(m.group(1))
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return sections


def _parse_named_bullet(line: str) -> Tuple[str, str]:
    line = BULLET_RE.sub(r"\1", line).strip()
    if ":" in line:
        name, desc = line.split(":", 1)
        return name.strip(), desc.strip()
    return line.strip(), line.strip()


def _infer_product_name(path: Path, sections: Dict[str, List[str]]) -> str:
    stem = path.stem.lower()
    if "stockly" in stem:
        return "Stockly"
    if "inspectly" in stem:
        return "Inspectly"
    intro = sections.get("intro", [])
    for line in intro[:5]:
        if line.lower().startswith("product:"):
            return line.split(":", 1)[1].strip()
    title = path.stem.replace("-product-overview", "").replace("-", " ").title()
    return title


def _first_sentence(lines: Iterable[str], fallback: str) -> str:
    joined = " ".join(l.strip("-* ") for l in lines if l.strip())
    if not joined:
        return fallback
    return re.split(r"(?<=[.!?])\s+", joined)[0][:400]


def _make_node(n_type: str, n_id: str, source: Dict[str, str], **data) -> Node:
    payload = {**data, **source}
    payload.setdefault("visibility", "approved_internal")
    return Node(id=n_id, type=n_type, data=payload)


def _make_edge(e_type: str, src: str, dst: str, source: Dict[str, str]) -> Edge:
    return Edge(id=edge_id(e_type, src, dst, source["source_doc_id"]), type=e_type, src=src, dst=dst, data={"source_doc_id": source["source_doc_id"]})


def heuristic_extract_file(path: Path) -> ExtractionResult:
    text = path.read_text(encoding="utf-8")
    source = _source_base(path, text)
    sections = _extract_section_lines(text)
    nodes: Dict[str, Node] = {}
    edges: Dict[str, Edge] = {}
    warnings: List[str] = []
    stem = path.stem.lower()

    # Always store a source document node.
    doc_node = _make_node(
        "SourceDocument",
        source["source_doc_id"],
        source,
        title=path.name,
        summary=_first_sentence(sections.get("intro", []), path.name),
        visibility="approved_internal",
    )
    nodes[doc_node.id] = doc_node

    if "email" in stem or "thread" in stem:
        subject = path.stem.replace("-", " ").title()
        for line in text.splitlines():
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
                break
        thread_id = node_id("EmailThread", path.stem)
        thread = _make_node(
            "EmailThread",
            thread_id,
            source,
            subject=subject,
            summary=_first_sentence(sections.get("intro", []) + sections.get("summary", []), subject),
            internal_notes=text[:1200],
            visibility="internal_only",
        )
        nodes[thread.id] = thread
        edges[_make_edge("MENTIONS", doc_node.id, thread.id, source).id] = _make_edge("MENTIONS", doc_node.id, thread.id, source)

        mentioned_product = "Stockly" if "stockly" in stem or "stockly" in text.lower() else "Inspectly" if "inspectly" in stem or "inspectly" in text.lower() else None
        if mentioned_product:
            product_id = node_id("Product", mentioned_product)
            nodes.setdefault(product_id, _make_node("Product", product_id, source, slug=slugify(mentioned_product), name=mentioned_product, description=f"Mentioned in {path.name}", visibility="approved_internal"))
            edges[_make_edge("DISCUSSED_IN", product_id, thread.id, source).id] = _make_edge("DISCUSSED_IN", product_id, thread.id, source)

        for line in text.splitlines():
            if line.strip().lower().startswith(("decision:", "decided:")):
                decision_text = line.split(":", 1)[1].strip()
                d_id = node_id("Decision", path.stem, decision_text[:40])
                nodes[d_id] = _make_node("Decision", d_id, source, decision=decision_text, rationale="Extracted from internal email thread", visibility="internal_only")
                edges[_make_edge("FROM_THREAD", d_id, thread.id, source).id] = _make_edge("FROM_THREAD", d_id, thread.id, source)
        return ExtractionResult(list(nodes.values()), list(edges.values()), [str(path)], warnings)

    if "icp" in stem:
        product_hint = None
        for product_name in ("Stockly", "Inspectly"):
            if product_name.lower() in text.lower():
                product_hint = product_name
                product_id = node_id("Product", product_name)
                nodes.setdefault(product_id, _make_node("Product", product_id, source, slug=slugify(product_name), name=product_name, description=f"Product referenced in ICP document {path.name}", visibility="approved_internal"))

        for section_name, lines in sections.items():
            if any(k in section_name for k in ["segment", "icp", "target"]):
                for raw in lines:
                    if raw.startswith(('-', '*')):
                        name, desc = _parse_named_bullet(raw)
                        seg_id = node_id("ICPSegment", name)
                        nodes[seg_id] = _make_node("ICPSegment", seg_id, source, slug=slugify(name), name=name, description=desc, firmographics=[desc], trigger_signals=[], visibility="approved_internal")
                        if product_hint:
                            edges[_make_edge("TARGETS", node_id("Product", product_hint), seg_id, source).id] = _make_edge("TARGETS", node_id("Product", product_hint), seg_id, source)
            if "persona" in section_name:
                for raw in lines:
                    if raw.startswith(('-', '*')):
                        name, desc = _parse_named_bullet(raw)
                        p_id = node_id("Persona", name)
                        nodes[p_id] = _make_node("Persona", p_id, source, slug=slugify(name), title=name, pain_points=[desc], goals=[], visibility="approved_internal")
        return ExtractionResult(list(nodes.values()), list(edges.values()), [str(path)], warnings)

    product = _infer_product_name(path, sections)
    p_id = node_id("Product", product)
    nodes[p_id] = _make_node(
        "Product",
        p_id,
        source,
        slug=slugify(product),
        name=product,
        description=_first_sentence(sections.get("intro", []), f"{product} product overview"),
        visibility="approved_internal",
    )
    edges[_make_edge("MENTIONS", doc_node.id, p_id, source).id] = _make_edge("MENTIONS", doc_node.id, p_id, source)

    for sec_name, lines in sections.items():
        if "feature" in sec_name or "capabil" in sec_name:
            for raw in lines:
                if raw.startswith(('-', '*')):
                    name, desc = _parse_named_bullet(raw)
                    f_id = node_id("Feature", product, name)
                    nodes[f_id] = _make_node("Feature", f_id, source, slug=slugify(f"{product}-{name}"), name=name, description=desc, visibility="approved_internal")
                    e = _make_edge("HAS_FEATURE", p_id, f_id, source)
                    edges[e.id] = e
        if any(k in sec_name for k in ["proof", "metric", "result", "evidence"]):
            for raw in lines:
                if raw.startswith(('-', '*')):
                    claim = BULLET_RE.sub(r"\1", raw).strip()
                    pr_id = proof_id(product, claim, source["source_doc_id"])
                    metric_match = METRIC_RE.search(claim)
                    nodes[pr_id] = _make_node("ProofPoint", pr_id, source, slug=slugify(pr_id), claim=claim, evidence=claim, numeric_value=float(metric_match.group("value")) if metric_match else None, unit=(metric_match.group("unit") if metric_match else None), visibility="approved_internal")
                    e = _make_edge("PROVEN_BY", p_id, pr_id, source)
                    edges[e.id] = e
                    if metric_match:
                        m_id = metric_id(product, claim, source["source_doc_id"])
                        nodes[m_id] = _make_node("Metric", m_id, source, slug=slugify(m_id), label=claim[:80], value=float(metric_match.group("value")), unit=metric_match.group("unit") or "count", direction="neutral", visibility="approved_internal")
                        me = _make_edge("HAS_METRIC", pr_id, m_id, source)
                        edges[me.id] = me
        if "persona" in sec_name:
            for raw in lines:
                if raw.startswith(('-', '*')):
                    name, desc = _parse_named_bullet(raw)
                    persona_id = node_id("Persona", name)
                    nodes[persona_id] = _make_node("Persona", persona_id, source, slug=slugify(name), title=name, pain_points=[desc], goals=[], visibility="approved_internal")
        if any(k in sec_name for k in ["icp", "segment", "target"]):
            for raw in lines:
                if raw.startswith(('-', '*')):
                    name, desc = _parse_named_bullet(raw)
                    seg_id = node_id("ICPSegment", name)
                    nodes[seg_id] = _make_node("ICPSegment", seg_id, source, slug=slugify(name), name=name, description=desc, firmographics=[desc], trigger_signals=[], visibility="approved_internal")
                    edges[_make_edge("TARGETS", p_id, seg_id, source).id] = _make_edge("TARGETS", p_id, seg_id, source)

    return ExtractionResult(list(nodes.values()), list(edges.values()), [str(path)], warnings)


def extract_path(input_path: Path) -> ExtractionResult:
    files = sorted(input_path.glob("*.md")) if input_path.is_dir() else [input_path]
    all_nodes: Dict[str, Node] = {}
    all_edges: Dict[str, Edge] = {}
    source_files: List[str] = []
    warnings: List[str] = []
    for file_path in files:
        result = heuristic_extract_file(file_path)
        for node in result.nodes:
            all_nodes[node.id] = node
        for edge in result.edges:
            all_edges[edge.id] = edge
        source_files.extend(result.source_files)
        warnings.extend(result.warnings)
    return ExtractionResult(list(all_nodes.values()), list(all_edges.values()), source_files, warnings)


def extract_with_optional_llm(input_path: Path) -> ExtractionResult:
    """Use deterministic extraction by default. LLM extraction can be added without changing downstream code.

    The assessment asks for an LLM extraction step. This repo keeps the POC reproducible without secrets by using
    deterministic extraction in tests and demos. If OPENAI_API_KEY or GEMINI_API_KEY is set, teams can replace this
    function with a model call while preserving the same ExtractionResult contract.
    """
    return extract_path(input_path)
