import pathlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam
from openai_messages_token_helper import build_messages, get_token_limit
from pydantic import BaseModel

from fastapi_app.api_models import Message, RAGContext, RetrievalResponse, ThoughtStep
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher


class ChatParams(BaseModel):
    top: int = 3
    temperature: float = 0.3
    response_token_limit: int = 1024
    enable_text_search: bool
    enable_vector_search: bool
    original_user_query: str
    past_messages: list[ChatCompletionMessageParam]
    prompt_template: str


class RAGChatBase(ABC):
    current_dir = pathlib.Path(__file__).parent
    query_prompt_template = open(current_dir / "prompts/query.txt").read()
    answer_prompt_template = open(current_dir / "prompts/answer.txt").read()

    def get_params(self, messages: list[ChatCompletionMessageParam], overrides: dict[str, Any]) -> ChatParams:
        top: int = overrides.get("top", 3)
        temperature: float = overrides.get("temperature", 0.3)
        response_token_limit = 1024
        prompt_template = overrides.get("prompt_template") or self.answer_prompt_template

        enable_text_search = overrides.get("retrieval_mode") in ["text", "hybrid", None]
        enable_vector_search = overrides.get("retrieval_mode") in ["vectors", "hybrid", None]

        original_user_query = messages[-1]["content"]
        if not isinstance(original_user_query, str):
            raise ValueError("The most recent message content must be a string.")
        past_messages = messages[:-1]

        return ChatParams(
            top=top,
            temperature=temperature,
            response_token_limit=response_token_limit,
            prompt_template=prompt_template,
            enable_text_search=enable_text_search,
            enable_vector_search=enable_vector_search,
            original_user_query=original_user_query,
            past_messages=past_messages,
        )

    @abstractmethod
    async def run(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any] = {},
    ) -> RetrievalResponse:
        raise NotImplementedError

    @abstractmethod
    async def retreive_and_build_context(
        self,
        chat_params: ChatParams,
        *args,
        **kwargs,
    ) -> tuple[list[ChatCompletionMessageParam], list[Item]]:
        raise NotImplementedError

    @abstractmethod
    async def run_stream(
        self,
        messages: list[ChatCompletionMessageParam],
        overrides: dict[str, Any] = {},
    ) -> AsyncGenerator[RetrievalResponse | Message, None]:
        raise NotImplementedError
        if False:
            yield 0


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

    async def retreive_and_build_context(
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
        overrides: dict[str, Any] = {},
    ) -> RetrievalResponse:
        chat_params = self.get_params(messages, overrides)

        # Retrieve relevant items from the database
        # Generate a contextual and content specific answer using the search results and chat history
        contextual_messages, results = await self.retreive_and_build_context(chat_params=chat_params)

        chat_completion_response: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            messages=contextual_messages,
            temperature=chat_params.temperature,
            max_tokens=chat_params.response_token_limit,
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
        overrides: dict[str, Any] = {},
    ) -> AsyncGenerator[RetrievalResponse | Message, None]:
        chat_params = self.get_params(messages, overrides)

        # Retrieve relevant items from the database
        # Generate a contextual and content specific answer using the search results and chat history
        contextual_messages, results = await self.retreive_and_build_context(chat_params=chat_params)

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

        # Forcefully Close the database session before yielding the response
        # Yielding keeps the connection open while streaming the response until the end
        # The connection closes when it returns back to the context manger in the dependencies
        await self.searcher.db_session.close()

        yield RetrievalResponse(
            message=Message(content="", role="assistant"),
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
            # first response has empty choices
            if response_chunk.choices:
                yield Message(content=str(response_chunk.choices[0].delta.content), role="assistant")
        return
