import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app import create_app
from fastapi_app.globals import global_storage

POSTGRES_HOST = "localhost"
POSTGRES_USERNAME = "admin"
POSTGRES_DATABASE = "postgres"
POSTGRES_PASSWORD = "postgres"
POSTGRES_SSL = "prefer"
POSTGRESQL_DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DATABASE}"
)


@pytest.fixture(scope="session")
def setup_env():
    os.environ["POSTGRES_HOST"] = POSTGRES_HOST
    os.environ["POSTGRES_USERNAME"] = POSTGRES_USERNAME
    os.environ["POSTGRES_DATABASE"] = POSTGRES_DATABASE
    os.environ["POSTGRES_PASSWORD"] = POSTGRES_PASSWORD
    os.environ["POSTGRES_SSL"] = POSTGRES_SSL
    os.environ["POSTGRESQL_DATABASE_URL"] = POSTGRESQL_DATABASE_URL
    os.environ["RUNNING_IN_PRODUCTION"] = "False"
    os.environ["OPENAI_API_KEY"] = "fakekey"


@pytest.fixture(scope="session")
def mock_azure_credential():
    """Mock the Azure credential for testing."""
    with patch("azure.identity.DefaultAzureCredential", return_value=None):
        yield


@pytest.fixture(scope="session")
def app(setup_env, mock_azure_credential):
    """Create a FastAPI app."""
    if not Path("src/static/").exists():
        pytest.skip("Please generate frontend files first!")
    return create_app(is_testing=True)


@pytest.fixture(scope="function")
def test_client(app):
    """Create a test client."""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session():
    """Create a new database session with a rollback at the end of the test."""
    async_sesion = async_sessionmaker(autocommit=False, autoflush=False, bind=global_storage.engine)
    session = async_sesion()
    session.begin()
    yield session
    session.rollback()
    session.close()
