import pytest

from fastapi_app.dependencies import common_parameters, get_azure_credential


@pytest.mark.asyncio
async def test_get_common_parameters(mock_session_env):
    result = await common_parameters()
    assert result.openai_chat_model == "gpt-4o-mini"
    assert result.openai_embed_model == "text-embedding-3-large"
    assert result.openai_embed_dimensions == 1024
    assert result.openai_chat_deployment == "gpt-4o-mini"
    assert result.openai_embed_deployment == "text-embedding-3-large"


@pytest.mark.asyncio
async def test_get_common_parameters_ollama(mock_session_env_ollama):
    result = await common_parameters()
    assert result.openai_chat_model == "llama3.1"
    assert result.openai_embed_model == "nomic-embed-text"
    assert result.openai_embed_dimensions is None
    assert result.openai_chat_deployment is None
    assert result.openai_embed_deployment is None


@pytest.mark.asyncio
async def test_get_common_parameters_openai(mock_session_env_openai):
    result = await common_parameters()
    assert result.openai_chat_model == "gpt-3.5-turbo"
    assert result.openai_embed_model == "text-embedding-3-large"
    assert result.openai_embed_dimensions == 1024
    assert result.openai_chat_deployment is None
    assert result.openai_embed_deployment is None


@pytest.mark.asyncio
async def test_get_azure_credential(mock_session_env, mock_azure_credential):
    result = await get_azure_credential()
    token = result.get_token("https://vault.azure.net")
    assert token.expires_on == 9999999999
    assert token.token == ""
