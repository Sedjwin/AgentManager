#!/usr/bin/env bash
cd "$(dirname "$0")"
source .env 2>/dev/null || true
exec uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
