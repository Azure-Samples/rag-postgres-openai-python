import logging

import fastapi
from dotenv import load_dotenv

logger = logging.getLogger("ragapp")


def create_app(testing: bool = False):
    load_dotenv(override=True)
    logging.basicConfig(level=logging.INFO)

    app = fastapi.FastAPI()

    from rag_app import api_routes

    app.include_router(api_routes.router)

    return app
