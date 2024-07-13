import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fastapi_app.dependencies import (
    FastAPIAppContext,
    common_parameters,
    create_async_sessionmaker,
    get_azure_credentials,
)
from fastapi_app.openai_clients import create_openai_chat_client, create_openai_embed_client
from fastapi_app.postgres_engine import create_postgres_engine_from_env

logger = logging.getLogger("ragapp")


class State(TypedDict):
    sessionmaker: async_sessionmaker[AsyncSession]
    context: FastAPIAppContext
    chat_client: AsyncOpenAI | AsyncAzureOpenAI
    embed_client: AsyncOpenAI | AsyncAzureOpenAI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    context = await common_parameters()
    azure_credential = await get_azure_credentials()
    engine = await create_postgres_engine_from_env(azure_credential)
    sessionmaker = await create_async_sessionmaker(engine)
    chat_client = await create_openai_chat_client(azure_credential)
    embed_client = await create_openai_embed_client(azure_credential)

    yield {"sessionmaker": sessionmaker, "context": context, "chat_client": chat_client, "embed_client": embed_client}
    await engine.dispose()


def create_app(testing: bool = False):
    if os.getenv("RUNNING_IN_PRODUCTION"):
        logging.basicConfig(level=logging.WARNING)
    else:
        if not testing:
            load_dotenv(override=True)
        logging.basicConfig(level=logging.INFO)

    app = FastAPI(docs_url="/docs", lifespan=lifespan)

    from fastapi_app.routes import api_routes, frontend_routes

    app.include_router(api_routes.router)
    app.mount("/", frontend_routes.router)

    return app
