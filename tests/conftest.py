import json
import os
from pathlib import Path
from unittest import mock

import openai
import openai.resources
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from openai.types import CreateEmbeddingResponse, Embedding
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion import (
    ChatCompletionMessage,
    Choice,
)
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function
from openai.types.create_embedding_response import Usage
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app import create_app
from fastapi_app.openai_clients import create_openai_embed_client
from fastapi_app.postgres_engine import create_postgres_engine_from_env
from fastapi_app.setup_postgres_database import create_db_schema
from fastapi_app.setup_postgres_seeddata import seed_data
from tests.data import test_data
from tests.mocks import MockAzureCredential

# Always use localhost for testing
POSTGRES_HOST = "localhost"
POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME", "admin")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
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
    # Note that this does *not* clear existing env variables by default-
    # we used to specify clear=True but this caused issues with Playwright tests
    # https://github.com/microsoft/playwright-python/issues/2506
    with mock.patch.dict(os.environ):
        # Database
        monkeypatch_session.setenv("POSTGRES_HOST", POSTGRES_HOST)
        monkeypatch_session.setenv("POSTGRES_USERNAME", POSTGRES_USERNAME)
        monkeypatch_session.setenv("POSTGRES_DATABASE", POSTGRES_DATABASE)
        monkeypatch_session.setenv("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
        monkeypatch_session.setenv("POSTGRES_SSL", POSTGRES_SSL)
        monkeypatch_session.setenv("RUNNING_IN_PRODUCTION", "False")
        # Azure Subscription
        monkeypatch_session.setenv("AZURE_SUBSCRIPTION_ID", "test-storage-subid")
        # Azure OpenAI
        monkeypatch_session.setenv("OPENAI_CHAT_HOST", "azure")
        monkeypatch_session.setenv("OPENAI_EMBED_HOST", "azure")
        monkeypatch_session.setenv("AZURE_OPENAI_ENDPOINT", "https://api.openai.com")
        monkeypatch_session.setenv("AZURE_OPENAI_VERSION", "2024-03-01-preview")
        monkeypatch_session.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
        monkeypatch_session.setenv("AZURE_OPENAI_CHAT_MODEL", "gpt-4o-mini")
        monkeypatch_session.setenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-large")
        monkeypatch_session.setenv("AZURE_OPENAI_EMBED_MODEL", "text-embedding-3-large")
        monkeypatch_session.setenv("AZURE_OPENAI_EMBED_DIMENSIONS", "1024")
        monkeypatch_session.setenv("AZURE_OPENAI_EMBEDDING_COLUMN", "embedding_3l")
        monkeypatch_session.setenv("AZURE_OPENAI_KEY", "fakekey")

        yield


@pytest.fixture(scope="session")
def mock_session_env_openai(monkeypatch_session):
    """Mock the environment variables for testing."""
    # Note that this does *not* clear existing env variables by default-
    # we used to specify clear=True but this caused issues with Playwright tests
    # https://github.com/microsoft/playwright-python/issues/2506
    with mock.patch.dict(os.environ):
        # Database
        monkeypatch_session.setenv("POSTGRES_HOST", POSTGRES_HOST)
        monkeypatch_session.setenv("POSTGRES_USERNAME", POSTGRES_USERNAME)
        monkeypatch_session.setenv("POSTGRES_DATABASE", POSTGRES_DATABASE)
        monkeypatch_session.setenv("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
        monkeypatch_session.setenv("POSTGRES_SSL", POSTGRES_SSL)
        monkeypatch_session.setenv("RUNNING_IN_PRODUCTION", "False")
        # Azure Subscription
        monkeypatch_session.setenv("AZURE_SUBSCRIPTION_ID", "test-storage-subid")
        # OpenAI.com OpenAI
        monkeypatch_session.setenv("OPENAI_CHAT_HOST", "openai")
        monkeypatch_session.setenv("OPENAI_EMBED_HOST", "openai")
        monkeypatch_session.setenv("OPENAICOM_KEY", "fakekey")
        monkeypatch_session.setenv("OPENAICOM_CHAT_MODEL", "gpt-3.5-turbo")
        monkeypatch_session.setenv("OPENAICOM_EMBED_MODEL", "text-embedding-3-large")
        monkeypatch_session.setenv("OPENAICOM_EMBED_DIMENSIONS", "1024")
        monkeypatch_session.setenv("OPENAICOM_EMBEDDING_COLUMN", "embedding_3l")

        yield


@pytest.fixture(scope="session")
def mock_session_env_ollama(monkeypatch_session):
    """Mock the environment variables for testing."""
    # Note that this does *not* clear existing env variables by default-
    # we used to specify clear=True but this caused issues with Playwright tests
    # https://github.com/microsoft/playwright-python/issues/2506
    with mock.patch.dict(os.environ):
        # Database
        monkeypatch_session.setenv("POSTGRES_HOST", POSTGRES_HOST)
        monkeypatch_session.setenv("POSTGRES_USERNAME", POSTGRES_USERNAME)
        monkeypatch_session.setenv("POSTGRES_DATABASE", POSTGRES_DATABASE)
        monkeypatch_session.setenv("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
        monkeypatch_session.setenv("POSTGRES_SSL", POSTGRES_SSL)
        monkeypatch_session.setenv("RUNNING_IN_PRODUCTION", "False")
        # Azure Subscription
        monkeypatch_session.setenv("AZURE_SUBSCRIPTION_ID", "test-storage-subid")
        # Ollama OpenAI
        monkeypatch_session.setenv("OPENAI_CHAT_HOST", "ollama")
        monkeypatch_session.setenv("OPENAI_EMBED_HOST", "ollama")
        monkeypatch_session.setenv("OLLAMA_ENDPOINT", "http://host.docker.internal:11434/v1")
        monkeypatch_session.setenv("OLLAMA_CHAT_MODEL", "llama3.1")
        monkeypatch_session.setenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        monkeypatch_session.setenv("OLLAMA_EMBEDDING_COLUMN", "embedding_nomic")

        yield


async def create_and_seed_db():
    """Create and seed the database."""
    engine = await create_postgres_engine_from_env()
    await create_db_schema(engine)
    await seed_data(engine)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def app(mock_session_env):
    """Create a FastAPI app."""
    if not Path("src/backend/static/").exists():
        pytest.skip("Please generate frontend files first!")
    app = create_app(testing=True)
    await create_and_seed_db()
    return app


@pytest.fixture(scope="session")
def mock_openai_embedding(monkeypatch_session):
    async def mock_acreate(*args, **kwargs):
        return CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    embedding=test_data.embeddings,
                    index=0,
                    object="embedding",
                )
            ],
            model="text-embedding-3-large",
            usage=Usage(prompt_tokens=8, total_tokens=8),
        )

    monkeypatch_session.setattr(openai.resources.AsyncEmbeddings, "create", mock_acreate)

    yield


