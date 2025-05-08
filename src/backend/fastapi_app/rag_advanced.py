from collections.abc import AsyncGenerator
from typing import Optional, Union

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from fastapi_app.api_models import (
    AIChatRoles,
    ChatRequestOverrides,
    Filter,
    ItemPublic,
    Message,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    SearchArguments,
    SearchResults,
    ThoughtStep,
)
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_base import ChatParams, RAGChatBase


class AdvancedRAGChat(RAGChatBase):
    query_prompt_template = open(RAGChatBase.prompts_dir / "query.txt").read()
    query_fewshots = open(RAGChatBase.prompts_dir / "query_fewshots.json").read()

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
        self.search_agent = Agent[ChatParams, SearchResults](
            pydantic_chat_model,
            model_settings=ModelSettings(
                temperature=0.0,
                max_tokens=500,
                **({"seed": self.chat_params.seed} if self.chat_params.seed is not None else {}),
            ),
            system_prompt=self.query_prompt_template,
            tools=[self.search_database],
            output_type=SearchArguments,
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

    async def search_database(
        self,
        search_arguments: SearchArguments,
    ) -> SearchResults:
        """
        Search PostgreSQL database for relevant products based on user query

        Args:
            search_query: English query string to use for full text search, e.g. 'red shoes'.
            price_filter: Filter search results based on price of the product
            brand_filter: Filter search results based on brand of the product

        Returns:
            List of formatted items that match the search query and filters
        """
        # Only send non-None filters
        filters: list[Filter] = []
        if search_arguments.price_filter:
            filters.append(search_arguments.price_filter)
        if search_arguments.brand_filter:
            filters.append(search_arguments.brand_filter)
        results = await self.searcher.search_and_embed(
            search_arguments.search_query,
            top=self.chat_params.top,
            enable_vector_search=self.chat_params.enable_vector_search,
            enable_text_search=self.chat_params.enable_text_search,
            filters=filters,
        )
        return SearchResults(
            query=search_arguments.search_query,
            items=[ItemPublic.model_validate(item.to_dict()) for item in results],
            filters=filters,
        )

    async def prepare_context(self) -> tuple[list[ItemPublic], list[ThoughtStep]]:
        few_shots = ModelMessagesTypeAdapter.validate_json(self.query_fewshots)
        user_query = f"Find search results for user query: {self.chat_params.original_user_query}"
        search_agent_runner = await self.search_agent.run(
            user_query,
            message_history=few_shots + self.chat_params.past_messages,
            output_type=SearchArguments,
        )
        search_arguments = search_agent_runner.output
        search_results = await self.search_database(search_arguments=search_arguments)
        thoughts = [
            ThoughtStep(
                title="Prompt to generate search arguments",
                description=search_agent_runner.all_messages(),
                props=self.model_for_thoughts,
            ),
            ThoughtStep(
                title="Search using generated search arguments",
                description=search_results.query,
                props={
                    "top": self.chat_params.top,
                    "vector_search": self.chat_params.enable_vector_search,
                    "text_search": self.chat_params.enable_text_search,
                    "filters": search_results.filters,
                },
            ),
            ThoughtStep(
                title="Search results",
                description=search_results.items,
            ),
        ]
        return search_results.items, thoughts

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
