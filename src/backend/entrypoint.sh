#!/bin/bash
set -e
python3 -m uvicorn "fastapi_app:create_app" --factory --host 0.0.0.0 --port 8000
