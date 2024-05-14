import logging
import os

import azure.identity.aio
import openai

logger = logging.getLogger("ragapp")


async def create_openai_chat_client(azure_credential):
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_CHAT_HOST == "azure":
        logger.info("Authenticating to OpenAI using Azure Identity...")

        token_provider = azure.identity.aio.get_bearer_token_provider(
            azure_credential, "https://cognitiveservices.azure.com/.default"
        )
        openai_chat_client = openai.AsyncAzureOpenAI(
            api_version=os.getenv("AZURE_OPENAI_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_ad_token_provider=token_provider,
            azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        )
        openai_chat_model = os.getenv("AZURE_OPENAI_CHAT_MODEL")
    elif OPENAI_CHAT_HOST == "ollama":
        logger.info("Authenticating to OpenAI using Ollama...")
        openai_chat_client = openai.AsyncOpenAI(
            base_url=os.getenv("OLLAMA_ENDPOINT"),
            api_key="nokeyneeded",
        )
        openai_chat_model = os.getenv("OLLAMA_CHAT_MODEL")
    else:
        logger.info("Authenticating to OpenAI using OpenAI.com API key...")
        openai_chat_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAICOM_KEY"))
        openai_chat_model = os.getenv("OPENAICOM_CHAT_MODEL")

    return openai_chat_client, openai_chat_model


async def create_openai_embed_client(azure_credential):
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    if OPENAI_EMBED_HOST == "azure":
        token_provider = azure.identity.aio.get_bearer_token_provider(
            azure_credential, "https://cognitiveservices.azure.com/.default"
        )
        openai_embed_client = openai.AsyncAzureOpenAI(
            api_version=os.getenv("AZURE_OPENAI_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_ad_token_provider=token_provider,
            azure_deployment=os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT"),
        )
        openai_embed_model = os.getenv("AZURE_OPENAI_EMBED_MODEL")
        openai_embed_dimensions = os.getenv("AZURE_OPENAI_EMBED_DIMENSIONS")
    else:
        openai_embed_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAICOM_KEY"))
        openai_embed_model = os.getenv("OPENAICOM_EMBED_MODEL")
        openai_embed_dimensions = os.getenv("OPENAICOM_EMBED_DIMENSIONS")
    return openai_embed_client, openai_embed_model, openai_embed_dimensions
