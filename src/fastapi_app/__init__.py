import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

logger = logging.getLogger("ragapp")


def create_app(testing: bool = False):
    if os.getenv("RUNNING_IN_PRODUCTION"):
        logging.basicConfig(level=logging.WARNING)
    else:
        if not testing:
            load_dotenv(override=True)
        logging.basicConfig(level=logging.INFO)

    app = FastAPI(docs_url="/docs")

    from fastapi_app.routes import api_routes, frontend_routes

    app.include_router(api_routes.router)
    app.mount("/", frontend_routes.router)

    return app
