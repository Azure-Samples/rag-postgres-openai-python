import pathlib
from collections.abc import AsyncGenerator
from typing import (
    Any,
)

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
)
from openai_messages_token_helper import build_messages, get_token_limit

from .api_models import ThoughtStep
from .postgres_searcher import PostgresSearcher
from .query_rewriter import build_search_function, extract_search_arguments


class AdvancedRAGChat:
    def __init__(
        self,
        *,
        searcher: PostgresSearcher,
        openai_chat_client: AsyncOpenAI,
        chat_model: str,
        chat_deployment: str | None,  # Not needed for non-Azure OpenAI
    ):
        self.searcher = searcher
        self.openai_chat_client = openai_chat_client
        self.chat_model = chat_model
        self.chat_deployment = chat_deployment
        self.chat_token_limit = get_token_limit(chat_model, default_to_minimum=True)
        current_dir = pathlib.Path(__file__).parent
        self.query_prompt_template = open(current_dir / "prompts/query.txt").read()
        self.answer_prompt_template = open(current_dir / "prompts/answer.txt").read()

    async def run(
        self, messages: list[dict], overrides: dict[str, Any] = {}
    ) -> dict[str, Any] | AsyncGenerator[dict[str, Any], None]:
        text_search = overrides.get("retrieval_mode") in ["text", "hybrid", None]
        vector_search = overrides.get("retrieval_mode") in ["vectors", "hybrid", None]
        top = overrides.get("top", 3)

        original_user_query = messages[-1]["content"]
        past_messages = messages[:-1]

        # Generate an optimized keyword search query based on the chat history and the last question
        query_response_token_limit = 500
        query_messages = build_messages(
            model=self.chat_model,
            system_prompt=self.query_prompt_template,
            new_user_content=original_user_query,
            past_messages=past_messages,
            max_tokens=self.chat_token_limit - query_response_token_limit,  # TODO: count functions
            fallback_to_default=True,
        )

        chat_completion: ChatCompletion = await self.openai_chat_client.chat.completions.create(
            messages=query_messages,  # type: ignore
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            temperature=0.0,  # Minimize creativity for search query generation
            max_tokens=query_response_token_limit,  # Setting too low risks malformed JSON, too high risks performance
            n=1,
            tools=build_search_function(),
            tool_choice="auto",
        )

        query_text, filters = extract_search_arguments(original_user_query, chat_completion)

        # Retrieve relevant items from the database with the GPT optimized query
        results = await self.searcher.search_and_embed(
            query_text,
            top=top,
            enable_vector_search=vector_search,
            enable_text_search=text_search,
            filters=filters,
        )

        sources_content = [f"[{(item.id)}]:{item.to_str_for_rag()}\n\n" for item in results]
        content = "\n".join(sources_content)

        # Generate a contextual and content specific answer using the search results and chat history
        response_token_limit = 1024
        messages = build_messages(
            model=self.chat_model,
            system_prompt=overrides.get("prompt_template") or self.answer_prompt_template,
            new_user_content=original_user_query + "\n\nSources:\n" + content,
            past_messages=past_messages,
            max_tokens=self.chat_token_limit - response_token_limit,
            fallback_to_default=True,
        )

        chat_completion_response = await self.openai_chat_client.chat.completions.create(
            # Azure OpenAI takes the deployment name as the model name
            model=self.chat_deployment if self.chat_deployment else self.chat_model,
            messages=messages,
            temperature=overrides.get("temperature", 0.3),
            max_tokens=response_token_limit,
            n=1,
            stream=False,
        )
        first_choice = chat_completion_response.model_dump()["choices"][0]
        return {
            "message": first_choice["message"],
            "context": {
                "data_points": {item.id: item.to_dict() for item in results},
                "thoughts": [
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
                            "top": top,
                            "vector_search": vector_search,
                            "text_search": text_search,
                            "filters": filters,
                        },
                    ),
                    ThoughtStep(
                        title="Search results",
                        description=[result.to_dict() for result in results],
                    ),
                    ThoughtStep(
                        title="Prompt to generate answer",
                        description=[str(message) for message in messages],
                        props=(
                            {"model": self.chat_model, "deployment": self.chat_deployment}
                            if self.chat_deployment
                            else {"model": self.chat_model}
                        ),
                    ),
                ],
            },
        }
