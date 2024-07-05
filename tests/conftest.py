import os
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app import create_app
from fastapi_app.globals import global_storage
from tests.mocks import MockAzureCredential

POSTGRES_HOST = "localhost"
POSTGRES_USERNAME = "admin"
POSTGRES_DATABASE = "postgres"
POSTGRES_PASSWORD = "postgres"
POSTGRES_SSL = "prefer"
POSTGRESQL_DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DATABASE}"
)


@pytest.fixture(scope="session")
def monkeypatch_session():
    with pytest.MonkeyPatch.context() as monkeypatch_session:
        yield monkeypatch_session


@pytest.fixture(scope="session")
def mock_session_env(monkeypatch_session):
    """Mock the environment variables for testing."""
    with mock.patch.dict(os.environ, clear=True):
        # Database
        monkeypatch_session.setenv("POSTGRES_HOST", POSTGRES_HOST)
        monkeypatch_session.setenv("POSTGRES_USERNAME", POSTGRES_USERNAME)
        monkeypatch_session.setenv("POSTGRES_DATABASE", POSTGRES_DATABASE)
        monkeypatch_session.setenv("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
        monkeypatch_session.setenv("POSTGRES_SSL", POSTGRES_SSL)
        monkeypatch_session.setenv("POSTGRESQL_DATABASE_URL", POSTGRESQL_DATABASE_URL)
        monkeypatch_session.setenv("RUNNING_IN_PRODUCTION", "False")
        # Azure Subscription
        monkeypatch_session.setenv("AZURE_SUBSCRIPTION_ID", "test-storage-subid")
        # OpenAI
        monkeypatch_session.setenv("AZURE_OPENAI_CHATGPT_MODEL", "gpt-35-turbo")
        monkeypatch_session.setenv("OPENAI_API_KEY", "fakekey")
        # Allowed Origin
        monkeypatch_session.setenv("ALLOWED_ORIGIN", "https://frontend.com")

        if os.getenv("AZURE_USE_AUTHENTICATION") is not None:
            monkeypatch_session.delenv("AZURE_USE_AUTHENTICATION")
        yield


@pytest.fixture(scope="session")
def app(mock_session_env):
    """Create a FastAPI app."""
    if not Path("src/static/").exists():
        pytest.skip("Please generate frontend files first!")
    return create_app(testing=True)


@pytest.fixture(scope="function")
def mock_default_azure_credential(mock_session_env):
    """Mock the Azure credential for testing."""
    with mock.patch("azure.identity.DefaultAzureCredential") as mock_default_azure_credential:
        mock_default_azure_credential.return_value = MockAzureCredential()
        yield mock_default_azure_credential


@pytest.fixture(scope="function")
def test_client(monkeypatch, app, mock_default_azure_credential):
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
