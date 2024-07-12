import asyncio

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.dependencies import common_parameters, get_engine, get_openai_embed_client
from fastapi_app.embeddings import compute_text_embedding
from fastapi_app.postgres_models import Item


async def update_embeddings():
    engine = await get_engine()
    openai_embed = await get_openai_embed_client()
    common_params = await common_parameters()

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        async with session.begin():
            items = (await session.scalars(select(Item))).all()

            for item in items:
                item.embedding = await compute_text_embedding(
                    item.to_str_for_embedding(),
                    openai_client=openai_embed.client,
                    embed_model=common_params.openai_embed_model,
                    embedding_dimensions=common_params.openai_embed_dimensions,
                )

            await session.commit()


if __name__ == "__main__":
    load_dotenv(override=True)
    asyncio.run(update_embeddings())
