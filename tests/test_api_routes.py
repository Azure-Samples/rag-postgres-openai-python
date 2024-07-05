import pytest

from tests.data import test_data


@pytest.mark.asyncio
async def test_item_handler(test_client):
    """test the item_handler route"""
    response = test_client.get(f"/items/{test_data.id}")
    response_data = response.json()

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "405"
    assert response_data["id"] == test_data.id
    assert response_data["name"] == test_data.name
    assert response_data["description"] == test_data.description
    assert response_data["price"] == test_data.price
    assert response_data["type"] == test_data.type
    assert response_data["brand"] == test_data.brand


@pytest.mark.asyncio
async def test_item_handler_404(test_client):
    """test the item_handler route with a non-existent item"""
    item_id = 10000000
    response = test_client.get(f"/items/{item_id}")

    assert response.status_code == 404
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "45"
    assert bytes(f'{{"detail":"Item with ID {item_id} not found."}}', "utf-8") in response.content


@pytest.mark.asyncio
async def test_similar_handler(test_client):
    """test the similar_handler route"""
    response = test_client.get("/similar?id=1&n=1")

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "428"
    assert response.json() == [
        {
            "id": 71,
            "name": "Explorer Frost Boots",
            "price": 149.99,
            "distance": 0.47,
            "type": "Footwear",
            "brand": "Daybird",
            "description": "The Explorer Frost Boots by Daybird are the perfect companion for "
            "cold-weather adventures. These premium boots are designed with a waterproof and insulated "
            "shell, keeping your feet warm and protected in icy conditions. The sleek black design "
            "with blue accents adds a touch of style to your outdoor gear.",
        }
    ]


@pytest.mark.asyncio
async def test_similar_handler_422(test_client):
    """test the similar_handler route with missing query parameters"""
    response = test_client.get("/similar")

    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "88"
    assert b'{"detail":[{"type":"missing","loc":["query","id"]' in response.content


@pytest.mark.asyncio
async def test_similar_handler_404(test_client):
    """test the similar_handler route with a non-existent item"""
    item_id = 10000000
    response = test_client.get(f"/similar?id={item_id}&n=1")

    assert response.status_code == 404
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "45"
    assert bytes(f'{{"detail":"Item with ID {item_id} not found."}}', "utf-8") in response.content


@pytest.mark.asyncio
async def test_search_handler(test_client):
    """test the search_handler route"""
    response = test_client.get(f"/search?query={test_data.name}&top=1")
    response_data = response.json()[0]

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "407"
    assert response_data["id"] == test_data.id
    assert response_data["name"] == test_data.name
    assert response_data["description"] == test_data.description
    assert response_data["price"] == test_data.price
    assert response_data["type"] == test_data.type
    assert response_data["brand"] == test_data.brand


@pytest.mark.asyncio
async def test_search_handler_422(test_client):
    """test the search_handler route with missing query parameters"""
    response = test_client.get("/search")

    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "91"
    assert b'{"detail":[{"type":"missing","loc":["query","query"]' in response.content


