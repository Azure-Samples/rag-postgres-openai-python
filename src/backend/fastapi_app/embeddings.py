from typing import (
    TypedDict,
)


async def compute_text_embedding(
    q: str, openai_client, embed_model: str, embed_deployment: str = None, embedding_dimensions: int = 1536
):
    SUPPORTED_DIMENSIONS_MODEL = {
        "text-embedding-ada-002": False,
        "text-embedding-3-small": True,
        "text-embedding-3-large": True,
    }

    class ExtraArgs(TypedDict, total=False):
        dimensions: int

    dimensions_args: ExtraArgs = {"dimensions": embedding_dimensions} if SUPPORTED_DIMENSIONS_MODEL[embed_model] else {}

    embedding = await openai_client.embeddings.create(
        # Azure OpenAI takes the deployment name as the model name
        model=embed_deployment if embed_deployment else embed_model,
        input=q,
        **dimensions_args,
    )
    return embedding.data[0].embedding
