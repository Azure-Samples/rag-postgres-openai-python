$POSTGRES_HOST = ((azd env get-values | Select-String -Pattern "POSTGRES_HOST") -replace '^POSTGRES_HOST=', '')
$POSTGRES_USERNAME = ((azd env get-values | Select-String -Pattern "POSTGRES_USERNAME") -replace '^POSTGRES_USERNAME=', '')
$APP_IDENTITY_NAME = ((azd env get-values | Select-String -Pattern "SERVICE_WEB_IDENTITY_NAME") -replace '^SERVICE_WEB_IDENTITY_NAME=', '')

if ([string]::IsNullOrEmpty($POSTGRES_HOST) -or [string]::IsNullOrEmpty($POSTGRES_USERNAME) -or [string]::IsNullOrEmpty($APP_IDENTITY_NAME)) {
    Write-Host "Can't find POSTGRES_HOST, POSTGRES_USERNAME, and SERVICE_WEB_IDENTITY_NAME environment variables. Make sure you run azd up first."
    exit 1
}

python ./src/fastapi_app/setup_postgres_azurerole.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --app-identity-name $APP_IDENTITY_NAME