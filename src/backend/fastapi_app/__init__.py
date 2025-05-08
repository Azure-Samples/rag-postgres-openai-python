import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict, Union

import fastapi
from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI, AsyncOpenAI
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fastapi_app.dependencies import (
    FastAPIAppContext,
    common_parameters,
    create_async_sessionmaker,
    get_azure_credential,
)
from fastapi_app.openai_clients import create_openai_chat_client, create_openai_embed_client
from fastapi_app.postgres_engine import create_postgres_engine_from_env

logger = logging.getLogger("ragapp")


class State(TypedDict):
    sessionmaker: async_sessionmaker[AsyncSession]
    context: FastAPIAppContext
    chat_client: Union[AsyncOpenAI, AsyncAzureOpenAI]
    embed_client: Union[AsyncOpenAI, AsyncAzureOpenAI]


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> AsyncIterator[State]:
    context = await common_parameters()
    azure_credential = None
    if (
        os.getenv("OPENAI_CHAT_HOST") == "azure"
        or os.getenv("OPENAI_EMBED_HOST") == "azure"
        or os.getenv("POSTGRES_HOST", "").endswith(".database.azure.com")
    ):
        azure_credential = await get_azure_credential()
    engine = await create_postgres_engine_from_env(azure_credential)
    sessionmaker = await create_async_sessionmaker(engine)
    chat_client = await create_openai_chat_client(azure_credential)
    embed_client = await create_openai_embed_client(azure_credential)
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    yield {"sessionmaker": sessionmaker, "context": context, "chat_client": chat_client, "embed_client": embed_client}
    await engine.dispose()


def create_app(testing: bool = False):
    if os.getenv("RUNNING_IN_PRODUCTION"):
        # You may choose to reduce this to logging.WARNING for production
        logging.basicConfig(level=logging.INFO)
    else:
        if not testing:
            load_dotenv(override=True)
        logging.basicConfig(level=logging.INFO)

    # Turn off particularly noisy INFO level logs from Azure Core SDK:
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure.identity").setLevel(logging.WARNING)

    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logger.info("Configuring Azure Monitor")
        configure_azure_monitor(logger_name="ragapp")
        # OpenAI SDK requests use httpx, so are thus not auto-instrumented:
        OpenAIInstrumentor().instrument()

    app = fastapi.FastAPI(docs_url="/docs", lifespan=lifespan)

    from fastapi_app.routes import api_routes, frontend_routes

    app.include_router(api_routes.router)
    app.mount("/", frontend_routes.router)

    return app
