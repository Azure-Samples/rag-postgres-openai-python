import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.dependencies import common_parameters, get_azure_credentials
from fastapi_app.embeddings import compute_text_embedding
from fastapi_app.openai_clients import create_openai_embed_client
from fastapi_app.postgres_engine import create_postgres_engine_from_env
from fastapi_app.postgres_models import Item

logger = logging.getLogger("ragapp")


async def update_embeddings(in_seed_data=False):
    azure_credential = await get_azure_credentials()
    engine = await create_postgres_engine_from_env(azure_credential)
    openai_embed_client = await create_openai_embed_client(azure_credential)
    common_params = await common_parameters()

    embedding_column = ""
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    if OPENAI_EMBED_HOST == "azure":
        embedding_column = os.getenv("AZURE_OPENAI_EMBEDDING_COLUMN", "embedding_ada002")
    elif OPENAI_EMBED_HOST == "ollama":
        embedding_column = os.getenv("OLLAMA_EMBEDDING_COLUMN", "embedding_nomic")
    else:
        embedding_column = os.getenv("OPENAICOM_EMBEDDING_COLUMN", "embedding_ada002")
    logger.info(f"Updating embeddings in column: {embedding_column}")
    if in_seed_data:
        current_dir = os.path.dirname(os.path.realpath(__file__))
        items = []
        with open(os.path.join(current_dir, "seed_data.json")) as f:
            catalog_items = json.load(f)
            for catalog_item in catalog_items:
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
                embedding = await compute_text_embedding(
                    item.to_str_for_embedding(),
                    openai_client=openai_embed_client,
                    embed_model=common_params.openai_embed_model,
                    embed_deployment=common_params.openai_embed_deployment,
                    embedding_dimensions=common_params.openai_embed_dimensions,
                )
                setattr(item, embedding_column, embedding)
                items.append(item)
            # write to the file
            with open(os.path.join(current_dir, "seed_data.json"), "w") as f:
                json.dump([item.to_dict(include_embedding=True) for item in items], f, indent=4)
        return

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        async with session.begin():
            items_to_update = (await session.scalars(select(Item))).all()

            for item in items_to_update:
                setattr(
                    item,
                    embedding_column,
                    await compute_text_embedding(
                        item.to_str_for_embedding(),
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
    asyncio.run(update_embeddings())
