 #!/bin/sh

python3 -m pip install uv

echo 'Creating Python virtual environment in .venv...'
uv venv

echo 'Installing dependencies from "requirements.txt" into virtual environment (in quiet mode)...'

uv pip install --quiet -e src/backend
uv pip install --quiet -r requirements-dev.txt
