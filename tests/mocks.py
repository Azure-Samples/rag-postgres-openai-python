import json
from collections import namedtuple

import openai.types
from azure.core.credentials_async import AsyncTokenCredential

MOCK_EMBEDDING_DIMENSIONS = 1536
MOCK_EMBEDDING_MODEL_NAME = "text-embedding-ada-002"

MockToken = namedtuple("MockToken", ["token", "expires_on", "value"])


class MockAzureCredential(AsyncTokenCredential):
    async def get_token(self, uri):
        return MockToken("", 9999999999, "")


class MockAzureCredentialExpired(AsyncTokenCredential):
    def __init__(self):
        self.access_number = 0

    async def get_token(self, uri):
        self.access_number += 1
        if self.access_number == 1:
            return MockToken("", 0, "")
        else:
            return MockToken("", 9999999999, "")


class MockAsyncPageIterator:
    def __init__(self, data):
        self.data = data

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.data:
            raise StopAsyncIteration
        return self.data.pop(0)  # This should be a list of dictionaries.


class MockCaption:
    def __init__(self, text, highlights=None, additional_properties=None):
        self.text = text
        self.highlights = highlights or []
        self.additional_properties = additional_properties or {}


class MockResponse:
    def __init__(self, text, status):
        self.text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self

    async def json(self):
        return json.loads(self.text)


class MockEmbeddingsClient:
    def __init__(self, create_embedding_response: openai.types.CreateEmbeddingResponse):
        self.create_embedding_response = create_embedding_response

    async def create(self, *args, **kwargs) -> openai.types.CreateEmbeddingResponse:
        return self.create_embedding_response


class MockClient:
    def __init__(self, embeddings_client):
        self.embeddings = embeddings_client


def mock_computervision_response():
    return MockResponse(
        status=200,
        text=json.dumps(
            {
                "vector": [
                    0.011925711,
                    0.023533698,
                    0.010133852,
                    0.0063544377,
                    -0.00038590943,
                    0.0013952175,
                    0.009054946,
                    -0.033573493,
                    -0.002028305,
                ],
                "modelVersion": "2022-04-11",
            }
        ),
    )


class MockSynthesisResult:
    def __init__(self, result):
        self.__result = result

    def get(self):
        return self.__result
