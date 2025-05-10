import json
from collections.abc import AsyncGenerator
from typing import Optional, Union

from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseFunctionToolCallParam,
    ResponseTextDeltaEvent,
)
from openai.types.responses.response_input_item_param import FunctionCallOutput

from fastapi_app.api_models import (
    AIChatRoles,
    BrandFilter,
    ChatRequestOverrides,
    Filter,
    ItemPublic,
    Message,
    PriceFilter,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    SearchResults,
    ThoughtStep,
)
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_base import RAGChatBase

set_tracing_disabled(disabled=True)


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
        openai_agents_model = OpenAIChatCompletionsModel(
            model=chat_model if chat_deployment is None else chat_deployment, openai_client=openai_chat_client
        )
        self.search_agent = Agent(
            name="Searcher",
            instructions=self.query_prompt_template,
            tools=[function_tool(self.search_database)],
            tool_use_behavior="stop_on_first_tool",
            model=openai_agents_model,
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

    async def search_database(
        self,
        search_query: str,
        price_filter: Optional[PriceFilter] = None,
        brand_filter: Optional[BrandFilter] = None,
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
        if price_filter:
            filters.append(price_filter)
        if brand_filter:
            filters.append(brand_filter)
        results = await self.searcher.search_and_embed(
            search_query,
            top=self.chat_params.top,
            enable_vector_search=self.chat_params.enable_vector_search,
            enable_text_search=self.chat_params.enable_text_search,
            filters=filters,
        )
        return SearchResults(
            query=search_query, items=[ItemPublic.model_validate(item.to_dict()) for item in results], filters=filters
        )

    async def prepare_context(self) -> tuple[list[ItemPublic], list[ThoughtStep]]:
        few_shots = json.loads(self.query_fewshots)
        few_shot_inputs = []
        for few_shot in few_shots:
            if few_shot["role"] == "user":
                message = EasyInputMessageParam(role="user", content=few_shot["content"])
            elif few_shot["role"] == "assistant" and few_shot["tool_calls"] is not None:
                message = ResponseFunctionToolCallParam(
                    id="madeup",
                    call_id=few_shot["tool_calls"][0]["id"],
                    name=few_shot["tool_calls"][0]["function"]["name"],
                    arguments=few_shot["tool_calls"][0]["function"]["arguments"],
                    type="function_call",
                )
            elif few_shot["role"] == "tool" and few_shot["tool_call_id"] is not None:
                message = FunctionCallOutput(
                    id="madeupoutput",
                    call_id=few_shot["tool_call_id"],
                    output=few_shot["content"],
                    type="function_call_output",
                )
            few_shot_inputs.append(message)

        user_query = f"Find search results for user query: {self.chat_params.original_user_query}"
        new_user_message = EasyInputMessageParam(role="user", content=user_query)
        all_messages = few_shot_inputs + self.chat_params.past_messages + [new_user_message]

        run_results = await Runner.run(self.search_agent, input=all_messages)
        search_results = run_results.new_items[-1].output

        thoughts = [
            ThoughtStep(
                title="Prompt to generate search arguments",
                description=run_results.input,
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
                        description=run_results.input,
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
                        description=run_results.input,
                        props=self.model_for_thoughts,
                    ),
                ],
            ),
        )

        async for event in run_results.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield RetrievalResponseDelta(delta=Message(content=str(event.data.delta), role=AIChatRoles.ASSISTANT))
        return
