from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam
from openai_messages_token_helper import build_messages, get_token_limit

from fastapi_app.api_models import Message, RAGContext, RetrievalResponse, ThoughtStep
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.query_rewriter import build_search_function, extract_search_arguments
from fastapi_app.rag_simple import RAGChatBase


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

    async def run(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any] = {},
    ) -> RetrievalResponse:
        chat_params = self.get_params(messages, overrides)

        # Generate an optimized keyword search query based on the chat history and the last question
        query_response_token_limit = 500
        query_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=self.query_prompt_template,
            new_user_content=chat_params.original_user_query,
            past_messages=chat_params.past_messages,
            max_tokens=self.chat_token_limit - query_response_token_limit,  # TODO: count functions
            fallback_to_default=True,
        )

        chat_completion: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            messages=query_messages,
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            temperature=0.0,  # Minimize creativity for search query generation
            max_tokens=query_response_token_limit,  # Setting too low risks malformed JSON, too high risks performance
            n=1,
            tools=build_search_function(),
            tool_choice="auto",
        )

        query_text, filters = extract_search_arguments(chat_params.original_user_query, chat_completion)

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
        response_token_limit = 1024
        contextual_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=overrides.get("prompt_template") or self.answer_prompt_template,
            new_user_content=chat_params.original_user_query + "\n\nSources:\n" + content,
            past_messages=chat_params.past_messages,
            max_tokens=self.chat_token_limit - response_token_limit,
            fallback_to_default=True,
        )

        chat_completion_response: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            messages=contextual_messages,
            temperature=overrides.get("temperature", 0.3),
            max_tokens=response_token_limit,
            n=1,
            stream=False,
        )

        first_choice_message = chat_completion_response.choices[0].message

        return RetrievalResponse(
            message=Message(content=str(first_choice_message.content), role=first_choice_message.role),
            context=RAGContext(
                data_points={item.id: item.to_dict() for item in results},
                thoughts=[
                    ThoughtStep(
                        title="Prompt to generate search arguments",
                        description=[str(message) for message in query_messages],
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
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=[str(message) for message in contextual_messages],
                        props=(
                            {"model": self.chat_model, "deployment": self.chat_deployment}
                            if self.chat_deployment
                            else {"model": self.chat_model}
                        ),
                    ),
                ],
            ),
        )

    async def run_stream(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any] = {},
    ) -> AsyncGenerator[RetrievalResponse | Message, None]:
        chat_params = self.get_params(messages, overrides)

        # Generate an optimized keyword search query based on the chat history and the last question
        query_response_token_limit = 500
        query_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=self.query_prompt_template,
            new_user_content=chat_params.original_user_query,
            past_messages=chat_params.past_messages,
            max_tokens=self.chat_token_limit - query_response_token_limit,  # TODO: count functions
            fallback_to_default=True,
        )

        chat_completion: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            messages=query_messages,
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            temperature=0.0,  # Minimize creativity for search query generation
            max_tokens=query_response_token_limit,  # Setting too low risks malformed JSON, too high risks performance
            n=1,
            tools=build_search_function(),
            tool_choice="auto",
        )

        query_text, filters = extract_search_arguments(chat_params.original_user_query, chat_completion)

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
        response_token_limit = 1024
        contextual_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=overrides.get("prompt_template") or self.answer_prompt_template,
            new_user_content=chat_params.original_user_query + "\n\nSources:\n" + content,
            past_messages=chat_params.past_messages,
            max_tokens=self.chat_token_limit - response_token_limit,
            fallback_to_default=True,
        )

        chat_completion_async_stream: AsyncStream[
            ChatCompletionChunk
        ] = await self.openai_chat_client.chat.completions.create(
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            messages=contextual_messages,
            temperature=overrides.get("temperature", 0.3),
            max_tokens=response_token_limit,
            n=1,
            stream=True,
        )

        yield RetrievalResponse(
            message=Message(content="", role="assistant"),
            context=RAGContext(
                data_points={item.id: item.to_dict() for item in results},
                thoughts=[
                    ThoughtStep(
                        title="Prompt to generate search arguments",
                        description=[str(message) for message in query_messages],
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
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=[str(message) for message in contextual_messages],
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
            yield Message(content=str(response_chunk.choices[0].delta.content), role="assistant")
        return
