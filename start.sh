#!/bin/sh
set -eu
port="${PORT:-8010}"
exec python -m uvicorn sed_report_engine.app:app --host 0.0.0.0 --port "$port"
