# Analytos Brain on Omnigraph — Submission POC

This repository is a submission-ready proof-of-concept for the **Analytos Org Context Layer / Analytos Brain** assessment.

It demonstrates the required loop:

```text
Ingest → Extract → Human Review → Merge to main → Dashboard + MCP → Agents produce real work
```

## What is included

- Omnigraph schema in `omnigraph/schema/analytos.pg`
- Omnigraph query templates in `omnigraph/queries/*.gq`
- Cedar policy sketch in `omnigraph/policies/analytos.cedar`
- Python ingestion pipeline that emits Omnigraph-compatible JSONL
- Idempotent deterministic IDs for nodes and edges
- Review/approval flow with branch diffs and merge attribution
- FastAPI dashboard for entity browsing, search, review, and recent changes
- MCP wrapper exposing governed graph reads to agents
- Content Agent and GTM Agent scripts
- Tests covering idempotency, governance, access control, and agent output
- Demo seed files matching the requested filenames

> Note: The official private seed docs were not available in this chat, so this repo includes realistic demo seed files with the required filenames. If you have the official assessment seed files, replace files in `seed-data/` and rerun the same commands.

## Architecture

```text
seed-data/*.md
  → pipeline.ingest
  → Gemini Flash extraction when GEMINI_API_KEY is set; deterministic fallback otherwise
  → runs/<run-id>/graph.jsonl
  → ingest/<run-id> branch
  → human review diff
  → approve merge to main
  → dashboard + MCP wrapper
  → content_agent.py and gtm_agent.py
```

The local graph store in `.local_graph/state.json` is used so the full demo can run without external services. The pipeline also emits Omnigraph-compatible JSONL and includes the real Omnigraph schema/query/policy files for a server-backed deployment.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional MCP dependencies:

```bash
npm install
```

Optional Omnigraph install:

```bash
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/install.sh | bash
omnigraph version
```

## Optional: enable real Gemini LLM extraction

The repo runs without secrets, but for assessment compliance you should set a Gemini key locally or in hosting:

```bash
export GEMINI_API_KEY="your-rotated-google-ai-studio-key"
# optional
export GEMINI_MODEL="gemini-1.5-flash"
```

Never commit `.env` files or paste API keys into the repository.

## Run the full local demo

```bash
bash scripts/demo.sh
```

This will:

1. Ingest all seed docs into `ingest/demo-run`.
2. Print the diff.
3. Approve and merge into `main` as `human-reviewer`.
4. Run Content Agent.
5. Run GTM Agent.

## Manual workflow

### 1. Ingest seed data

```bash
python -m pipeline.ingest --input seed-data --run-id seed-run
```

Expected result:

```text
branch: ingest/seed-run
status: pending_review
nodes/edges extracted
```

### 2. Review the branch diff

```bash
python -m pipeline.review diff ingest/seed-run
```

### 3. Approve and merge

```bash
python -m pipeline.review approve ingest/seed-run
```

Only `human-reviewer` can merge. `ingest-agent` cannot write directly to main.

### 4. Start dashboard

```bash
uvicorn dashboard.backend.main:app --reload --port 8000
```

Open:

```text
http://localhost:8000
```

Dashboard pages:

- `/entities` — entity browser
- `/search` — search approved knowledge
- `/review` — pending branch review
- `/recent` — merge/commit history

### 5. Run Content Agent

```bash
python agents/content_agent.py "Stockly inventory forecasting"
```

The Content Agent:

- Uses only approved main-branch knowledge
- Cites graph node IDs
- Avoids EmailThread/internal-only nodes
- Shows access-control check

### 6. Run GTM Agent

```bash
python agents/gtm_agent.py "Stockly"
```

The GTM Agent returns:

- Target company profile
- Persona to contact
- Example companies
- Opening angle grounded in proof points
- Graph node citations

## MCP usage

Install Node dependencies:

```bash
npm install
```

Run content-agent MCP wrapper:

```bash
ANALYTOS_ACTOR=content-agent node mcp/custom-wrapper/server.mjs
```

Run GTM-agent MCP wrapper:

```bash
ANALYTOS_ACTOR=gtm-agent node mcp/custom-wrapper/server.mjs
```

Claude Desktop-style configs are provided:

- `mcp/content-agent-config.json`
- `mcp/gtm-agent-config.json`

The MCP tool `try_read_email_threads` demonstrates policy behavior:

```json
{
  "actor": "content-agent",
  "visible_count": 0,
  "denied_count": 2
}
```

## Omnigraph-backed mode

The POC emits JSONL that follows the Omnigraph bulk load shape:

```json
{"type":"Product","id":"product:stockly","data":{...}}
{"edge":"HAS_FEATURE","id":"edge:...","from":"product:stockly","to":"feature:stockly:demand-forecasting","data":{...}}
```

Initialize a real graph:

```bash
mkdir -p data
omnigraph init --schema omnigraph/schema/analytos.pg data/analytos-brain.omni
```

Load an approved run branch into Omnigraph:

```bash
omnigraph branch create ingest/seed-run data/analytos-brain.omni
omnigraph load --data runs/seed-run/graph.jsonl --mode merge --branch ingest/seed-run data/analytos-brain.omni
omnigraph branch merge ingest/seed-run --into main data/analytos-brain.omni
```

For cluster/server deployments, adapt `omnigraph/cluster.yaml`, then use:

```bash
omnigraph cluster validate --config omnigraph/cluster.yaml
omnigraph cluster plan --config omnigraph/cluster.yaml
omnigraph cluster apply --config omnigraph/cluster.yaml
omnigraph-server --cluster omnigraph/cluster.yaml --bind 0.0.0.0:8080
```

## Tests

```bash
pytest -q
```

Covered criteria:

- Idempotent re-ingestion
- No direct writes to main by ingest-agent
- Merge requires human-reviewer
- content-agent cannot read EmailThread nodes
- Content Agent has citations and no internal client leak
- GTM Agent produces a prospecting brief

## Assessment criteria mapping

| Criterion | Where implemented |
|---|---|
| Governance correctness | `pipeline/graph_store.py`, `pipeline/review.py`, tests |
| Extraction quality | `pipeline/extract.py`, structured entities/edges, source metadata |
| Agent output quality | `agents/content_agent.py`, `agents/gtm_agent.py` |
| Access control | `omnigraph/policies/analytos.cedar`, local policy in `LocalGraphStore.can_read` |
| Dashboard usability | `dashboard/backend/main.py` |
| Engineering hygiene | README, tests, reproducible scripts, clear repo structure |

## Known limitations

- Gemini Flash extraction is implemented and used when `GEMINI_API_KEY` is set. The deterministic fallback remains for reproducible tests and demos without credentials.
- The local graph store is a test/demo fallback. Production submission hosting should run Omnigraph server with `cluster.yaml` and the Cedar bundle.
- The included seed docs are demo fixtures because the private official seed docs were not uploaded here.

## Submission email template

To: `santosh.thota@analytos.ai`  
CC: `ashok.suthar@analytos.ai`  
Subject: `Context Layer Omnigraph Task – <Your Name>`

Include:

1. GitHub repo link
2. Dashboard URL and credentials
3. MCP endpoint/config and credentials
4. Demo video link
5. Resume drive link
6. Short implementation notes
