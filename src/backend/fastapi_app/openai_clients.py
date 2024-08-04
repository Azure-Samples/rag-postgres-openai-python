import logging
import os

import azure.identity
import openai

logger = logging.getLogger("ragapp")


async def create_openai_chat_client(
    azure_credential: azure.identity.DefaultAzureCredential | azure.identity.ManagedIdentityCredential,
) -> openai.AsyncAzureOpenAI | openai.AsyncOpenAI:
    openai_chat_client: openai.AsyncAzureOpenAI | openai.AsyncOpenAI
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_CHAT_HOST == "azure":
        api_version = os.environ["AZURE_OPENAI_VERSION"]
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        azure_deployment = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
        if api_key := os.getenv("AZURE_OPENAI_KEY"):
            logger.info("Authenticating to Azure OpenAI using API key...")
            openai_chat_client = openai.AsyncAzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_key=api_key,
            )
        else:
            logger.info("Authenticating to Azure OpenAI Chat using Azure Identity...")
            token_provider = azure.identity.get_bearer_token_provider(
                azure_credential, "https://cognitiveservices.azure.com/.default"
            )
            openai_chat_client = openai.AsyncAzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                azure_ad_token_provider=token_provider,
            )
    elif OPENAI_CHAT_HOST == "ollama":
        logger.info("Authenticating to OpenAI using Ollama...")
        openai_chat_client = openai.AsyncOpenAI(
            base_url=os.getenv("OLLAMA_ENDPOINT"),
            api_key="nokeyneeded",
        )
    else:
        logger.info("Authenticating to OpenAI using OpenAI.com API key...")
        openai_chat_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAICOM_KEY"))

    return openai_chat_client


async def create_openai_embed_client(
    azure_credential: azure.identity.DefaultAzureCredential | azure.identity.ManagedIdentityCredential,
) -> openai.AsyncAzureOpenAI | openai.AsyncOpenAI:
    openai_embed_client: openai.AsyncAzureOpenAI | openai.AsyncOpenAI
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    if OPENAI_EMBED_HOST == "azure":
        api_version = os.environ["AZURE_OPENAI_VERSION"]
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        azure_deployment = os.environ["AZURE_OPENAI_EMBED_DEPLOYMENT"]
        if api_key := os.getenv("AZURE_OPENAI_KEY"):
            logger.info("Authenticating to Azure OpenAI using API key...")
            openai_embed_client = openai.AsyncAzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_key=api_key,
            )
        else:
            logger.info("Authenticating to Azure OpenAI Embedding using Azure Identity...")
            token_provider = azure.identity.get_bearer_token_provider(
                azure_credential, "https://cognitiveservices.azure.com/.default"
            )
            openai_embed_client = openai.AsyncAzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                azure_ad_token_provider=token_provider,
            )
    elif OPENAI_EMBED_HOST == "ollama":
        logger.info("Authenticating to OpenAI using Ollama...")
        openai_embed_client = openai.AsyncOpenAI(
            base_url=os.getenv("OLLAMA_ENDPOINT"),
            api_key="nokeyneeded",
        )
    else:
        logger.info("Authenticating to OpenAI using OpenAI.com API key...")
        openai_embed_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAICOM_KEY"))
    return openai_embed_client
