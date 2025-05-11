from collections.abc import AsyncGenerator
from typing import Optional, Union

from agents import Agent, ItemHelpers, ModelSettings, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.responses import ResponseInputItemParam, ResponseTextDeltaEvent

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

set_tracing_disabled(disabled=True)


class SimpleRAGChat(RAGChatBase):
    def __init__(
        self,
        *,
        messages: list[ResponseInputItemParam],
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
        openai_agents_model = OpenAIChatCompletionsModel(
            model=chat_model if chat_deployment is None else chat_deployment, openai_client=openai_chat_client
        )
        self.answer_agent = Agent(
            name="Answerer",
            instructions=self.answer_prompt_template,
            model=openai_agents_model,
            model_settings=ModelSettings(
                temperature=self.chat_params.temperature,
                max_tokens=self.chat_params.response_token_limit,
                extra_body={"seed": self.chat_params.seed} if self.chat_params.seed is not None else {},
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
        run_results = await Runner.run(
            self.answer_agent,
            input=self.chat_params.past_messages
            + [{"content": self.prepare_rag_request(self.chat_params.original_user_query, items), "role": "user"}],
        )

        return RetrievalResponse(
            message=Message(content=str(run_results.final_output), role=AIChatRoles.ASSISTANT),
            context=RAGContext(
                data_points={item.id: item for item in items},
                thoughts=earlier_thoughts
                + [
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=[{"content": self.answer_prompt_template}]
                        + ItemHelpers.input_to_new_input_list(run_results.input),
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
        run_results = Runner.run_streamed(
            self.answer_agent,
            input=self.chat_params.past_messages
            + [{"content": self.prepare_rag_request(self.chat_params.original_user_query, items), "role": "user"}],
        )

        yield RetrievalResponseDelta(
            context=RAGContext(
                data_points={item.id: item for item in items},
                thoughts=earlier_thoughts
                + [
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=[{"content": self.answer_agent.instructions}]
                        + ItemHelpers.input_to_new_input_list(run_results.input),
                        props=self.model_for_thoughts,
                    ),
                ],
            ),
        )

        async for event in run_results.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield RetrievalResponseDelta(delta=Message(content=str(event.data.delta), role=AIChatRoles.ASSISTANT))
        return
