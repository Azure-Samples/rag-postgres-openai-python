from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount, Route, Router

parent_dir = Path(__file__).resolve().parent.parent.parent


async def index(request) -> FileResponse:
    return FileResponse(parent_dir / "static/index.html")


async def favicon(request):
    return FileResponse(parent_dir / "static/favicon.ico")


router = Router(
    routes=[
        Route("/", endpoint=index),
        Route("/favicon.ico", endpoint=favicon),
        Mount("/assets", app=StaticFiles(directory=parent_dir / "static/assets"), name="static_assets"),
    ]
)
