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
                "description": "Search PostgreSQL database for relevant conference sessions based on user query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {
                            "type": "string",
                            "description": "Query string to use for full text search, e.g. 'python AI'",
                        },
                        "mode_filter": {
                            "type": "object",
                            "description": "Filter search results based on mode of the session",
                            "properties": {
                                "comparison_operator": {
                                    "type": "string",
                                    "description": "Operator to compare the column value, either '=' or '!='",
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Possible values are 'In-person', 'Livestream', or 'Recorded'.",
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
                if "mode_filter" in arg and arg["mode_filter"]:
                    mode_filter = arg["mode_filter"]
                    filters.append(
                        {
                            "column": "mode",
                            "comparison_operator": mode_filter["comparison_operator"],
                            "value": mode_filter["value"],
                        }
                    )
    elif query_text := response_message.content:
        search_query = query_text.strip()
    return search_query, filters
