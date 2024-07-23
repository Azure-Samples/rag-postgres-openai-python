from collections.abc import AsyncGenerator

from openai import AsyncAzureOpenAI, AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam
from openai_messages_token_helper import build_messages, get_token_limit

from fastapi_app.api_models import (
    AIChatRoles,
    ChatRequestOverrides,
    Message,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
)
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_base import ChatParams, RAGChatBase


class SimpleRAGChat(RAGChatBase):
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

    async def retrieve_and_build_context(
        self, chat_params: ChatParams
    ) -> tuple[list[ChatCompletionMessageParam], list[Item]]:
        """Retrieve relevant items from the database and build a context for the chat model."""

        # Retrieve relevant items from the database
        results = await self.searcher.search_and_embed(
            chat_params.original_user_query,
            top=chat_params.top,
            enable_vector_search=chat_params.enable_vector_search,
            enable_text_search=chat_params.enable_text_search,
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
        return contextual_messages, results

    async def run(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: ChatRequestOverrides,
    ) -> RetrievalResponse:
        chat_params = self.get_params(messages, overrides)

        contextual_messages, results = await self.retrieve_and_build_context(chat_params=chat_params)

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
                thoughts=[
                    ThoughtStep(
                        title="Search query for database",
                        description=chat_params.original_user_query if chat_params.enable_text_search else None,
                        props={
                            "top": chat_params.top,
                            "vector_search": chat_params.enable_vector_search,
                            "text_search": chat_params.enable_text_search,
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
        overrides: ChatRequestOverrides,
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        chat_params = self.get_params(messages, overrides)

        contextual_messages, results = await self.retrieve_and_build_context(chat_params=chat_params)

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

        # Forcefully close the database session before yielding the response
        # Yielding keeps the connection open while streaming the response until the end
        # The connection closes when it returns back to the context manger in the dependencies
        await self.searcher.db_session.close()

        yield RetrievalResponseDelta(
            context=RAGContext(
                data_points={item.id: item.to_dict() for item in results},
                thoughts=[
                    ThoughtStep(
                        title="Search query for database",
                        description=chat_params.original_user_query if chat_params.enable_text_search else None,
                        props={
                            "top": chat_params.top,
                            "vector_search": chat_params.enable_vector_search,
                            "text_search": chat_params.enable_text_search,
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
            # first response has empty choices and last response has empty content
            if response_chunk.choices and response_chunk.choices[0].delta.content:
                yield RetrievalResponseDelta(
                    delta=Message(content=str(response_chunk.choices[0].delta.content), role=AIChatRoles.ASSISTANT)
                )
        return
