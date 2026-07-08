from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from pipeline.graph_store import LocalGraphStore
from pipeline.ingest import default_state_path
from pipeline.review import approve, reject, review_diff

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = Path(os.environ.get("ANALYTOS_GRAPH_STATE", str(default_state_path(REPO_ROOT))))
STORE = LocalGraphStore(STATE_PATH)

app = FastAPI(title="Analytos Brain Dashboard", version="0.1.0")


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: Inter, system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #111827; background: #f9fafb; }}
    header {{ background: #111827; color: white; padding: 16px 24px; }}
    nav a {{ color: #d1d5db; margin-right: 16px; text-decoration: none; }}
    main {{ padding: 24px; max-width: 1100px; margin: auto; }}
    .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin: 12px 0; box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    code, pre {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
    pre {{ padding: 12px; overflow: auto; }}
    button {{ background:#111827;color:white;border:0;border-radius:8px;padding:10px 14px;cursor:pointer; }}
    .danger {{ background:#b91c1c; }}
    input, select {{ padding:10px;border:1px solid #d1d5db;border-radius:8px; }}
    .muted {{ color:#6b7280; }}
  </style>
</head>
<body>
<header>
  <h1>Analytos Brain</h1>
  <nav><a href="/">Home</a><a href="/entities">Entities</a><a href="/search">Search</a><a href="/review">Review</a><a href="/recent">Recent Changes</a></nav>
</header>
<main>{body}</main>
</body>
</html>
""")


@app.get("/", response_class=HTMLResponse)
def home():
    stats = {t: len(STORE.nodes(node_type=t)) for t in ["Product", "Feature", "ProofPoint", "Metric", "ICPSegment", "Persona", "EmailThread", "Decision"]}
    cards = "".join(f"<div class='card'><h3>{k}</h3><p style='font-size:32px'>{v}</p></div>" for k, v in stats.items())
    pending = [b for b in STORE.branches() if b.startswith("ingest/")]
    body = f"<div class='grid'>{cards}</div><div class='card'><h2>Pending review branches</h2><pre>{json.dumps(pending, indent=2)}</pre></div>"
    return page("Analytos Brain", body)


@app.get("/entities", response_class=HTMLResponse)
def entities(entity_type: str = Query("Product")):
    options = "".join(f"<option {'selected' if entity_type == t else ''}>{t}</option>" for t in ["Product", "Feature", "ProofPoint", "Metric", "ICPSegment", "Persona", "EmailThread", "Decision", "SourceDocument"])
    rows = STORE.nodes(node_type=entity_type)
    body = f"""
    <form method="get"><select name="entity_type">{options}</select><button>View</button></form>
    <div class="card"><h2>{entity_type}</h2><p class="muted">{len(rows)} records on approved main branch.</p></div>
    """ + "".join(f"<div class='card'><h3>{r['data'].get('name') or r['data'].get('title') or r['data'].get('claim') or r['id']}</h3><p><code>{r['id']}</code></p><pre>{json.dumps(r['data'], indent=2)}</pre></div>" for r in rows)
    return page("Entities", body)


@app.get("/search", response_class=HTMLResponse)
def search(q: str = ""):
    results = STORE.search(q, actor="human-reviewer") if q else []
    body = f"""
    <form method="get"><input name="q" value="{q}" placeholder="Search approved graph" style="width:70%"><button>Search</button></form>
    <p class="muted">Search uses the local fallback scorer. Omnigraph `.gq` files include BM25/hybrid query templates.</p>
    """ + "".join(f"<div class='card'><strong>{r['type']}</strong> <code>{r['id']}</code><p>Score: {r['score']}</p><pre>{json.dumps(r['data'], indent=2)}</pre></div>" for r in results)
    return page("Search", body)


@app.get("/review", response_class=HTMLResponse)
def review():
    branches = [b for b in STORE.branches() if b.startswith("ingest/")]
    if not branches:
        return page("Review", "<div class='card'><h2>No pending branches</h2><p>Run <code>python -m pipeline.ingest --input seed-data</code>.</p></div>")
    body = "<h2>Pending Review</h2>"
    for branch in branches:
        diff = STORE.diff(branch)
        body += f"""
        <div class='card'>
          <h3>{branch}</h3>
          <p>Nodes added: {len(diff['nodes_added'])}; Nodes changed: {len(diff['nodes_changed'])}; Edges added: {len(diff['edges_added'])}; Edges changed: {len(diff['edges_changed'])}</p>
          <form method="post" action="/review/approve"><input type="hidden" name="branch" value="{branch}"><button>Approve and merge</button></form>
          <br>
          <form method="post" action="/review/reject"><input type="hidden" name="branch" value="{branch}"><button class="danger">Reject and discard</button></form>
          <details><summary>Diff JSON</summary><pre>{json.dumps(diff, indent=2)}</pre></details>
        </div>
        """
    return page("Review", body)


@app.post("/review/approve")
def approve_route(branch: str = Form(...)):
    approve(branch, REPO_ROOT, actor="human-reviewer")
    return RedirectResponse("/recent", status_code=303)


@app.post("/review/reject")
def reject_route(branch: str = Form(...)):
    reject(branch, REPO_ROOT, actor="human-reviewer")
    return RedirectResponse("/review", status_code=303)


@app.get("/recent", response_class=HTMLResponse)
def recent():
    commits = STORE.commits()
    body = "<h2>Recent Changes</h2>" + "".join(f"<div class='card'><h3>{c['id']}</h3><pre>{json.dumps(c, indent=2)}</pre></div>" for c in commits)
    return page("Recent Changes", body)


@app.get("/api/entities")
def api_entities(entity_type: Optional[str] = None, actor: str = "human-reviewer"):
    return STORE.nodes(node_type=entity_type, actor=actor)


@app.get("/api/search")
def api_search(q: str, actor: str = "human-reviewer"):
    return STORE.search(q, actor=actor)


@app.get("/api/product-context")
def api_product_context(product: str, actor: str = "content-agent"):
    return STORE.product_context(product, actor=actor)


@app.get("/api/recent")
def api_recent():
    return STORE.commits()
