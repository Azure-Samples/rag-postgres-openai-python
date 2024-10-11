import json
import pathlib
from typing import Final

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from openai_messages_token_helper import build_messages, get_token_limit

from rag_app.api_models import (
    AIChatRoles,
    Message,
    RAGContext,
    RetrievalResponse,
)
from rag_app.postgres_searcher import PostgresSearcher
from rag_app.query_rewriter import build_search_function, extract_search_arguments


class RAGFlow:
    current_dir = pathlib.Path(__file__).parent
    query_prompt_template = open(current_dir / "prompts/query.txt").read()
    query_fewshots = json.loads(open(current_dir / "prompts/query_fewshots.json").read())
    answer_prompt_template = open(current_dir / "prompts/answer.txt").read()

    def __init__(
        self, *, searcher: PostgresSearcher, openai_chat_client: AsyncOpenAI | AsyncAzureOpenAI, chat_model: str
    ):
        self.searcher = searcher
        self.openai_chat_client = openai_chat_client
        self.chat_model = chat_model
        self.chat_token_limit = get_token_limit(chat_model, default_to_minimum=True)

    async def answer(self, original_user_query: str, past_messages: list[dict]) -> RetrievalResponse:
        # Step 1: Query re-writing using OpenAI function calling
        tools = build_search_function()
        tool_choice: Final = "auto"

        query_response_token_limit = 500
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
            model=self.chat_model,
            temperature=0.0,  # Minimize creativity for search query generation
            max_tokens=query_response_token_limit,  # Setting too low risks malformed JSON, too high risks performance
            n=1,
            tools=tools,
            tool_choice=tool_choice,
        )

        query_text, filters = extract_search_arguments(original_user_query, chat_completion)

        # Step 2: Retrieve relevant rows from the database with the GPT optimized query
        results = await self.searcher.search_and_embed(
            query_text,
            top=3,
            filters=filters,
        )

        sources_content = [f"[{(item.id)}]:{item.to_str_for_rag()}\n\n" for item in results]
        content = "\n".join(sources_content)

        # Step 3: Generate a contextual and content specific answer using the search results and chat history
        response_token_limit = 1024
        contextual_messages: list[ChatCompletionMessageParam] = build_messages(
            model=self.chat_model,
            system_prompt=self.answer_prompt_template,
            new_user_content=original_user_query + "\n\nSources:\n" + content,
            past_messages=past_messages,
            max_tokens=self.chat_token_limit - response_token_limit,
            fallback_to_default=True,
        )

        chat_completion_response: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            model=self.chat_model,
            messages=contextual_messages,
            temperature=0.3,
            max_tokens=response_token_limit,
            n=1,
            stream=False,
        )

        return RetrievalResponse(
            message=Message(
                content=str(chat_completion_response.choices[0].message.content), role=AIChatRoles.ASSISTANT
            ),
            context=RAGContext(data_points={item.id: item.to_dict() for item in results}),
        )
