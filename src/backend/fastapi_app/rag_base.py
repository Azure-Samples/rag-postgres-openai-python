import json
import pathlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from fastapi_app.api_models import (
    ChatParams,
    ChatRequestOverrides,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
)
from fastapi_app.postgres_models import Item


class RAGChatBase(ABC):
    current_dir = pathlib.Path(__file__).parent
    query_prompt_template = open(current_dir / "prompts/query.txt").read()
    query_fewshots = json.loads(open(current_dir / "prompts/query_fewshots.json").read())
    answer_prompt_template = open(current_dir / "prompts/answer.txt").read()

    def get_params(self, messages: list[ChatCompletionMessageParam], overrides: ChatRequestOverrides) -> ChatParams:
        response_token_limit = 1024
        prompt_template = overrides.prompt_template or self.answer_prompt_template

        enable_text_search = overrides.retrieval_mode in ["text", "hybrid", None]
        enable_vector_search = overrides.retrieval_mode in ["vectors", "hybrid", None]

        original_user_query = messages[-1]["content"]
        if not isinstance(original_user_query, str):
            raise ValueError("The most recent message content must be a string.")
        past_messages = messages[:-1]

        return ChatParams(
            top=overrides.top,
            temperature=overrides.temperature,
            retrieval_mode=overrides.retrieval_mode,
            use_advanced_flow=overrides.use_advanced_flow,
            response_token_limit=response_token_limit,
            prompt_template=prompt_template,
            enable_text_search=enable_text_search,
            enable_vector_search=enable_vector_search,
            original_user_query=original_user_query,
            past_messages=past_messages,
        )

    @abstractmethod
    async def prepare_context(
        self, chat_params: ChatParams
    ) -> tuple[list[ChatCompletionMessageParam], list[Item], list[ThoughtStep]]:
        raise NotImplementedError

    @abstractmethod
    async def answer(
        self,
        chat_params: ChatParams,
        contextual_messages: list[ChatCompletionMessageParam],
        results: list[Item],
        earlier_thoughts: list[ThoughtStep],
    ) -> RetrievalResponse:
        raise NotImplementedError

    @abstractmethod
    async def answer_stream(
        self,
        chat_params: ChatParams,
        contextual_messages: list[ChatCompletionMessageParam],
        results: list[Item],
        earlier_thoughts: list[ThoughtStep],
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        raise NotImplementedError
        if False:
            yield 0
