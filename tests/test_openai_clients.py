import pytest

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
