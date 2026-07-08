# Submission Notes

## Repository status

This repo contains a runnable proof-of-concept for the Analytos Brain assessment:

- Ingests all five required seed-data filenames.
- Extracts typed Product, Feature, ProofPoint, Metric, ICP, Persona, EmailThread, Decision, and SourceDocument nodes.
- Writes every ingestion to `ingest/<run-id>` instead of `main`.
- Shows diff and requires `human-reviewer` approval before merge.
- Serves a dashboard for humans.
- Exposes an MCP wrapper for agents.
- Demonstrates content-agent access denial for `EmailThread` nodes.
- Includes Content and GTM agents with graph-node citations.
- Includes tests: `pytest -q`.

## Verification performed

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
# 5 passed
```

## Important note

The actual private assessment seed files were not provided in this chat. Demo seed documents with the required filenames are included. Replace `seed-data/*.md` with the official seed files before final evaluator demo if you have them.

## Submission email

To: santosh.thota@analytos.ai  
CC: ashok.suthar@analytos.ai  
Subject: Context Layer Omnigraph Task – <Your Name>
