POSTGRES_HOST=$(azd env get-value POSTGRES_HOST)
if [ $? -ne 0 ]; then
    echo "Failed to find a value or POSTGRES_HOST in your azd environment. Make sure you run azd up first."
    exit 1
fi
POSTGRES_USERNAME=$(azd env get-value POSTGRES_USERNAME)
POSTGRES_DATABASE=$(azd env get-value POSTGRES_DATABASE)
AZURE_TENANT_ID=$(azd env get-value AZURE_TENANT_ID)

. ./scripts/load_python_env.sh

.venv/bin/python ./src/backend/fastapi_app/setup_postgres_seeddata.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --database $POSTGRES_DATABASE  --sslmode require --tenant-id $AZURE_TENANT_ID
