import json

from openai.types.chat import (
    ChatCompletion,
    ChatCompletionToolParam,
)


def build_search_function() -> list[ChatCompletionToolParam]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_database",
                "description": "Search PostgreSQL database for relevant restaurants based on user query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {
                            "type": "string",
                            "description": "Query string to use for full text search, e.g. 'red shoes'",
                        },
                        "price_level_filter": {
                            "type": "object",
                            "description": "Filter search results to a certain price level (from 1 $ to 4 $$$$, with 4 being most costly)",  # noqa: E501
                            "properties": {
                                "comparison_operator": {
                                    "type": "string",
                                    "description": "Operator to compare the column value, either '>', '<', '>=', '<=', '='",  # noqa: E501
                                },
                                "value": {
                                    "type": "number",
                                    "description": "Value to compare against, either 1, 2, 3, 4",
                                },
                            },
                        },
                        "rating_filter": {
                            "type": "object",
                            "description": "Filter search results based on ratings of restaurant (from 1 to 5 stars, with 5 the best)",  # noqa: E501
                            "properties": {
                                "comparison_operator": {
                                    "type": "string",
                                    "description": "Operator to compare the column value, either '>', '<', '>=', '<=', '='",  # noqa: E501
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Value to compare against, either 0 1 2 3 4 5",
                                },
                            },
                        },
                    },
                    "required": ["search_query"],
                },
            },
        }
    ]


def extract_search_arguments(original_user_query: str, chat_completion: ChatCompletion):
    response_message = chat_completion.choices[0].message
    search_query = None
    filters = []
    if response_message.tool_calls:
        for tool in response_message.tool_calls:
            if tool.type != "function":
                continue
            function = tool.function
            if function.name == "search_database":
                arg = json.loads(function.arguments)
                # Even though its required, search_query is not always specified
                search_query = arg.get("search_query", original_user_query)
                if (
                    "price_level_filter" in arg
                    and arg["price_level_filter"]
                    and isinstance(arg["price_level_filter"], dict)
                ):
                    price_level_filter = arg["price_level_filter"]
                    filters.append(
                        {
                            "column": "price_level",
                            "comparison_operator": price_level_filter["comparison_operator"],
                            "value": price_level_filter["value"],
                        }
                    )
                if "rating_filter" in arg and arg["rating_filter"] and isinstance(arg["rating_filter"], dict):
                    rating_filter = arg["rating_filter"]
                    filters.append(
                        {
                            "column": "rating",
                            "comparison_operator": rating_filter["comparison_operator"],
                            "value": rating_filter["value"],
                        }
                    )
    elif query_text := response_message.content:
        search_query = query_text.strip()
    return search_query, filters
