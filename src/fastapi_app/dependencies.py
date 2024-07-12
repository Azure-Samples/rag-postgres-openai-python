import logging
import os
from typing import Annotated

import azure.identity
from dotenv import load_dotenv
from fastapi import Depends
from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fastapi_app.openai_clients import create_openai_chat_client, create_openai_embed_client
from fastapi_app.postgres_engine import create_postgres_engine_from_env

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
    openai_embed_dimensions: int
    openai_chat_deployment: str
    openai_embed_deployment: str


async def common_parameters():
    """
    Get the common parameters for the FastAPI app
    """
    load_dotenv(override=True)
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_EMBED_HOST == "azure":
        openai_embed_deployment = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-ada-002")
        openai_embed_model = os.getenv("AZURE_OPENAI_EMBED_MODEL", "text-embedding-ada-002")
        openai_embed_dimensions = int(os.getenv("AZURE_OPENAI_EMBED_DIMENSIONS", 1536))
    else:
        openai_embed_deployment = "text-embedding-ada-002"
        openai_embed_model = os.getenv("OPENAICOM_EMBED_MODEL", "text-embedding-ada-002")
        openai_embed_dimensions = int(os.getenv("OPENAICOM_EMBED_DIMENSIONS", 1536))
    if OPENAI_CHAT_HOST == "azure":
        openai_chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-35-turbo")
        openai_chat_model = os.getenv("AZURE_OPENAI_CHAT_MODEL", "gpt-35-turbo")
    elif OPENAI_CHAT_HOST == "ollama":
        openai_chat_deployment = "phi3:3.8b"
        openai_chat_model = os.getenv("OLLAMA_CHAT_MODEL", "phi3:3.8b")
    else:
        openai_chat_deployment = "gpt-3.5-turbo"
        openai_chat_model = os.getenv("OPENAICOM_CHAT_MODEL", "gpt-3.5-turbo")
    return FastAPIAppContext(
        openai_chat_model=openai_chat_model,
        openai_embed_model=openai_embed_model,
        openai_embed_dimensions=openai_embed_dimensions,
        openai_chat_deployment=openai_chat_deployment,
        openai_embed_deployment=openai_embed_deployment,
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


async def get_engine():
    """Get the agent database engine"""
    load_dotenv(override=True)
    azure_credentials = await get_azure_credentials()
    engine = await create_postgres_engine_from_env(azure_credentials)
    return engine


async def get_async_session(engine: Annotated[AsyncEngine, Depends(get_engine)]):
    """Get the agent database"""
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as async_session:
        yield async_session


async def get_openai_chat_client():
    """Get the OpenAI chat client"""
    azure_credentials = await get_azure_credentials()
    chat_client = await create_openai_chat_client(azure_credentials)
    return OpenAIClient(client=chat_client)


async def get_openai_embed_client():
    """Get the OpenAI embed client"""
    azure_credentials = await get_azure_credentials()
    embed_client = await create_openai_embed_client(azure_credentials)
    return OpenAIClient(client=embed_client)


CommonDeps = Annotated[FastAPIAppContext, Depends(common_parameters)]
DBSession = Annotated[AsyncSession, Depends(get_async_session)]
ChatClient = Annotated[OpenAIClient, Depends(get_openai_chat_client)]
EmbeddingsClient = Annotated[OpenAIClient, Depends(get_openai_embed_client)]
