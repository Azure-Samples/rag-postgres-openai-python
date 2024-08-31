from collections.abc import AsyncGenerator
from typing import Any, Final

from openai import AsyncAzureOpenAI, AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam
from openai_messages_token_helper import build_messages, get_token_limit

from fastapi_app.api_models import (
    AIChatRoles,
    Message,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
)
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.query_rewriter import build_search_function, extract_search_arguments
from fastapi_app.rag_base import ChatParams, RAGChatBase


class AdvancedRAGChat(RAGChatBase):
    def __init__(
        self,
        *,
        searcher: PostgresSearcher,
        openai_chat_client: AsyncOpenAI | AsyncAzureOpenAI,
        chat_model: str,
        chat_deployment: str | None,  # Not needed for non-Azure OpenAI
    ):
        self.searcher = searcher
        self.openai_chat_client = openai_chat_client
        self.chat_model = chat_model
        self.chat_deployment = chat_deployment
        self.chat_token_limit = get_token_limit(chat_model, default_to_minimum=True)

    async def generate_search_query(
        self, original_user_query: str, past_messages: list[ChatCompletionMessageParam], query_response_token_limit: int
    ) -> tuple[list[ChatCompletionMessageParam], Any | str | None, list]:
        """Generate an optimized keyword search query based on the chat history and the last question"""

        tools = build_search_function()
        tool_choice: Final = "auto"

        query_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=self.query_prompt_template,
            few_shots=self.query_fewshots,
            new_user_content=original_user_query,
            past_messages=past_messages,
            max_tokens=self.chat_token_limit - query_response_token_limit,
            tools=tools,
            tool_choice=tool_choice,
            fallback_to_default=True,
        )

        chat_completion: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            messages=query_messages,
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            temperature=0.0,  # Minimize creativity for search query generation
            max_tokens=query_response_token_limit,  # Setting too low risks malformed JSON, too high risks performance
            n=1,
            tools=tools,
            tool_choice=tool_choice,
        )

        query_text, filters = extract_search_arguments(original_user_query, chat_completion)

        return query_messages, query_text, filters

    async def prepare_context(
        self, chat_params: ChatParams
    ) -> tuple[list[ChatCompletionMessageParam], list[Item], list[ThoughtStep]]:
        query_messages, query_text, filters = await self.generate_search_query(
            original_user_query=chat_params.original_user_query,
            past_messages=chat_params.past_messages,
            query_response_token_limit=500,
        )

        # Retrieve relevant items from the database with the GPT optimized query
        results = await self.searcher.search_and_embed(
            query_text,
            top=chat_params.top,
            enable_vector_search=chat_params.enable_vector_search,
            enable_text_search=chat_params.enable_text_search,
            filters=filters,
        )

        sources_content = [f"[{(item.id)}]:{item.to_str_for_rag()}\n\n" for item in results]
        content = "\n".join(sources_content)

        # Generate a contextual and content specific answer using the search results and chat history
        contextual_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=chat_params.prompt_template,
            new_user_content=chat_params.original_user_query + "\n\nSources:\n" + content,
            past_messages=chat_params.past_messages,
            max_tokens=self.chat_token_limit - chat_params.response_token_limit,
            fallback_to_default=True,
        )

        thoughts = [
            ThoughtStep(
                title="Prompt to generate search arguments",
                description=query_messages,
                props=(
                    {"model": self.chat_model, "deployment": self.chat_deployment}
                    if self.chat_deployment
                    else {"model": self.chat_model}
                ),
            ),
            ThoughtStep(
                title="Search using generated search arguments",
                description=query_text,
                props={
                    "top": chat_params.top,
                    "vector_search": chat_params.enable_vector_search,
                    "text_search": chat_params.enable_text_search,
                    "filters": filters,
                },
            ),
            ThoughtStep(
                title="Search results",
                description=[result.to_dict() for result in results],
            ),
        ]
        return contextual_messages, results, thoughts

    async def answer(
        self,
        chat_params: ChatParams,
        contextual_messages: list[ChatCompletionMessageParam],
        results: list[Item],
        earlier_thoughts: list[ThoughtStep],
    ) -> RetrievalResponse:
        chat_completion_response: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            messages=contextual_messages,
            temperature=chat_params.temperature,
            max_tokens=chat_params.response_token_limit,
            n=1,
            stream=False,
        )

        return RetrievalResponse(
            message=Message(
                content=str(chat_completion_response.choices[0].message.content), role=AIChatRoles.ASSISTANT
            ),
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
