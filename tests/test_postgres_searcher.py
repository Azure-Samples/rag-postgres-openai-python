from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from fastapi_app.api_models import BrandFilter, Filter, ItemPublic, PriceFilter
from fastapi_app.postgres_searcher import PostgresSearcher
from tests.data import test_data


def test_postgres_build_filter_clause_without_filters(postgres_searcher):
    assert postgres_searcher.build_filter_clause(None) == ("", "", {})
    assert postgres_searcher.build_filter_clause([]) == ("", "", {})


def test_postgres_build_filter_clause_with_filters(postgres_searcher):
    assert postgres_searcher.build_filter_clause(
        [
            BrandFilter(comparison_operator="=", value="AirStrider"),
        ]
    ) == (
        "WHERE brand = :filter_0",
        "AND brand = :filter_0",
        {"filter_0": "AirStrider"},
    )


def test_postgres_build_filter_clause_with_filters_numeric(postgres_searcher):
    assert postgres_searcher.build_filter_clause(
        [
            PriceFilter(comparison_operator="<", value=30),
        ]
    ) == (
        "WHERE price < :filter_0",
        "AND price < :filter_0",
        {"filter_0": 30},
    )


def test_postgres_build_filter_clause_parameterizes_injection_payload(postgres_searcher):
    payload = "x' OR TRUE --"

    assert postgres_searcher.build_filter_clause([BrandFilter(comparison_operator="=", value=payload)]) == (
        "WHERE brand = :filter_0",
        "AND brand = :filter_0",
        {"filter_0": payload},
    )


def test_postgres_build_filter_clause_rejects_unsupported_filter(postgres_searcher):
    with pytest.raises(ValueError, match="Unsupported filter"):
        postgres_searcher.build_filter_clause([Filter(column="description", comparison_operator="=", value="tent")])


def test_filter_models_reject_overridden_columns_and_operators():
    with pytest.raises(ValidationError):
        BrandFilter.model_validate({"column": "description", "comparison_operator": "=", "value": "tent"})
    with pytest.raises(ValidationError):
        PriceFilter.model_validate({"comparison_operator": "OR TRUE --", "value": 30})


@pytest.mark.asyncio
async def test_postgres_searcher_search_empty_text_search(postgres_searcher):
    assert await postgres_searcher.search("", [], 5, None) == []


@pytest.mark.asyncio
async def test_postgres_searcher_search_binds_filter_value():
    db_session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = []
    db_session.execute.return_value = result
    searcher = PostgresSearcher(
        db_session=db_session,
        openai_embed_client=AsyncMock(),
        embed_deployment=None,
        embed_model="text-embedding-3-small",
        embed_dimensions=1536,
        embedding_column="embedding",
    )
    payload = "x' OR TRUE --"

    assert (
        await searcher.search(
            "",
            [],
            5,
            [BrandFilter(comparison_operator="=", value=payload)],
        )
        == []
    )
    sql, parameters = db_session.execute.await_args.args
    assert payload not in str(sql)
    assert parameters["filter_0"] == payload


@pytest.mark.asyncio
async def test_postgres_searcher_search(postgres_searcher):
    assert (await postgres_searcher.search(test_data.name, test_data.embeddings, 5, None))[0].to_dict() == ItemPublic(
        **test_data.model_dump()
    ).model_dump()


@pytest.mark.asyncio
async def test_postgres_searcher_search_and_embed_empty_text_search(postgres_searcher):
    assert await postgres_searcher.search_and_embed("", 5, False, True) == []


@pytest.mark.asyncio
async def test_postgres_searcher_search_and_embed(postgres_searcher):
    assert await postgres_searcher.search_and_embed("", 5, False, True) == []
    assert (await postgres_searcher.search_and_embed(test_data.name, 5, True))[0].to_dict() == ItemPublic(
        **test_data.model_dump()
    ).model_dump()
