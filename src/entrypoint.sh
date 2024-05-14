#!/bin/bash
set -e
python3 -m gunicorn "fastapi_app:create_app()"