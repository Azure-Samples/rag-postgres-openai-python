import json
import logging
from collections.abc import AsyncGenerator
from typing import Union

import fastapi
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openai import APIError
from sqlalchemy import select, text

from fastapi_app.api_models import (
    ChatRequest,
    ErrorResponse,
    ItemPublic,
    ItemWithDistance,
    RetrievalResponse,
    RetrievalResponseDelta,
)
from fastapi_app.dependencies import ChatClient, CommonDeps, DBSession, EmbeddingsClient
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_advanced import AdvancedRAGChat
from fastapi_app.rag_simple import SimpleRAGChat

router = fastapi.APIRouter()


ERROR_FILTER = {"error": "Your message contains content that was flagged by the content filter."}


async def format_as_ndjson(r: AsyncGenerator[RetrievalResponseDelta, None]) -> AsyncGenerator[str, None]:
    """
    Format the response as NDJSON
    """
    try:
        async for event in r:
            yield event.model_dump_json() + "\n"
    except Exception as error:
        if isinstance(error, APIError) and error.code == "content_filter":
            yield json.dumps(ERROR_FILTER) + "\n"
        else:
            logging.exception("Exception while generating response stream: %s", error)
            yield json.dumps({"error": str(error)}, ensure_ascii=False) + "\n"


@router.get("/items/{id}", response_model=ItemPublic)
async def item_handler(database_session: DBSession, id: int) -> ItemPublic:
    """A simple API to get an item by ID."""
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)
    return ItemPublic.model_validate(item.to_dict())


@router.get("/similar", response_model=list[ItemWithDistance])
async def similar_handler(
    context: CommonDeps, database_session: DBSession, id: int, n: int = 5
) -> list[ItemWithDistance]:
    """A similarity API to find items similar to items with given ID."""
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)

    closest = (
        await database_session.execute(
            text(
                f"SELECT *, {context.embedding_column} <=> :embedding as DISTANCE FROM {Item.__tablename__} "
                "WHERE id <> :item_id ORDER BY distance LIMIT :n"
            ),
            {"embedding": getattr(item, context.embedding_column), "n": n, "item_id": id},
        )
    ).fetchall()

    items = [dict(row._mapping) for row in closest]
    return [ItemWithDistance.model_validate(item) for item in items]


@router.get("/search", response_model=list[ItemPublic])
async def search_handler(
    context: CommonDeps,
    database_session: DBSession,
    openai_embed: EmbeddingsClient,
    query: str,
    top: int = 5,
    enable_vector_search: bool = True,
    enable_text_search: bool = True,
) -> list[ItemPublic]:
    """A search API to find items based on a query."""
    searcher = PostgresSearcher(
        db_session=database_session,
        openai_embed_client=openai_embed.client,
        embed_deployment=context.openai_embed_deployment,
        embed_model=context.openai_embed_model,
        embed_dimensions=context.openai_embed_dimensions,
        embedding_column=context.embedding_column,
    )
    results = await searcher.search_and_embed(
        query, top=top, enable_vector_search=enable_vector_search, enable_text_search=enable_text_search
    )
    return [ItemPublic.model_validate(item.to_dict()) for item in results]


@router.post("/chat", response_model=Union[RetrievalResponse, ErrorResponse])
async def chat_handler(
    context: CommonDeps,
    database_session: DBSession,
    openai_embed: EmbeddingsClient,
    openai_chat: ChatClient,
    chat_request: ChatRequest,
):
    try:
        searcher = PostgresSearcher(
            db_session=database_session,
            openai_embed_client=openai_embed.client,
            embed_deployment=context.openai_embed_deployment,
            embed_model=context.openai_embed_model,
            embed_dimensions=context.openai_embed_dimensions,
            embedding_column=context.embedding_column,
        )
        rag_flow: Union[SimpleRAGChat, AdvancedRAGChat]
        if chat_request.context.overrides.use_advanced_flow:
            rag_flow = AdvancedRAGChat(
                messages=chat_request.messages,
                overrides=chat_request.context.overrides,
                searcher=searcher,
                openai_chat_client=openai_chat.client,
                chat_model=context.openai_chat_model,
                chat_deployment=context.openai_chat_deployment,
            )
        else:
            rag_flow = SimpleRAGChat(
                messages=chat_request.messages,
                overrides=chat_request.context.overrides,
                searcher=searcher,
                openai_chat_client=openai_chat.client,
                chat_model=context.openai_chat_model,
                chat_deployment=context.openai_chat_deployment,
            )

        items, thoughts = await rag_flow.prepare_context()
        response = await rag_flow.answer(items=items, earlier_thoughts=thoughts)
        return response
    except Exception as e:
        if isinstance(e, APIError) and e.code == "content_filter":
            return ERROR_FILTER
        else:
            logging.exception("Exception while generating response: %s", e)
            return {"error": str(e)}


@router.post("/chat/stream")
async def chat_stream_handler(
    context: CommonDeps,
    database_session: DBSession,
    openai_embed: EmbeddingsClient,
    openai_chat: ChatClient,
    chat_request: ChatRequest,
):
    searcher = PostgresSearcher(
        db_session=database_session,
        openai_embed_client=openai_embed.client,
        embed_deployment=context.openai_embed_deployment,
        embed_model=context.openai_embed_model,
        embed_dimensions=context.openai_embed_dimensions,
        embedding_column=context.embedding_column,
    )

    rag_flow: Union[SimpleRAGChat, AdvancedRAGChat]
    if chat_request.context.overrides.use_advanced_flow:
        rag_flow = AdvancedRAGChat(
            messages=chat_request.messages,
            overrides=chat_request.context.overrides,
            searcher=searcher,
            openai_chat_client=openai_chat.client,
            chat_model=context.openai_chat_model,
            chat_deployment=context.openai_chat_deployment,
        )
    else:
        rag_flow = SimpleRAGChat(
            messages=chat_request.messages,
            overrides=chat_request.context.overrides,
            searcher=searcher,
            openai_chat_client=openai_chat.client,
            chat_model=context.openai_chat_model,
            chat_deployment=context.openai_chat_deployment,
        )

    try:
        # Intentionally do search we stream down the answer, to avoid using database connections during stream
        # See https://github.com/tiangolo/fastapi/discussions/11321
        items, thoughts = await rag_flow.prepare_context()
        result = rag_flow.answer_stream(items, thoughts)
        return StreamingResponse(content=format_as_ndjson(result), media_type="application/x-ndjson")
    except Exception as e:
        if isinstance(e, APIError) and e.code == "content_filter":
            return StreamingResponse(
                content=json.dumps(ERROR_FILTER) + "\n",
                media_type="application/x-ndjson",
            )
        else:
            logging.exception("Exception while generating response: %s", e)
            return StreamingResponse(
                content=json.dumps({"error": str(e)}, ensure_ascii=False) + "\n",
                media_type="application/x-ndjson",
            )
