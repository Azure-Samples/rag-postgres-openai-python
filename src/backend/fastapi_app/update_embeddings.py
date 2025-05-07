import argparse
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.dependencies import common_parameters, get_azure_credential
from fastapi_app.embeddings import compute_text_embedding
from fastapi_app.openai_clients import create_openai_embed_client
from fastapi_app.postgres_engine import create_postgres_engine_from_env
from fastapi_app.postgres_models import Item

logger = logging.getLogger("ragapp")


async def update_embeddings(in_seed_data=False):
    azure_credential = await get_azure_credential()
    engine = await create_postgres_engine_from_env(azure_credential)
    openai_embed_client = await create_openai_embed_client(azure_credential)
    common_params = await common_parameters()

    embedding_column = ""
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    if OPENAI_EMBED_HOST == "azure":
        embedding_column = os.getenv("AZURE_OPENAI_EMBEDDING_COLUMN", "embedding_3l")
    elif OPENAI_EMBED_HOST == "ollama":
        embedding_column = os.getenv("OLLAMA_EMBEDDING_COLUMN", "embedding_nomic")
    elif OPENAI_EMBED_HOST == "github":
        embedding_column = os.getenv("GITHUB_EMBEDDING_COLUMN", "embedding_3l")
    else:
        embedding_column = os.getenv("OPENAICOM_EMBEDDING_COLUMN", "embedding_3l")
    logger.info(f"Updating embeddings in column: {embedding_column}")
    if in_seed_data:
        current_dir = os.path.dirname(os.path.realpath(__file__))
        rows = []
        with open(os.path.join(current_dir, "seed_data.json")) as f:
            seed_data_objects = json.load(f)
            for seed_data_object in seed_data_objects:
                # for each column in the JSON, store it in the same named attribute in the object
                attrs = {key: value for key, value in seed_data_object.items()}
                row = Item(**attrs)
                embedding = await compute_text_embedding(
                    row.to_str_for_embedding(),
                    openai_client=openai_embed_client,
                    embed_model=common_params.openai_embed_model,
                    embed_deployment=common_params.openai_embed_deployment,
                    embedding_dimensions=common_params.openai_embed_dimensions,
                )
                setattr(row, embedding_column, embedding)
                rows.append(row)
            # Write updated seed data to the file
            with open(os.path.join(current_dir, "seed_data.json"), "w") as f:
                json.dump([row.to_dict(include_embedding=True) for row in rows], f, indent=4)
        return

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        async with session.begin():
            rows_to_update = (await session.scalars(select(Item))).all()

            for row_model in rows_to_update:
                setattr(
                    row_model,
                    embedding_column,
                    await compute_text_embedding(
                        row_model.to_str_for_embedding(),
                        openai_client=openai_embed_client,
                        embed_model=common_params.openai_embed_model,
                        embed_deployment=common_params.openai_embed_deployment,
                        embedding_dimensions=common_params.openai_embed_dimensions,
                    ),
                )
            await session.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--in_seed_data", action="store_true")
    args = parser.parse_args()
    asyncio.run(update_embeddings(args.in_seed_data))
