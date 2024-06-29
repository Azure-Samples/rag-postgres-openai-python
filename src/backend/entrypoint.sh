#!/bin/bash
set -e
python3 -m pip install .
python3 -m gunicorn "fastapi_app:create_app()"