@pytest.fixture(scope="session")
def mock_openai_chatcompletion(monkeypatch_session):
    class AsyncChatCompletionIterator:
        def __init__(self, answer: str):
            chunk_id = "test-id"
            model = "gpt-4o-mini"
            self.responses = [
                {"object": "chat.completion.chunk", "choices": [], "id": chunk_id, "model": model, "created": 1},
                {
                    "object": "chat.completion.chunk",
                    "choices": [{"delta": {"role": "assistant"}, "index": 0, "finish_reason": None}],
                    "id": chunk_id,
                    "model": model,
                    "created": 1,
                },
            ]
            # Split at << to simulate chunked responses
            if answer.find("<<") > -1:
                parts = answer.split("<<")
                self.responses.append(
                    {
                        "object": "chat.completion.chunk",
                        "choices": [
                            {
                                "delta": {"role": "assistant", "content": parts[0] + "<<"},
                                "index": 0,
                                "finish_reason": None,
                            }
                        ],
                        "id": chunk_id,
                        "model": model,
                        "created": 1,
                    }
                )
                self.responses.append(
                    {
                        "object": "chat.completion.chunk",
                        "choices": [
                            {"delta": {"role": "assistant", "content": parts[1]}, "index": 0, "finish_reason": None}
                        ],
                        "id": chunk_id,
                        "model": model,
                        "created": 1,
                    }
                )
                self.responses.append(
                    {
                        "object": "chat.completion.chunk",
                        "choices": [{"delta": {"role": None, "content": None}, "index": 0, "finish_reason": "stop"}],
                        "id": chunk_id,
                        "model": model,
                        "created": 1,
                    }
                )
            else:
                self.responses.append(
                    {
                        "object": "chat.completion.chunk",
                        "choices": [{"delta": {"content": answer}, "index": 0, "finish_reason": None}],
                        "id": chunk_id,
                        "model": model,
                        "created": 1,
                    }
                )

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.responses:
                return ChatCompletionChunk.model_validate(self.responses.pop(0))
            else:
                raise StopAsyncIteration

    async def mock_acreate(*args, **kwargs):
        messages = kwargs["messages"]
        last_question = messages[-1]["content"]
        last_role = messages[-1]["role"]
        if last_role == "tool":
            items = json.loads(last_question)["items"]
            arguments = {"query": "capital of France", "items": items, "filters": []}
            return ChatCompletion(
                object="chat.completion",
                choices=[
                    Choice(
                        message=ChatCompletionMessage(
                            role="assistant",
                            tool_calls=[
                                ChatCompletionMessageToolCall(
                                    id="call_abc123final",
                                    type="function",
                                    function=Function(
                                        name="final_result",
                                        arguments=json.dumps(arguments),
                                    ),
                                )
                            ],
                        ),
                        finish_reason="stop",
                        index=0,
                    )
                ],
                id="test-123final",
                created=0,
                model="test-model",
            )
        if last_question == "Find search results for user query: What is the capital of France?":
            return ChatCompletion(
                object="chat.completion",
                choices=[
                    Choice(
                        message=ChatCompletionMessage(
                            role="assistant",
                            tool_calls=[
                                ChatCompletionMessageToolCall(
                                    id="call_abc123",
                                    type="function",
                                    function=Function(
                                        name="search_database", arguments='{"search_query":"climbing gear outside"}'
                                    ),
                                )
                            ],
                        ),
                        finish_reason="stop",
                        index=0,
                    )
                ],
                id="test-123",
                created=0,
                model="test-model",
            )
        elif last_question == "Find search results for user query: Are interest rates high?":
            answer = "interest rates"
        elif isinstance(last_question, list) and last_question[2].get("image_url"):
            answer = "From the provided sources, the impact of interest rates and GDP growth on "
            "financial markets can be observed through the line graph. [Financial Market Analysis Report 2023-7.png]"
        else:
            answer = "The capital of France is Paris. [Benefit_Options-2.pdf]."
            if messages[0]["content"].find("Generate 3 very brief follow-up questions") > -1:
                answer = "The capital of France is Paris. [Benefit_Options-2.pdf]. <<What is the capital of Spain?>>"
        if "stream" in kwargs and kwargs["stream"] is True:
            return AsyncChatCompletionIterator(answer)
        else:
            return ChatCompletion(
                object="chat.completion",
                choices=[
                    Choice(
                        message=ChatCompletionMessage(role="assistant", content=answer), finish_reason="stop", index=0
                    )
                ],
                id="test-123",
                created=0,
                model="test-model",
            )

    monkeypatch_session.setattr(openai.resources.chat.completions.AsyncCompletions, "create", mock_acreate)

    yield


