from typing import (
    TypedDict,
)

from openai import AsyncAzureOpenAI, AsyncOpenAI


async def compute_text_embedding(
    q: str,
    openai_client: AsyncOpenAI | AsyncAzureOpenAI,
    embed_model: str,
    embedding_dimensions: int | None = None,
) -> list[float]:
    SUPPORTED_DIMENSIONS_MODEL = {
        "text-embedding-ada-002": False,
        "text-embedding-3-small": True,
        "text-embedding-3-large": True,
    }

    class ExtraArgs(TypedDict, total=False):
        dimensions: int

    dimensions_args: ExtraArgs = {}
    if SUPPORTED_DIMENSIONS_MODEL.get(embed_model):
        if embedding_dimensions is None:
            raise ValueError(f"Model {embed_model} requires embedding dimensions")
        else:
            dimensions_args = {"dimensions": embedding_dimensions}

    embedding = await openai_client.embeddings.create(
        # Azure OpenAI takes the deployment name as the model name
        model=embed_model,
        input=q,
        **dimensions_args,
    )
    return embedding.data[0].embedding
