import asyncio
import json
import logging
import os

import openai
from dotenv import load_dotenv

from rag_app.embeddings import compute_text_embedding
from rag_app.postgres_models import Item

logger = logging.getLogger("ragapp")


async def update_embeddings(in_seed_data=False):
    openai_embed_client = openai.AsyncOpenAI(
        base_url="https://models.inference.ai.azure.com", api_key=os.getenv("GITHUB_TOKEN")
    )

    embedding_column = "embedding"
    logger.info(f"Updating embeddings in column: {embedding_column}")
    if in_seed_data:
        current_dir = os.path.dirname(os.path.realpath(__file__))
        rows = []
        # Create a new file for appending new embeddings
        new_seed_data_file = os.path.join(current_dir, "seed_data_two.json")

        with open(os.path.join(current_dir, "seed_data.json")) as f:
            seed_data_objects = json.load(f)
            for ind, seed_data_object in enumerate(seed_data_objects):
                print("Computing embedding for seed data index: ", ind)
                # for each column in the JSON, store it in the same named attribute in the object
                attrs = {key: value for key, value in seed_data_object.items()}
                row = Item(
                    id=attrs["id"],
                    description=attrs["description"],
                    type=attrs["type"],
                    brand=attrs["brand"],
                    price=attrs["price"],
                    name=attrs["name"],
                )
                row.embedding = await compute_text_embedding(
                    row.to_str_for_embedding(),
                    openai_client=openai_embed_client,
                    embed_model="text-embedding-3-small",
                    embedding_dimensions=256,
                )
                rows.append(row)
                with open(new_seed_data_file, "a") as f:
                    json.dump([row.to_dict(include_embedding=True)], f, indent=4)
                # wait 4 seconds to avoid rate limiting, 15 requests per minute
                await asyncio.sleep(5)
        return


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)

    asyncio.run(update_embeddings(True))
