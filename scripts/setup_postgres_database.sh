POSTGRES_HOST=$(azd env get-value POSTGRES_HOST)
POSTGRES_USERNAME=$(azd env get-value POSTGRES_USERNAME)
POSTGRES_DATABASE=$(azd env get-value POSTGRES_DATABASE)

. ./scripts/load_python_env.sh

.venv/bin/python ./src/fastapi_app/setup_postgres_database.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --database $POSTGRES_DATABASE
