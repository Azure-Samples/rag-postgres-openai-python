POSTGRES_HOST=$(azd env get-values | grep POSTGRES_HOST | sed 's/="/=/' | sed 's/"$//' | sed 's/^POSTGRES_HOST=//')
POSTGRES_USERNAME=$(azd env get-values | grep POSTGRES_USERNAME | sed 's/="/=/' | sed 's/"$//' | sed 's/^POSTGRES_USERNAME=//')
POSTGRES_DATABASE=$(azd env get-values | grep POSTGRES_DATABASE | sed 's/="/=/' | sed 's/"$//' | sed 's/^POSTGRES_DATABASE=//')

. ./scripts/load_python_env.sh

.venv/bin/python ./src/fastapi_app/setup_postgres_database.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --database $POSTGRES_DATABASE