@pytest.mark.asyncio
async def test_simple_chat_flow(test_client):
    """test the simple chat flow route with hybrid retrieval mode"""
    response = test_client.post(
        "/chat",
        json={
            "context": {
                "overrides": {"top": 1, "use_advanced_flow": False, "retrieval_mode": "hybrid", "temperature": 0.3}
            },
            "messages": [{"content": "What is the capital of France?", "role": "user"}],
        },
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response_data["message"]["content"] == "The capital of France is Paris. [Benefit_Options-2.pdf]."
    assert response_data["message"]["role"] == "assistant"
    assert response_data["context"]["data_points"] == {
        "1": {
            "id": 1,
            "name": "Wanderer Black Hiking Boots",
            "description": "Daybird's Wanderer Hiking Boots in sleek black are perfect for all "
            "your outdoor adventures. These boots are made with a waterproof "
            "leather upper and a durable rubber sole for superior traction. With "
            "their cushioned insole and padded collar, these boots will keep you "
            "comfortable all day long.",
            "brand": "Daybird",
            "price": 109.99,
            "type": "Footwear",
        }
    }
    assert response_data["context"]["thoughts"] == [
        {
            "description": "What is the capital of France?",
            "props": {"text_search": True, "top": 1, "vector_search": True},
            "title": "Search query for database",
        },
        {
            "description": [
                {
                    "brand": "Daybird",
                    "description": "Daybird's Wanderer Hiking Boots in sleek black are perfect for all your "
                    "outdoor adventures. These boots are made with a waterproof leather upper and a durable "
                    "rubber sole for superior traction. With their cushioned insole and padded collar, "
                    "these boots will keep you comfortable all day long.",
                    "id": 1,
                    "name": "Wanderer Black Hiking Boots",
                    "price": 109.99,
                    "type": "Footwear",
                },
            ],
            "props": {},
            "title": "Search results",
        },
        {
            "description": [
                "{'role': 'system', 'content': \"Assistant helps customers with questions about "
                "products.\\nRespond as if you are a salesperson helping a customer in a store. "
                "Do NOT respond with tables.\\nAnswer ONLY with the product details listed in the "
                "products.\\nIf there isn't enough information below, say you don't know.\\nDo not "
                "generate answers that don't use the sources below.\\nEach product has an ID in brackets "
                "followed by colon and the product details.\\nAlways include the product ID for each product "
                "you use in the response.\\nUse square brackets to reference the source, "
                "for example [52].\\nDon't combine citations, list each product separately, for example [27][51].\"}",
                "{'role': 'user', 'content': \"What is the capital of France?\\n\\nSources:\\n[1]:Name:Wanderer "
                "Black Hiking Boots Description:Daybird's Wanderer Hiking Boots in sleek black are perfect for "
                "all your outdoor adventures. These boots are made with a waterproof leather upper and a durable "
                "rubber sole for superior traction. With their cushioned insole and padded collar, "
                "these boots will keep you comfortable all day long. Price:109.99 Brand:Daybird "
                'Type:Footwear\\n\\n"}',
            ],
            "props": {"model": "gpt-35-turbo"},
            "title": "Prompt to generate answer",
        },
    ]
    assert response_data["context"]["thoughts"] == [
        {
            "description": "What is the capital of France?",
            "props": {"text_search": True, "top": 1, "vector_search": True},
            "title": "Search query for database",
        },
        {
            "description": [
                {
                    "brand": "Daybird",
                    "description": "Daybird's Wanderer Hiking Boots in sleek black are perfect for all "
                    "your outdoor adventures. These boots are made with a waterproof leather upper and "
                    "a durable rubber sole for superior traction. With their cushioned insole and padded "
                    "collar, these boots will keep you comfortable all day long.",
                    "id": 1,
                    "name": "Wanderer Black Hiking Boots",
                    "price": 109.99,
                    "type": "Footwear",
                }
            ],
            "props": {},
            "title": "Search results",
        },
        {
            "description": [
                "{'role': 'system', 'content': \"Assistant helps customers with questions about "
                "products.\\nRespond as if you are a salesperson helping a customer in a store. "
                "Do NOT respond with tables.\\nAnswer ONLY with the product details listed in the "
                "products.\\nIf there isn't enough information below, say you don't know.\\nDo not "
                "generate answers that don't use the sources below.\\nEach product has an ID in brackets "
                "followed by colon and the product details.\\nAlways include the product ID for each product "
                "you use in the response.\\nUse square brackets to reference the source, "
                "for example [52].\\nDon't combine citations, list each product separately, for example [27][51].\"}",
                "{'role': 'user', 'content': \"What is the capital of France?\\n\\nSources:\\n[1]:Name:Wanderer "
                "Black Hiking Boots Description:Daybird's Wanderer Hiking Boots in sleek black are perfect for "
                "all your outdoor adventures. These boots are made with a waterproof leather upper and a durable "
                "rubber sole for superior traction. With their cushioned insole and padded collar, "
                "these boots will keep you comfortable all day long. Price:109.99 Brand:Daybird "
                'Type:Footwear\\n\\n"}',
            ],
            "props": {"model": "gpt-35-turbo"},
            "title": "Prompt to generate answer",
        },
    ]
    assert response_data["session_state"] is None


@pytest.mark.asyncio
async def test_advanced_chat_flow(test_client):
    """test the advanced chat flow route with hybrid retrieval mode"""
    response = test_client.post(
        "/chat",
        json={
            "context": {
                "overrides": {"top": 1, "use_advanced_flow": True, "retrieval_mode": "hybrid", "temperature": 0.3}
            },
            "messages": [{"content": "What is the capital of France?", "role": "user"}],
        },
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response_data["message"]["content"] == "The capital of France is Paris. [Benefit_Options-2.pdf]."
    assert response_data["message"]["role"] == "assistant"
    assert response_data["context"]["data_points"] == {
        "1": {
            "id": 1,
            "name": "Wanderer Black Hiking Boots",
            "description": "Daybird's Wanderer Hiking Boots in sleek black are perfect for all "
            "your outdoor adventures. These boots are made with a waterproof "
            "leather upper and a durable rubber sole for superior traction. With "
            "their cushioned insole and padded collar, these boots will keep you "
            "comfortable all day long.",
            "brand": "Daybird",
            "price": 109.99,
            "type": "Footwear",
        }
    }
    assert response_data["context"]["thoughts"] == [
        {
            "description": [
                "{'role': 'system', 'content': 'Below is a history of the "
                "conversation so far, and a new question asked by the user that "
                "needs to be answered by searching database rows.\\nYou have "
                "access to an Azure PostgreSQL database with an items table that "
                "has columns for title, description, brand, price, and "
                "type.\\nGenerate a search query based on the conversation and the "
                "new question.\\nIf the question is not in English, translate the "
                "question to English before generating the search query.\\nIf you "
                "cannot generate a search query, return the original user "
                "question.\\nDO NOT return anything besides the query.'}",
                "{'role': 'user', 'content': 'What is the capital of France?'}",
            ],
            "props": {
                "model": "gpt-35-turbo",
            },
            "title": "Prompt to generate search arguments",
        },
        {
            "description": "The capital of France is Paris. [Benefit_Options-2.pdf].",
            "props": {"filters": [], "text_search": True, "top": 1, "vector_search": True},
            "title": "Search using generated search arguments",
        },
        {
            "description": [
                {
                    "brand": "Daybird",
                    "description": "Daybird's Wanderer Hiking Boots in sleek black are perfect for all your "
                    "outdoor adventures. These boots are made with a waterproof leather upper and a durable "
                    "rubber sole for superior traction. With their cushioned insole and padded collar, "
                    "these boots will keep you comfortable all day long.",
                    "id": 1,
                    "name": "Wanderer Black Hiking Boots",
                    "price": 109.99,
                    "type": "Footwear",
                },
            ],
            "props": {},
            "title": "Search results",
        },
        {
            "description": [
                "{'role': 'system', 'content': \"Assistant helps customers with questions about "
                "products.\\nRespond as if you are a salesperson helping a customer in a store. "
                "Do NOT respond with tables.\\nAnswer ONLY with the product details listed in the "
                "products.\\nIf there isn't enough information below, say you don't know.\\nDo not "
                "generate answers that don't use the sources below.\\nEach product has an ID in brackets "
                "followed by colon and the product details.\\nAlways include the product ID for each product "
                "you use in the response.\\nUse square brackets to reference the source, "
                "for example [52].\\nDon't combine citations, list each product separately, for example [27][51].\"}",
                "{'role': 'user', 'content': \"What is the capital of France?\\n\\nSources:\\n[1]:Name:Wanderer "
                "Black Hiking Boots Description:Daybird's Wanderer Hiking Boots in sleek black are perfect for "
                "all your outdoor adventures. These boots are made with a waterproof leather upper and a durable "
                "rubber sole for superior traction. With their cushioned insole and padded collar, "
                "these boots will keep you comfortable all day long. Price:109.99 Brand:Daybird "
                'Type:Footwear\\n\\n"}',
            ],
            "props": {"model": "gpt-35-turbo"},
            "title": "Prompt to generate answer",
        },
    ]
    assert response_data["context"]["thoughts"] == [
        {
            "description": [
                "{'role': 'system', 'content': 'Below is a history of the "
                "conversation so far, and a new question asked by the user that "
                "needs to be answered by searching database rows.\\nYou have "
                "access to an Azure PostgreSQL database with an items table that "
                "has columns for title, description, brand, price, and "
                "type.\\nGenerate a search query based on the conversation and the "
                "new question.\\nIf the question is not in English, translate the "
                "question to English before generating the search query.\\nIf you "
                "cannot generate a search query, return the original user "
                "question.\\nDO NOT return anything besides the query.'}",
                "{'role': 'user', 'content': 'What is the capital of France?'}",
            ],
            "props": {
                "model": "gpt-35-turbo",
            },
            "title": "Prompt to generate search arguments",
        },
        {
            "description": "The capital of France is Paris. [Benefit_Options-2.pdf].",
            "props": {"filters": [], "text_search": True, "top": 1, "vector_search": True},
            "title": "Search using generated search arguments",
        },
        {
            "description": [
                {
                    "brand": "Daybird",
                    "description": "Daybird's Wanderer Hiking Boots in sleek black are perfect for all "
                    "your outdoor adventures. These boots are made with a waterproof leather upper and "
                    "a durable rubber sole for superior traction. With their cushioned insole and padded "
                    "collar, these boots will keep you comfortable all day long.",
                    "id": 1,
                    "name": "Wanderer Black Hiking Boots",
                    "price": 109.99,
                    "type": "Footwear",
                }
            ],
            "props": {},
            "title": "Search results",
        },
        {
            "description": [
                "{'role': 'system', 'content': \"Assistant helps customers with questions about "
                "products.\\nRespond as if you are a salesperson helping a customer in a store. "
                "Do NOT respond with tables.\\nAnswer ONLY with the product details listed in the "
                "products.\\nIf there isn't enough information below, say you don't know.\\nDo not "
                "generate answers that don't use the sources below.\\nEach product has an ID in brackets "
                "followed by colon and the product details.\\nAlways include the product ID for each product "
                "you use in the response.\\nUse square brackets to reference the source, "
                "for example [52].\\nDon't combine citations, list each product separately, for example [27][51].\"}",
                "{'role': 'user', 'content': \"What is the capital of France?\\n\\nSources:\\n[1]:Name:Wanderer "
                "Black Hiking Boots Description:Daybird's Wanderer Hiking Boots in sleek black are perfect for "
                "all your outdoor adventures. These boots are made with a waterproof leather upper and a durable "
                "rubber sole for superior traction. With their cushioned insole and padded collar, "
                "these boots will keep you comfortable all day long. Price:109.99 Brand:Daybird "
                'Type:Footwear\\n\\n"}',
            ],
            "props": {"model": "gpt-35-turbo"},
            "title": "Prompt to generate answer",
        },
    ]
    assert response_data["session_state"] is None


@pytest.mark.asyncio
async def test_chat_non_json_422(test_client):
    """test the chat route with a non-json request"""
    response = test_client.post("/chat")

    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["Content-Length"] == "82"
    assert b'{"detail":[{"type":"missing"' in response.content
