import asyncio
import json
import logging
import os

from dotenv import load_dotenv

from fastapi_app.dependencies import common_parameters, get_azure_credential
from fastapi_app.embeddings import compute_text_embedding
from fastapi_app.openai_clients import create_openai_embed_client
from fastapi_app.postgres_models import Car

logger = logging.getLogger("ragapp")


async def update_cars_embeddings():
    azure_credential = await get_azure_credential()
    openai_embed_client = await create_openai_embed_client(azure_credential)
    common_params = await common_parameters()

    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    if OPENAI_EMBED_HOST == "azure":
        embedding_column = os.getenv("AZURE_OPENAI_EMBEDDING_COLUMN", "embedding_3l")
    elif OPENAI_EMBED_HOST == "ollama":
        embedding_column = os.getenv("OLLAMA_EMBEDDING_COLUMN", "embedding_nomic")
    else:
        embedding_column = os.getenv("OPENAICOM_EMBEDDING_COLUMN", "embedding_3l")

    logger.info(f"Updating car embeddings in column: {embedding_column}")

    current_dir = os.path.dirname(os.path.realpath(__file__))
    seed_file = os.path.join(current_dir, "cars_seed_data.json")

    with open(seed_file) as f:
        seed_data_objects = json.load(f)

    rows = []
    for seed_data_object in seed_data_objects:
        # Strip any existing embedding keys before constructing the model
        attrs = {k: v for k, v in seed_data_object.items() if k not in ("embedding_3l", "embedding_nomic")}
        row = Car(**attrs)

        embedding = await compute_text_embedding(
            row.to_str_for_embedding(),
            openai_client=openai_embed_client,
            embed_model=common_params.openai_embed_model,
            embed_deployment=common_params.openai_embed_deployment,
            embedding_dimensions=common_params.openai_embed_dimensions,
        )
        setattr(row, embedding_column, embedding)
        rows.append(row)
        logger.info(f"Embedded: {row.name}")

    # Write updated seed data (with embeddings) back to the file
    with open(seed_file, "w") as f:
        json.dump([row.to_dict(include_embedding=True) for row in rows], f, indent=4)

    logger.info(f"Done. Embeddings written to {seed_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(update_cars_embeddings())
