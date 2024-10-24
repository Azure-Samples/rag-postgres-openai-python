import os

import pytest

from fastapi_app.postgres_engine import (
    create_postgres_engine,
    create_postgres_engine_from_args,
    create_postgres_engine_from_env,
)
from tests.conftest import POSTGRES_DATABASE, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_SSL, POSTGRES_USERNAME


@pytest.mark.asyncio
async def test_create_postgres_engine(mock_session_env, mock_azure_credential):
    engine = await create_postgres_engine(
        host=os.environ["POSTGRES_HOST"],
        username=os.environ["POSTGRES_USERNAME"],
        database=os.environ["POSTGRES_DATABASE"],
        password=os.environ.get("POSTGRES_PASSWORD"),
        sslmode=os.environ.get("POSTGRES_SSL"),
        azure_credential=mock_azure_credential,
    )
    assert engine.url.host == "localhost"
    assert engine.url.username == os.environ["POSTGRES_USERNAME"]
    assert engine.url.database == os.environ["POSTGRES_DATABASE"]
    assert engine.url.password == os.environ.get("POSTGRES_PASSWORD")
    assert engine.url.query["ssl"] == "prefer"


@pytest.mark.asyncio
async def test_create_postgres_engine_from_env(mock_session_env, mock_azure_credential):
    engine = await create_postgres_engine_from_env(
        azure_credential=mock_azure_credential,
    )
    assert engine.url.host == "localhost"
    assert engine.url.username == os.environ["POSTGRES_USERNAME"]
    assert engine.url.database == os.environ["POSTGRES_DATABASE"]
    assert engine.url.password == os.environ.get("POSTGRES_PASSWORD")
    assert engine.url.query["ssl"] == "prefer"


@pytest.mark.asyncio
async def test_create_postgres_engine_from_args(mock_azure_credential):
    args = type(
        "Args",
        (),
        {
            "host": POSTGRES_HOST,
            "username": POSTGRES_USERNAME,
            "database": POSTGRES_DATABASE,
            "password": POSTGRES_PASSWORD,
            "sslmode": POSTGRES_SSL,
        },
    )
    engine = await create_postgres_engine_from_args(
        args=args,
        azure_credential=mock_azure_credential,
    )
    assert engine.url.host == "localhost"
    assert engine.url.username == os.environ["POSTGRES_USERNAME"]
    assert engine.url.database == os.environ["POSTGRES_DATABASE"]
    assert engine.url.password == os.environ.get("POSTGRES_PASSWORD")
    assert engine.url.query["ssl"] == "prefer"
