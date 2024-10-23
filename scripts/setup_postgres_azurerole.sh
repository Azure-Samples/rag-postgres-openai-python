POSTGRES_HOST=$(azd env get-value POSTGRES_HOST)
if [ $? -ne 0 ]; then
    echo "Failed to find a value or POSTGRES_HOST in your azd environment. Make sure you run azd up first."
    exit 1
fi
POSTGRES_USERNAME=$(azd env get-value POSTGRES_USERNAME)
APP_IDENTITY_NAME=$(azd env get-value SERVICE_WEB_IDENTITY_NAME)
AZURE_TENANT_ID=$(azd env get-value AZURE_TENANT_ID)

if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_USERNAME" ] || [ -z "$APP_IDENTITY_NAME" ]; then
    echo "Can't find POSTGRES_HOST, POSTGRES_USERNAME, and SERVICE_WEB_IDENTITY_NAME environment variables. Make sure you run azd up first."
    exit 1
fi

. ./scripts/load_python_env.sh

.venv/bin/python ./src/backend/fastapi_app/setup_postgres_azurerole.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --app-identity-name $APP_IDENTITY_NAME --sslmode require --tenant-id $AZURE_TENANT_ID
