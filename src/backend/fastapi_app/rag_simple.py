from collections.abc import AsyncGenerator
from typing import Optional, Union

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from fastapi_app.api_models import (
    AIChatRoles,
    ChatRequestOverrides,
    ItemPublic,
    Message,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
)
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_base import RAGChatBase


class SimpleRAGChat(RAGChatBase):
    def __init__(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        overrides: ChatRequestOverrides,
        searcher: PostgresSearcher,
        openai_chat_client: Union[AsyncOpenAI, AsyncAzureOpenAI],
        chat_model: str,
        chat_deployment: Optional[str],  # Not needed for non-Azure OpenAI
    ):
        self.searcher = searcher
        self.chat_params = self.get_chat_params(messages, overrides)
        self.model_for_thoughts = (
            {"model": chat_model, "deployment": chat_deployment} if chat_deployment else {"model": chat_model}
        )
        pydantic_chat_model = OpenAIModel(
            chat_model if chat_deployment is None else chat_deployment,
            provider=OpenAIProvider(openai_client=openai_chat_client),
        )
        self.answer_agent = Agent(
            pydantic_chat_model,
            system_prompt=self.answer_prompt_template,
            model_settings=ModelSettings(
                temperature=self.chat_params.temperature,
                max_tokens=self.chat_params.response_token_limit,
                **({"seed": self.chat_params.seed} if self.chat_params.seed is not None else {}),
            ),
        )

    async def prepare_context(self) -> tuple[list[ItemPublic], list[ThoughtStep]]:
        """Retrieve relevant rows from the database and build a context for the chat model."""

        results = await self.searcher.search_and_embed(
            self.chat_params.original_user_query,
            top=self.chat_params.top,
            enable_vector_search=self.chat_params.enable_vector_search,
            enable_text_search=self.chat_params.enable_text_search,
        )
        items = [ItemPublic.model_validate(item.to_dict()) for item in results]

        thoughts = [
            ThoughtStep(
                title="Search query for database",
                description=self.chat_params.original_user_query,
                props={
                    "top": self.chat_params.top,
                    "vector_search": self.chat_params.enable_vector_search,
                    "text_search": self.chat_params.enable_text_search,
                },
            ),
            ThoughtStep(
                title="Search results",
                description=items,
            ),
        ]
        return items, thoughts

    async def answer(
        self,
        items: list[ItemPublic],
        earlier_thoughts: list[ThoughtStep],
    ) -> RetrievalResponse:
        response = await self.answer_agent.run(
            user_prompt=self.prepare_rag_request(self.chat_params.original_user_query, items),
            message_history=self.chat_params.past_messages,
        )
        return RetrievalResponse(
            message=Message(content=str(response.output), role=AIChatRoles.ASSISTANT),
            context=RAGContext(
                data_points={item.id: item for item in items},
                thoughts=earlier_thoughts
                + [
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=response.all_messages(),
                        props=self.model_for_thoughts,
                    ),
                ],
            ),
        )

    async def answer_stream(
        self,
        items: list[ItemPublic],
        earlier_thoughts: list[ThoughtStep],
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        async with self.answer_agent.run_stream(
            self.prepare_rag_request(self.chat_params.original_user_query, items),
            message_history=self.chat_params.past_messages,
        ) as agent_stream_runner:
            yield RetrievalResponseDelta(
                context=RAGContext(
                    data_points={item.id: item for item in items},
                    thoughts=earlier_thoughts
                    + [
                        ThoughtStep(
                            title="Prompt to generate answer",
                            description=agent_stream_runner.all_messages(),
                            props=self.model_for_thoughts,
                        ),
                    ],
                ),
            )

            async for message in agent_stream_runner.stream_text(delta=True, debounce_by=None):
                yield RetrievalResponseDelta(delta=Message(content=str(message), role=AIChatRoles.ASSISTANT))
            return