@pytest.fixture(scope="function")
def mock_azure_credential(mock_session_env):
    """Mock the Azure credential for testing."""
    with mock.patch("azure.identity.AzureDeveloperCliCredential") as mock_azure_credential:
        mock_azure_credential.return_value = MockAzureCredential()
        yield mock_azure_credential


@pytest_asyncio.fixture(scope="function")
async def test_client(app, mock_azure_credential, mock_openai_embedding, mock_openai_chatcompletion):
    """Create a test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture(scope="function")
async def db_session(mock_session_env, mock_azure_credential):
    """Create a new database session with a rollback at the end of the test."""
    engine = await create_postgres_engine_from_env()
    async_sesion = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = async_sesion()
    await session.begin()
    yield session
    await session.rollback()
    await session.close()
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def postgres_searcher(mock_session_env, mock_azure_credential, db_session, mock_openai_embedding):
    from fastapi_app.postgres_searcher import PostgresSearcher

    openai_embed_client = await create_openai_embed_client(mock_azure_credential)

    yield PostgresSearcher(
        db_session=db_session,
        openai_embed_client=openai_embed_client,
        embed_deployment="text-embedding-3-large",
        embed_model="text-embedding-3-large",
        embed_dimensions=1024,
        embedding_column="embedding_3l",
    )
