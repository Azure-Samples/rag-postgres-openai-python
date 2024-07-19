import os

import pytest


@pytest.mark.asyncio
async def test_index(test_client):
    """test the index route"""
    response = test_client.get("/")

    html_index_file_path = "src/backend/static/index.html"
    with open(html_index_file_path, "rb") as f:
        html_index_file = f.read()

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"
    assert response.headers["Content-Length"] == str(len(html_index_file))
    assert html_index_file == response.content


@pytest.mark.asyncio
async def test_favicon(test_client):
    """test the favicon route"""
    response = test_client.get("/favicon.ico")

    favicon_file_path = "src/backend/static/favicon.ico"
    with open(favicon_file_path, "rb") as f:
        favicon_file = f.read()

    assert response.status_code == 200
    assert response.headers["Content-Length"] == str(len(favicon_file))
    assert favicon_file == response.content


@pytest.mark.asyncio
async def test_assets_non_existent_404(test_client):
    """test the assets route with a non-existent file"""
    response = test_client.get("/assets/manifest.json")

    assert response.status_code == 404
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "22"
    assert b'{"detail":"Not Found"}' in response.content


@pytest.mark.asyncio
async def test_assets(test_client):
    """test the assets route with an existing file"""
    assets_dir_path = "src/backend/static/assets"
    assets_file_path = os.listdir(assets_dir_path)[0]

    with open(os.path.join(assets_dir_path, assets_file_path), "rb") as f:
        assets_file = f.read()

    response = test_client.get(f"/assets/{assets_file_path}")

    assert response.status_code == 200
    assert response.headers["Content-Length"] == str(len(assets_file))
    assert assets_file == response.content
