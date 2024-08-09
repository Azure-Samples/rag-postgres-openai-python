import logging
import os
from collections.abc import AsyncGenerator
from typing import Annotated

import azure.identity
from fastapi import Depends, Request
from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = logging.getLogger("ragapp")


class OpenAIClient(BaseModel):
    """
    OpenAI client
    """

    client: AsyncOpenAI | AsyncAzureOpenAI
    model_config = {"arbitrary_types_allowed": True}


class FastAPIAppContext(BaseModel):
    """
    Context for the FastAPI app
    """

    openai_chat_model: str
    openai_embed_model: str
    openai_embed_dimensions: int | None
    openai_chat_deployment: str | None
    openai_embed_deployment: str | None
    embedding_column: str


async def common_parameters():
    """
    Get the common parameters for the FastAPI app
    """
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_EMBED_HOST == "azure":
        openai_embed_deployment = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-ada-002")
        openai_embed_model = os.getenv("AZURE_OPENAI_EMBED_MODEL", "text-embedding-ada-002")
        openai_embed_dimensions = int(os.getenv("AZURE_OPENAI_EMBED_DIMENSIONS", 1536))
        embedding_column = os.getenv("AZURE_OPENAI_EMBEDDING_COLUMN", "embedding_ada002")
    elif OPENAI_EMBED_HOST == "ollama":
        openai_embed_deployment = None
        openai_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        openai_embed_dimensions = None
        embedding_column = os.getenv("OLLAMA_EMBEDDING_COLUMN", "embedding_nomic")
    else:
        openai_embed_deployment = None
        openai_embed_model = os.getenv("OPENAICOM_EMBED_MODEL", "text-embedding-ada-002")
        openai_embed_dimensions = int(os.getenv("OPENAICOM_EMBED_DIMENSIONS", 1536))
        embedding_column = os.getenv("OPENAICOM_EMBEDDING_COLUMN", "embedding_ada002")
    if OPENAI_CHAT_HOST == "azure":
        openai_chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-35-turbo")
        openai_chat_model = os.getenv("AZURE_OPENAI_CHAT_MODEL", "gpt-35-turbo")
    elif OPENAI_CHAT_HOST == "ollama":
        openai_chat_deployment = None
        openai_chat_model = os.getenv("OLLAMA_CHAT_MODEL", "phi3:3.8b")
        openai_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    else:
        openai_chat_deployment = None
        openai_chat_model = os.getenv("OPENAICOM_CHAT_MODEL", "gpt-3.5-turbo")
    return FastAPIAppContext(
        openai_chat_model=openai_chat_model,
        openai_embed_model=openai_embed_model,
        openai_embed_dimensions=openai_embed_dimensions,
        openai_chat_deployment=openai_chat_deployment,
        openai_embed_deployment=openai_embed_deployment,
        embedding_column=embedding_column,
    )


async def get_azure_credentials() -> azure.identity.DefaultAzureCredential | azure.identity.ManagedIdentityCredential:
    azure_credential: azure.identity.DefaultAzureCredential | azure.identity.ManagedIdentityCredential
    try:
        if client_id := os.getenv("APP_IDENTITY_ID"):
            # Authenticate using a user-assigned managed identity on Azure
            # See web.bicep for value of APP_IDENTITY_ID
            logger.info(
                "Using managed identity for client ID %s",
                client_id,
            )
            azure_credential = azure.identity.ManagedIdentityCredential(client_id=client_id)
        else:
            azure_credential = azure.identity.DefaultAzureCredential()
        return azure_credential
    except Exception as e:
        logger.warning("Failed to authenticate to Azure: %s", e)
        raise e


async def create_async_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Get the agent database"""
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_async_sessionmaker(
    request: Request,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    yield request.state.sessionmaker


async def get_context(
    request: Request,
) -> FastAPIAppContext:
    return request.state.context


async def get_async_db_session(
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_async_sessionmaker)],
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        yield session


async def get_openai_chat_client(
    request: Request,
) -> OpenAIClient:
    """Get the OpenAI chat client"""
    return OpenAIClient(client=request.state.chat_client)


async def get_openai_embed_client(
    request: Request,
) -> OpenAIClient:
    """Get the OpenAI embed client"""
    return OpenAIClient(client=request.state.embed_client)


CommonDeps = Annotated[FastAPIAppContext, Depends(get_context)]
DBSession = Annotated[AsyncSession, Depends(get_async_db_session)]
ChatClient = Annotated[OpenAIClient, Depends(get_openai_chat_client)]
EmbeddingsClient = Annotated[OpenAIClient, Depends(get_openai_embed_client)]
