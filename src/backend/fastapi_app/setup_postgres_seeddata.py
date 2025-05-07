import argparse
import asyncio
import json
import logging
import os

import numpy as np
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
        table_name = Item.__tablename__
        result = await conn.execute(
            text(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}')"  # noqa
            )
        )
        if not result.scalar():
            logger.error(f" {table_name} table does not exist. Please run the database setup script first.")
            return

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        # Insert the objects from the JSON file into the database
        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, "seed_data.json")) as f:
            seed_data_objects = json.load(f)
            for seed_data_object in seed_data_objects:
                db_item = await session.execute(select(Item).filter(Item.id == seed_data_object["id"]))
                if db_item.scalars().first():
                    continue
                attrs = {key: value for key, value in seed_data_object.items()}
                attrs["embedding_3l"] = np.array(seed_data_object["embedding_3l"])
                attrs["embedding_nomic"] = np.array(seed_data_object["embedding_nomic"])
                column_names = ", ".join(attrs.keys())
                values = ", ".join([f":{key}" for key in attrs.keys()])
                await session.execute(text(f"INSERT INTO {table_name} ({column_names}) VALUES ({values})"), attrs)
            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                pass

    logger.info(f"{table_name} table seeded successfully.")


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

    await seed_data(engine)

    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
