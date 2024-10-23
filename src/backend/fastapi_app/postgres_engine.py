import logging
import os

from azure.identity import AzureDeveloperCliCredential
from pgvector.asyncpg import register_vector
from sqlalchemy import event
from sqlalchemy.engine import AdaptedConnection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from fastapi_app.dependencies import get_azure_credential

logger = logging.getLogger("ragapp")


async def create_postgres_engine(*, host, username, database, password, sslmode, azure_credential) -> AsyncEngine:
    def get_password_from_azure_credential():
        token = azure_credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
        return token.token

    token_based_password = False
    if host.endswith(".database.azure.com"):
        token_based_password = True
        logger.info("Authenticating to Azure Database for PostgreSQL using Azure Identity...")
        if azure_credential is None:
            raise ValueError("Azure credential must be provided for Azure Database for PostgreSQL")
        password = get_password_from_azure_credential()
    else:
        logger.info("Authenticating to PostgreSQL using password...")

    DATABASE_URI = f"postgresql+asyncpg://{username}:{password}@{host}/{database}"
    # Specify SSL mode if needed
    if sslmode:
        DATABASE_URI += f"?ssl={sslmode}"

    engine = create_async_engine(DATABASE_URI, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def register_custom_types(dbapi_connection: AdaptedConnection, *args):
        logger.info("Registering pgvector extension...")
        try:
            dbapi_connection.run_async(register_vector)
        except ValueError:
            logger.warning("Could not register pgvector data type yet as vector extension has not been CREATEd")

    @event.listens_for(engine.sync_engine, "do_connect")
    def update_password_token(dialect, conn_rec, cargs, cparams):
        if token_based_password:
            logger.info("Updating password token for Azure Database for PostgreSQL")
            cparams["password"] = get_password_from_azure_credential()

    return engine


async def create_postgres_engine_from_env(azure_credential=None) -> AsyncEngine:
    if azure_credential is None and os.environ["POSTGRES_HOST"].endswith(".database.azure.com"):
        azure_credential = get_azure_credential()

    return await create_postgres_engine(
        host=os.environ["POSTGRES_HOST"],
        username=os.environ["POSTGRES_USERNAME"],
        database=os.environ["POSTGRES_DATABASE"],
        password=os.environ.get("POSTGRES_PASSWORD"),
        sslmode=os.environ.get("POSTGRES_SSL"),
        azure_credential=azure_credential,
    )


async def create_postgres_engine_from_args(args, azure_credential=None) -> AsyncEngine:
    if azure_credential is None and args.host.endswith(".database.azure.com"):
        if tenant_id := args.tenant_id:
            logger.info("Authenticating to Azure using Azure Developer CLI Credential for tenant %s", tenant_id)
            azure_credential = AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
        else:
            logger.info("Authenticating to Azure using Azure Developer CLI Credential")
            azure_credential = AzureDeveloperCliCredential(process_timeout=60)

    return await create_postgres_engine(
        host=args.host,
        username=args.username,
        database=args.database,
        password=args.password,
        sslmode=args.sslmode,
        azure_credential=azure_credential,
    )
