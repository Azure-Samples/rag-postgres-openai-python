import fastapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.api_models import ChatRequest
from fastapi_app.globals import global_storage
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_advanced import AdvancedRAGChat
from fastapi_app.rag_simple import SimpleRAGChat

router = fastapi.APIRouter()


@router.get("/items/{id}")
async def item_handler(id: int):
    """A simple API to get an item by ID."""
    async_session_maker = async_sessionmaker(global_storage.engine, expire_on_commit=False)
    async with async_session_maker() as session:
        item = (await session.scalars(select(Item).where(Item.id == id))).first()
        return item.to_dict()


@router.get("/similar")
async def similar_handler(id: int, n: int = 5):
    """A similarity API to find items similar to items with given ID."""
    async_session_maker = async_sessionmaker(global_storage.engine, expire_on_commit=False)
    async with async_session_maker() as session:
        item = (await session.scalars(select(Item).where(Item.id == id))).first()
        closest = await session.execute(
            select(Item, Item.embedding.l2_distance(item.embedding))
            .filter(Item.id != id)
            .order_by(Item.embedding.l2_distance(item.embedding))
            .limit(n)
        )
        return [item.to_dict() | {"distance": round(distance, 2)} for item, distance in closest]


@router.get("/search")
async def search_handler(query: str, top: int = 5, enable_vector_search: bool = True, enable_text_search: bool = True):
    """A search API to find items based on a query."""
    searcher = PostgresSearcher(
        global_storage.engine,
        openai_embed_client=global_storage.openai_embed_client,
        embed_deployment=global_storage.openai_embed_deployment,
        embed_model=global_storage.openai_embed_model,
        embed_dimensions=global_storage.openai_embed_dimensions,
    )
    results = await searcher.search_and_embed(
        query, top=top, enable_vector_search=enable_vector_search, enable_text_search=enable_text_search
    )
    return [item.to_dict() for item in results]


@router.post("/chat")
async def chat_handler(chat_request: ChatRequest):
    messages = [message.model_dump() for message in chat_request.messages]
    overrides = chat_request.context.get("overrides", {})

    searcher = PostgresSearcher(
        global_storage.engine,
        openai_embed_client=global_storage.openai_embed_client,
        embed_deployment=global_storage.openai_embed_deployment,
        embed_model=global_storage.openai_embed_model,
        embed_dimensions=global_storage.openai_embed_dimensions,
    )
    if overrides.get("use_advanced_flow"):
        ragchat = AdvancedRAGChat(
            searcher=searcher,
            openai_chat_client=global_storage.openai_chat_client,
            chat_model=global_storage.openai_chat_model,
            chat_deployment=global_storage.openai_chat_deployment,
        )
    else:
        ragchat = SimpleRAGChat(
            searcher=searcher,
            openai_chat_client=global_storage.openai_chat_client,
            chat_model=global_storage.openai_chat_model,
            chat_deployment=global_storage.openai_chat_deployment,
        )

    response = await ragchat.run(messages, overrides=overrides)
    return response
