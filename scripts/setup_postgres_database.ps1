$POSTGRES_HOST = ((azd env get-values | Select-String -Pattern "POSTGRES_HOST") -replace '^POSTGRES_HOST=', '')
$POSTGRES_USERNAME = ((azd env get-values | Select-String -Pattern "POSTGRES_USERNAME") -replace '^POSTGRES_USERNAME=', '')
$POSTGRES_PASSWORD = ((azd env get-values | Select-String -Pattern "POSTGRES_PASSWORD") -replace '^POSTGRES_PASSWORD=', '')

if ([string]::IsNullOrEmpty($POSTGRES_HOST) -or [string]::IsNullOrEmpty($POSTGRES_USERNAME) -or [string]::IsNullOrEmpty($POSTGRES_PASSWORD)) {
    Write-Host "Can't find POSTGRES_HOST, POSTGRES_USERNAME, and POSTGRES_PASSWORD environment variables. Make sure you run azd up first."
    exit 1
}

python ./src/fastapi_app/setup_postgres_database.py --host $POSTGRES_HOST --username $POSTGRES_USERNAME --password $POSTGRES_PASSWORD