import os

import openai
import rich
from dotenv import load_dotenv

from rag_app.postgres_searcher import PostgresSearcher
from rag_app.rag_flow import RAGFlow


async def do_rag(question: str):
    load_dotenv()
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

    response = await rag_flow.answer(original_user_query=question, past_messages=[])
    return response


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(do_rag("Any climbing gear?"))
    rich.print(response)
