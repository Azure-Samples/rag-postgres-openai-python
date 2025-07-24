import pytest

from fastapi_app.dependencies import common_parameters
from fastapi_app.openai_clients import create_openai_chat_client, create_openai_embed_client
from tests.data import test_data


@pytest.mark.asyncio
async def test_create_openai_embed_client(mock_azure_credential, mock_openai_embedding):
    openai_embed_client = await create_openai_embed_client(mock_azure_credential)
    assert openai_embed_client.embeddings.create is not None
    embeddings = await openai_embed_client.embeddings.create(
        model="text-embedding-3-large", input="test", dimensions=1024
    )
    assert embeddings.data[0].embedding == test_data.embeddings


@pytest.mark.asyncio
async def test_create_openai_chat_client(mock_azure_credential, mock_openai_chatcompletion):
    openai_chat_client = await create_openai_chat_client(mock_azure_credential)
    assert openai_chat_client.chat.completions.create is not None
    response = await openai_chat_client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"content": "test", "role": "user"}]
    )
    assert response.choices[0].message.content == "The capital of France is Paris. [Benefit_Options-2.pdf]."


@pytest.mark.asyncio
async def test_github_models_configuration(monkeypatch):
    """Test that GitHub Models uses the correct URLs and model names."""
    # Set up environment for GitHub Models
    monkeypatch.setenv("OPENAI_CHAT_HOST", "github")
    monkeypatch.setenv("OPENAI_EMBED_HOST", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    # Don't set GITHUB_MODEL to test defaults

    # Test chat client configuration
    chat_client = await create_openai_chat_client(None)
    assert str(chat_client.base_url).rstrip("/") == "https://models.github.ai/inference"
    assert chat_client.api_key == "fake-token"

    # Test embed client configuration
    embed_client = await create_openai_embed_client(None)
    assert str(embed_client.base_url).rstrip("/") == "https://models.github.ai/inference"
    assert embed_client.api_key == "fake-token"

    # Test that dependencies use correct defaults
    context = await common_parameters()
    assert context.openai_chat_model == "openai/gpt-4o"
    assert context.openai_embed_model == "openai/text-embedding-3-large"


@pytest.mark.asyncio
async def test_github_models_with_custom_values(monkeypatch):
    """Test that GitHub Models respects custom environment values."""
    # Set up environment for GitHub Models with custom values
    monkeypatch.setenv("OPENAI_CHAT_HOST", "github")
    monkeypatch.setenv("OPENAI_EMBED_HOST", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_MODEL", "openai/gpt-4")
    monkeypatch.setenv("GITHUB_EMBED_MODEL", "openai/text-embedding-ada-002")

    # Test that dependencies use custom values
    context = await common_parameters()
    assert context.openai_chat_model == "openai/gpt-4"
    assert context.openai_embed_model == "openai/text-embedding-ada-002"
