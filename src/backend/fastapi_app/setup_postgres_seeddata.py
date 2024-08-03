import argparse
import asyncio
import json
import logging
import os

import sqlalchemy.exc
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.postgres_engine import (
    create_postgres_engine_from_args,
    create_postgres_engine_from_env,
)
from fastapi_app.postgres_models import Item

logger = logging.getLogger("ragapp")


async def seed_data(engine):
    # Check if Item table exists
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'items')"  # noqa
            )
        )
        if not result.scalar():
            logger.error("Items table does not exist. Please run the database setup script first.")
            return

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        # Insert the items from the JSON file into the database
        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, "seed_data.json")) as f:
            catalog_items = json.load(f)
            for catalog_item in catalog_items:
                db_item = await session.execute(select(Item).filter(Item.id == catalog_item["id"]))
                if db_item.scalars().first():
                    continue
                item = Item(
                    id=catalog_item["id"],
                    type=catalog_item["type"],
                    brand=catalog_item["brand"],
                    name=catalog_item["name"],
                    description=catalog_item["description"],
                    price=catalog_item["price"],
                    embedding_ada002=catalog_item["embedding_ada002"],
                    embedding_nomic=catalog_item.get("embedding_nomic"),
                )
                session.add(item)
            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                pass

    logger.info("Items table seeded successfully.")


async def main():
    parser = argparse.ArgumentParser(description="Create database schema")
    parser.add_argument("--host", type=str, help="Postgres host")
    parser.add_argument("--username", type=str, help="Postgres username")
    parser.add_argument("--password", type=str, help="Postgres password")
    parser.add_argument("--database", type=str, help="Postgres database")
    parser.add_argument("--sslmode", type=str, help="Postgres sslmode")

    # if no args are specified, use environment variables
    args = parser.parse_args()
    if args.host is None:
        engine = await create_postgres_engine_from_env()
    else:
        engine = await create_postgres_engine_from_args(args)

    await seed_data(engine)

    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
