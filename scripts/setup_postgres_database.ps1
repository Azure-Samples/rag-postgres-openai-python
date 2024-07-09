$POSTGRES_HOST = (azd env get-value POSTGRES_HOST)
$POSTGRES_USERNAME = (azd env get-value POSTGRES_USERNAME)
$POSTGRES_DATABASE = (azd env get-value POSTGRES_DATABASE)

if ([string]::IsNullOrEmpty($POSTGRES_HOST) -or [string]::IsNullOrEmpty($POSTGRES_USERNAME) -or [string]::IsNullOrEmpty($POSTGRES_DATABASE)) {
    Write-Host "Can't find POSTGRES_HOST, POSTGRES_USERNAME, and POSTGRES_DATABASE environment variables. Make sure you run azd up first."
    exit 1
}

python ./src/fastapi_app/setup_postgres_database.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --database $POSTGRES_DATABASE
