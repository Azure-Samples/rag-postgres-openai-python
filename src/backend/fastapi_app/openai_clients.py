import logging
import os
from typing import Union

import azure.identity
import openai

logger = logging.getLogger("ragapp")


async def create_openai_chat_client(
    azure_credential: Union[azure.identity.AzureDeveloperCliCredential, azure.identity.ManagedIdentityCredential, None],
) -> openai.AsyncOpenAI:
    openai_chat_client: openai.AsyncOpenAI
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_CHAT_HOST == "azure":
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        azure_deployment = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
        # Use default API version for Azure OpenAI
        api_version = "2024-10-21"
        if api_key := os.getenv("AZURE_OPENAI_KEY"):
            logger.info(
                "Setting up Azure OpenAI client for chat completions using API key, endpoint %s, deployment %s",
                azure_endpoint,
                azure_deployment,
            )
            openai_chat_client = openai.AsyncOpenAI(
                base_url=f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}?api-version={api_version}",
                api_key=api_key,
            )
        elif azure_credential:
            logger.info(
                "Setting up Azure OpenAI client for chat completions using Azure Identity, endpoint %s, deployment %s",
                azure_endpoint,
                azure_deployment,
            )
            token_provider = azure.identity.get_bearer_token_provider(
                azure_credential, "https://cognitiveservices.azure.com/.default"
            )
            # Get the initial token from the provider
            initial_token = token_provider()
            openai_chat_client = openai.AsyncOpenAI(
                base_url=f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}?api-version={api_version}",
                api_key=initial_token,
            )
        else:
            raise ValueError("Azure OpenAI client requires either an API key or Azure Identity credential.")
    elif OPENAI_CHAT_HOST == "ollama":
        logger.info("Setting up OpenAI client for chat completions using Ollama")
        openai_chat_client = openai.AsyncOpenAI(
            base_url=os.getenv("OLLAMA_ENDPOINT"),
            api_key="nokeyneeded",
        )
    elif OPENAI_CHAT_HOST == "github":
        logger.info("Setting up OpenAI client for chat completions using GitHub Models")
        github_model = os.getenv("GITHUB_MODEL", "openai/gpt-4o")
        logger.info(f"Using GitHub Models with model: {github_model}")
        openai_chat_client = openai.AsyncOpenAI(
            base_url="https://models.github.ai/inference",
            api_key=os.getenv("GITHUB_TOKEN"),
        )
    else:
        logger.info("Setting up OpenAI client for chat completions using OpenAI.com API key")
        openai_chat_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAICOM_KEY"))

    return openai_chat_client


async def create_openai_embed_client(
    azure_credential: Union[azure.identity.AzureDeveloperCliCredential, azure.identity.ManagedIdentityCredential, None],
) -> openai.AsyncOpenAI:
    openai_embed_client: openai.AsyncOpenAI
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    if OPENAI_EMBED_HOST == "azure":
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        azure_deployment = os.environ["AZURE_OPENAI_EMBED_DEPLOYMENT"]
        # Use default API version for Azure OpenAI
        api_version = "2024-03-01-preview"
        if api_key := os.getenv("AZURE_OPENAI_KEY"):
            logger.info(
                "Setting up Azure OpenAI client for embeddings using API key, endpoint %s, deployment %s",
                azure_endpoint,
                azure_deployment,
            )
            openai_embed_client = openai.AsyncOpenAI(
                base_url=f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}?api-version={api_version}",
                api_key=api_key,
            )
        elif azure_credential:
            logger.info(
                "Setting up Azure OpenAI client for embeddings using Azure Identity, endpoint %s, deployment %s",
                azure_endpoint,
                azure_deployment,
            )
            token_provider = azure.identity.get_bearer_token_provider(
                azure_credential, "https://cognitiveservices.azure.com/.default"
            )
            # Get the initial token from the provider
            initial_token = token_provider()
            openai_embed_client = openai.AsyncOpenAI(
                base_url=f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}?api-version={api_version}",
                api_key=initial_token,
            )
        else:
            raise ValueError("Azure OpenAI client requires either an API key or Azure Identity credential.")
    elif OPENAI_EMBED_HOST == "ollama":
        logger.info("Setting up OpenAI client for embeddings using Ollama")
        openai_embed_client = openai.AsyncOpenAI(
            base_url=os.getenv("OLLAMA_ENDPOINT"),
            api_key="nokeyneeded",
        )
    elif OPENAI_EMBED_HOST == "github":
        logger.info("Setting up OpenAI client for embeddings using GitHub Models")
        github_embed_model = os.getenv("GITHUB_EMBED_MODEL", "openai/text-embedding-3-small")
        logger.info(f"Using GitHub Models with embedding model: {github_embed_model}")
        openai_embed_client = openai.AsyncOpenAI(
            base_url="https://models.github.ai/inference",
            api_key=os.getenv("GITHUB_TOKEN"),
        )
    else:
        logger.info("Setting up OpenAI client for embeddings using OpenAI.com API key")
        openai_embed_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAICOM_KEY"))
    return openai_embed_client
