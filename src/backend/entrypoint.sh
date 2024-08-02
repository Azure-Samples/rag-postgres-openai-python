#!/bin/bash
set -e
python3 -m uvicorn "fastapi_app:create_app" --factory --port 8000
