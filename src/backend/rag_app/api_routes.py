import os

import fastapi
import openai

from rag_app.api_models import (
    ChatRequest,
    RetrievalResponse,
)
from rag_app.postgres_searcher import PostgresSearcher
from rag_app.rag_flow import RAGFlow

router = fastapi.APIRouter()


@router.post("/chat", response_model=RetrievalResponse)
async def chat_handler(chat_request: ChatRequest):
    openai_client = openai.AsyncOpenAI(
        base_url="https://models.inference.ai.azure.com", api_key=os.getenv("GITHUB_TOKEN")
    )
    searcher = PostgresSearcher(
        postgres_host=os.environ["POSTGRES_HOST"],
        postgres_username=os.environ["POSTGRES_USERNAME"],
        postgres_database=os.environ["POSTGRES_DATABASE"],
        postgres_password=os.environ.get("POSTGRES_PASSWORD"),
        openai_embed_client=openai_client,
        embed_model="text-embedding-3-small",
        embed_dimensions=256,
    )
    rag_flow = RAGFlow(searcher=searcher, openai_chat_client=openai_client, chat_model="gpt-4o-mini")

    response = await rag_flow.answer(
        original_user_query=chat_request.messages[-1]["content"],
        past_messages=chat_request.messages[:-1],
    )
    return response
