import argparse
import asyncio
import logging

from dotenv import load_dotenv
from sqlalchemy import text

from fastapi_app.postgres_engine import create_postgres_engine_from_args, create_postgres_engine_from_env
from fastapi_app.postgres_models import Base

logger = logging.getLogger("ragapp")


async def create_db_schema(engine):
    async with engine.begin() as conn:
        logger.info("Enabling the pgvector extension for Postgres...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("Creating database tables and indexes...")
        await conn.run_sync(Base.metadata.create_all)

    await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Create database schema")
    parser.add_argument("--host", type=str, help="Postgres host")
    parser.add_argument("--username", type=str, help="Postgres username")
    parser.add_argument("--password", type=str, help="Postgres password")
    parser.add_argument("--database", type=str, help="Postgres database")
    parser.add_argument("--sslmode", type=str, help="Postgres sslmode")
    parser.add_argument("--tenant-id", type=str, help="Azure tenant ID", default=None)

    # if no args are specified, use environment variables
    args = parser.parse_args()
    if args.host is None:
        engine = await create_postgres_engine_from_env()
    else:
        engine = await create_postgres_engine_from_args(args)

    await create_db_schema(engine)

    await engine.dispose()

    logger.info("Database extension and tables created successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
