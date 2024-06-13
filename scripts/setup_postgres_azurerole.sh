POSTGRES_HOST=$(azd env get-values | grep POSTGRES_HOST | sed 's/="/=/' | sed 's/"$//' | sed 's/^POSTGRES_HOST=//')
POSTGRES_USERNAME=$(azd env get-values | grep POSTGRES_USERNAME | sed 's/="/=/' | sed 's/"$//' | sed 's/^POSTGRES_USERNAME=//')
APP_IDENTITY_NAME=$(azd env get-values | grep SERVICE_WEB_IDENTITY_NAME | sed 's/="/=/' | sed 's/"$//' | sed 's/^SERVICE_WEB_IDENTITY_NAME=//')

if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_USERNAME" ] || [ -z "$APP_IDENTITY_NAME" ]; then
    echo "Can't find POSTGRES_HOST, POSTGRES_USERNAME, and SERVICE_WEB_IDENTITY_NAME environment variables. Make sure you run azd up first."
    exit 1
fi

. ./scripts/load_python_env.sh

.venv/bin/python ./src/fastapi_app/setup_postgres_azurerole.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --app-identity-name $APP_IDENTITY_NAME
