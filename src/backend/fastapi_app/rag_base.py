import pathlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from fastapi_app.api_models import (
    RetrievalResponse,
    RetrievalResponseDelta,
)
from fastapi_app.postgres_models import Item


class ChatParams(BaseModel):
    top: int = 3
    temperature: float = 0.3
    response_token_limit: int = 1024
    enable_text_search: bool
    enable_vector_search: bool
    original_user_query: str
    past_messages: list[ChatCompletionMessageParam]
    prompt_template: str


class RAGChatBase(ABC):
    current_dir = pathlib.Path(__file__).parent
    query_prompt_template = open(current_dir / "prompts/query.txt").read()
    answer_prompt_template = open(current_dir / "prompts/answer.txt").read()

    def get_params(self, messages: list[ChatCompletionMessageParam], overrides: dict[str, Any]) -> ChatParams:
        top: int = overrides.get("top", 3)
        temperature: float = overrides.get("temperature", 0.3)
        response_token_limit = 1024
        prompt_template = overrides.get("prompt_template") or self.answer_prompt_template

        enable_text_search = overrides.get("retrieval_mode") in ["text", "hybrid", None]
        enable_vector_search = overrides.get("retrieval_mode") in ["vectors", "hybrid", None]

        original_user_query = messages[-1]["content"]
        if not isinstance(original_user_query, str):
            raise ValueError("The most recent message content must be a string.")
        past_messages = messages[:-1]

        return ChatParams(
            top=top,
            temperature=temperature,
            response_token_limit=response_token_limit,
            prompt_template=prompt_template,
            enable_text_search=enable_text_search,
            enable_vector_search=enable_vector_search,
            original_user_query=original_user_query,
            past_messages=past_messages,
        )

    @abstractmethod
    async def retrieve_and_build_context(
        self,
        chat_params: ChatParams,
        *args,
        **kwargs,
    ) -> tuple[list[ChatCompletionMessageParam], list[Item]]:
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any] = {},
    ) -> RetrievalResponse:
        raise NotImplementedError

    @abstractmethod
    async def run_stream(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any] = {},
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        raise NotImplementedError
        if False:
            yield 0
