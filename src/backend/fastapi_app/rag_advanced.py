import os
from collections.abc import AsyncGenerator
from typing import Optional, TypedDict, Union

from openai import AsyncAzureOpenAI, AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam
from openai_messages_token_helper import get_token_limit
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from fastapi_app.api_models import (
    AIChatRoles,
    ItemPublic,
    Message,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
)
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_base import ChatParams, RAGChatBase

# Experiment #1: Annotated did not work!
# Experiment #2: Function-level docstring, Inline docstrings next to attributes
#  Function -level docstring leads to XML like this: <summary>Search ...
# Experiment #3: Move the docstrings below the attributes in triple-quoted strings - SUCCESS!!!


class PriceFilter(TypedDict):
    column: str = "price"
    """The column to filter on (always 'price' for this filter)"""

    comparison_operator: str
    """The operator for price comparison ('>', '<', '>=', '<=', '=')"""

    value: float
    """ The price value to compare against (e.g., 30.00) """


class BrandFilter(TypedDict):
    column: str = "brand"
    """The column to filter on (always 'brand' for this filter)"""

    comparison_operator: str
    """The operator for brand comparison ('=' or '!=')"""

    value: str
    """The brand name to compare against (e.g., 'AirStrider')"""


class SearchResults(TypedDict):
    items: list[ItemPublic]
    """List of items that match the search query and filters"""

    filters: list[Union[PriceFilter, BrandFilter]]
    """List of filters applied to the search results"""


class AdvancedRAGChat(RAGChatBase):
    def __init__(
        self,
        *,
        searcher: PostgresSearcher,
        openai_chat_client: Union[AsyncOpenAI, AsyncAzureOpenAI],
        chat_model: str,
        chat_deployment: Optional[str],  # Not needed for non-Azure OpenAI
    ):
        self.searcher = searcher
        self.openai_chat_client = openai_chat_client
        self.chat_model = chat_model
        self.chat_deployment = chat_deployment
        self.chat_token_limit = get_token_limit(chat_model, default_to_minimum=True)

    async def search_database(
        self,
        ctx: RunContext[ChatParams],
        search_query: str,
        price_filter: Optional[PriceFilter] = None,
        brand_filter: Optional[BrandFilter] = None,
    ) -> SearchResults:
        """
        Search PostgreSQL database for relevant products based on user query

        Args:
            search_query: Query string to use for full text search, e.g. 'red shoes'
            price_filter: Filter search results based on price of the product
            brand_filter: Filter search results based on brand of the product

        Returns:
            List of formatted items that match the search query and filters
        """
        # Only send non-None filters
        filters = []
        if price_filter:
            filters.append(price_filter)
        if brand_filter:
            filters.append(brand_filter)
        results = await self.searcher.search_and_embed(
            search_query,
            top=ctx.deps.top,
            enable_vector_search=ctx.deps.enable_vector_search,
            enable_text_search=ctx.deps.enable_text_search,
            filters=filters,
        )
        return SearchResults(items=[ItemPublic.model_validate(item.to_dict()) for item in results], filters=filters)

    async def prepare_context(self, chat_params: ChatParams) -> tuple[list[ItemPublic], list[ThoughtStep]]:
        model = OpenAIModel(
            os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"], provider=OpenAIProvider(openai_client=self.openai_chat_client)
        )
        agent = Agent(
            model,
            model_settings=ModelSettings(temperature=0.0, max_tokens=500, seed=chat_params.seed),
            system_prompt=self.query_prompt_template,
            tools=[self.search_database],
            output_type=SearchResults,
        )
        # TODO: Provide few-shot examples
        results = await agent.run(
            f"Find search results for user query: {chat_params.original_user_query}",
            # message_history=chat_params.past_messages, # TODO
            deps=chat_params,
        )
        items = results.output.items
        thoughts = [
            ThoughtStep(
                title="Prompt to generate search arguments",
                description=chat_params.past_messages,  # TODO: update this
                props=(
                    {"model": self.chat_model, "deployment": self.chat_deployment}
                    if self.chat_deployment
                    else {"model": self.chat_model}
                ),
            ),
            ThoughtStep(
                title="Search using generated search arguments",
                description=chat_params.original_user_query,  # TODO:
                props={
                    "top": chat_params.top,
                    "vector_search": chat_params.enable_vector_search,
                    "text_search": chat_params.enable_text_search,
                    "filters": [],  # TODO
                },
            ),
            ThoughtStep(
                title="Search results",
                description="",  # TODO
            ),
        ]
        return items, thoughts

    async def answer(
        self,
        chat_params: ChatParams,
        items: list[ItemPublic],
        earlier_thoughts: list[ThoughtStep],
    ) -> RetrievalResponse:
        agent = Agent(
            OpenAIModel(
                os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                provider=OpenAIProvider(openai_client=self.openai_chat_client),
            ),
            system_prompt=self.answer_prompt_template,
            model_settings=ModelSettings(
                temperature=chat_params.temperature, max_tokens=chat_params.response_token_limit, seed=chat_params.seed
            ),
        )

        item_references = [item.to_str_for_rag() for item in items]
        response = await agent.run(
            user_prompt=chat_params.original_user_query + "Sources:\n" + "\n".join(item_references),
            message_history=chat_params.past_messages,
        )

        return RetrievalResponse(
            message=Message(content=str(response.output), role=AIChatRoles.ASSISTANT),
            context=RAGContext(
                data_points={},  # TODO
                thoughts=earlier_thoughts
                + [
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description="",  # TODO: update
                        props=(
                            {"model": self.chat_model, "deployment": self.chat_deployment}
                            if self.chat_deployment
                            else {"model": self.chat_model}
                        ),
                    ),
                ],
            ),
        )

    async def answer_stream(
        self,
        chat_params: ChatParams,
        contextual_messages: list[ChatCompletionMessageParam],
        results: list[Item],
        earlier_thoughts: list[ThoughtStep],
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        chat_completion_async_stream: AsyncStream[
            ChatCompletionChunk
        ] = await self.openai_chat_client.chat.completions.create(
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            messages=contextual_messages,
            temperature=chat_params.temperature,
            max_tokens=chat_params.response_token_limit,
            n=1,
            stream=True,
        )

        yield RetrievalResponseDelta(
            context=RAGContext(
                data_points={item.id: item.to_dict() for item in results},
                thoughts=earlier_thoughts
                + [
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=contextual_messages,
                        props=(
                            {"model": self.chat_model, "deployment": self.chat_deployment}
                            if self.chat_deployment
                            else {"model": self.chat_model}
                        ),
                    ),
                ],
            ),
        )

        async for response_chunk in chat_completion_async_stream:
            # first response has empty choices and last response has empty content
            if response_chunk.choices and response_chunk.choices[0].delta.content:
                yield RetrievalResponseDelta(
                    delta=Message(content=str(response_chunk.choices[0].delta.content), role=AIChatRoles.ASSISTANT)
                )
        return
