#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf .local_graph runs/demo-run
python -m pipeline.ingest --input seed-data --run-id demo-run
python -m pipeline.review diff ingest/demo-run | head -120
python -m pipeline.review approve ingest/demo-run
python agents/content_agent.py "Stockly inventory forecasting"
python agents/gtm_agent.py "Stockly"
echo "Dashboard: uvicorn dashboard.backend.main:app --reload --port 8000"
