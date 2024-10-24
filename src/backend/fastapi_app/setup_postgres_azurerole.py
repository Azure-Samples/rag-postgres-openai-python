import argparse
import asyncio
import logging

from dotenv import load_dotenv
from sqlalchemy import text

from fastapi_app.postgres_engine import create_postgres_engine_from_args

logger = logging.getLogger("ragapp")


async def assign_role_for_webapp(engine, app_identity_name):
    async with engine.begin() as conn:
        identities = await conn.execute(
            text(f"select * from pgaadauth_list_principals(false) WHERE rolname = '{app_identity_name}'")
        )

        if identities.rowcount > 0:
            logger.info(f"Found an existing PostgreSQL role for identity {app_identity_name}")
        else:
            logger.info(f"Creating a PostgreSQL role for identity {app_identity_name}")
            await conn.execute(text(f"SELECT * FROM pgaadauth_create_principal('{app_identity_name}', false, false)"))

        logger.info(f"Granting permissions to {app_identity_name}")
        # set role to azure_pg_admin
        await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{app_identity_name}"'))
        await conn.execute(text(f'GRANT CREATE ON SCHEMA public TO "{app_identity_name}"'))
        await conn.execute(text(f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{app_identity_name}"'))
        await conn.execute(
            text(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f'GRANT SELECT, UPDATE, INSERT, DELETE ON TABLES TO "{app_identity_name}"'
            )
        )

    await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Create database schema")
    parser.add_argument("--host", type=str, help="Postgres host")
    parser.add_argument("--username", type=str, help="Postgres username")
    parser.add_argument("--password", type=str, help="Postgres password", default=None)
    # You must connect to the *postgres* database when assigning roles
    parser.add_argument("--database", type=str, help="Postgres database", default="postgres")
    parser.add_argument("--sslmode", type=str, help="Postgres SSL mode", default=None)
    parser.add_argument("--tenant-id", type=str, help="Azure tenant ID", default=None)
    parser.add_argument("--app-identity-name", type=str, help="Azure App Service identity name")

    args = parser.parse_args()
    if not args.host.endswith(".database.azure.com"):
        logger.info("This script is intended to be used with Azure Database for PostgreSQL, not local PostgreSQL.")
        return

    engine = await create_postgres_engine_from_args(args)

    await assign_role_for_webapp(engine, args.app_identity_name)

    await engine.dispose()

    logger.info("Role created successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
