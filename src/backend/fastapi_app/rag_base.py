import pathlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from openai.types.responses import ResponseInputItemParam

from fastapi_app.api_models import (
    ChatParams,
    ChatRequestOverrides,
    ItemPublic,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
)


class RAGChatBase(ABC):
    prompts_dir = pathlib.Path(__file__).parent / "prompts/"
    answer_prompt_template = open(prompts_dir / "answer.txt").read()

    def get_chat_params(self, messages: list[ResponseInputItemParam], overrides: ChatRequestOverrides) -> ChatParams:
        response_token_limit = 1024
        prompt_template = overrides.prompt_template or self.answer_prompt_template

        enable_text_search = overrides.retrieval_mode in ["text", "hybrid", None]
        enable_vector_search = overrides.retrieval_mode in ["vectors", "hybrid", None]

        original_user_query = messages[-1].get("content")
        if not isinstance(original_user_query, str):
            raise ValueError("The most recent message content must be a string.")

        return ChatParams(
            top=overrides.top,
            temperature=overrides.temperature,
            seed=overrides.seed,
            retrieval_mode=overrides.retrieval_mode,
            use_advanced_flow=overrides.use_advanced_flow,
            response_token_limit=response_token_limit,
            prompt_template=prompt_template,
            enable_text_search=enable_text_search,
            enable_vector_search=enable_vector_search,
            original_user_query=original_user_query,
            past_messages=messages[:-1],
        )

    @abstractmethod
    async def prepare_context(self) -> tuple[list[ItemPublic], list[ThoughtStep]]:
        raise NotImplementedError

    def prepare_rag_request(self, user_query, items: list[ItemPublic]) -> str:
        sources_str = "\n".join([f"[{item.id}]:{item.to_str_for_rag()}" for item in items])
        return f"{user_query}Sources:\n{sources_str}"

    @abstractmethod
    async def answer(
        self,
        items: list[ItemPublic],
        earlier_thoughts: list[ThoughtStep],
    ) -> RetrievalResponse:
        raise NotImplementedError

    @abstractmethod
    async def answer_stream(
        self,
        items: list[ItemPublic],
        earlier_thoughts: list[ThoughtStep],
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        raise NotImplementedError
        if False:
            yield 0
