import pytest

from fastapi_app.api_models import Filter, ItemPublic
from tests.data import test_data


def test_postgres_build_filter_clause_without_filters(postgres_searcher):
    assert postgres_searcher.build_filter_clause(None) == ("", "")
    assert postgres_searcher.build_filter_clause([]) == ("", "")


def test_postgres_build_filter_clause_with_filters(postgres_searcher):
    assert postgres_searcher.build_filter_clause(
        [
            Filter(column="brand", comparison_operator="=", value="AirStrider"),
        ]
    ) == (
        "WHERE brand = 'AirStrider'",
        "AND brand = 'AirStrider'",
    )


def test_postgres_build_filter_clause_with_filters_numeric(postgres_searcher):
    assert postgres_searcher.build_filter_clause(
        [
            Filter(column="price", comparison_operator="<", value=30),
        ]
    ) == (
        "WHERE price < 30",
        "AND price < 30",
    )


@pytest.mark.asyncio
async def test_postgres_searcher_search_empty_text_search(postgres_searcher):
    assert await postgres_searcher.search("", [], 5, None) == []


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
