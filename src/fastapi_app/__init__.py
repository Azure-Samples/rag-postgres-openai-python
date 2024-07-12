import contextlib
import logging
import os

from dotenv import load_dotenv
from environs import Env
from fastapi import FastAPI

from fastapi_app.dependencies import get_azure_credentials
from fastapi_app.postgres_engine import create_postgres_engine_from_env

logger = logging.getLogger("ragapp")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(override=True)

    azure_credential = await get_azure_credentials()
    engine = await create_postgres_engine_from_env(azure_credential)

    yield

    await engine.dispose()


def create_app(testing: bool = False):
    env = Env()

    if os.getenv("RUNNING_IN_PRODUCTION"):
        logging.basicConfig(level=logging.WARNING)
    else:
        if not testing:
            env.read_env(".env", override=True)
        logging.basicConfig(level=logging.INFO)

    app = FastAPI(docs_url="/docs", lifespan=lifespan)

    from fastapi_app.routes import api_routes, frontend_routes

    app.include_router(api_routes.router)
    app.mount("/", frontend_routes.router)

    return app
