import logging
import os
from pathlib import Path
from typing import Any

import azure.identity
from dotenv import load_dotenv
from evaltools.eval.evaluate import run_evaluate_from_config
from rich.logging import RichHandler

logger = logging.getLogger("ragapp")


def get_openai_config() -> dict:
    openai_config: dict[str, Any]
    if os.environ.get("OPENAI_CHAT_HOST") == "azure":
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        azure_deployment = os.environ["AZURE_OPENAI_EVAL_DEPLOYMENT"]
        if os.environ.get("AZURE_OPENAI_KEY"):
            logger.info("Using Azure OpenAI Service with API Key from AZURE_OPENAI_KEY")
            openai_config = {
                "azure_endpoint": azure_endpoint,
                "azure_deployment": azure_deployment,
                "api_key": os.environ["AZURE_OPENAI_KEY"],
            }
        else:
            if tenant_id := os.getenv("AZURE_TENANT_ID"):
                logger.info("Authenticating to Azure using Azure Developer CLI Credential for tenant %s", tenant_id)
                azure_credential = azure.identity.AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
            else:
                logger.info("Authenticating to Azure using Azure Developer CLI Credential")
                azure_credential = azure.identity.AzureDeveloperCliCredential(process_timeout=60)
            openai_config = {
                "azure_endpoint": azure_endpoint,
                "azure_deployment": azure_deployment,
                "credential": azure_credential,
            }
            # azure-ai-evaluate will call DefaultAzureCredential behind the scenes,
            # so we must be logged in to Azure CLI with the correct tenant
        openai_config["model"] = os.environ["AZURE_OPENAI_EVAL_MODEL"]
    else:
        logger.info("Using OpenAI Service with API Key from OPENAICOM_KEY")
        openai_config = {"api_key": os.environ["OPENAICOM_KEY"], "model": "gpt-4"}
    return openai_config


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
    )
    load_dotenv(".env", override=True)

    openai_config = get_openai_config()
    # TODO: specify the localhost URL using argument
    # TODO: specify the experiment name (based on PR number)
    # TODO: Specify the num questions using argument

    run_evaluate_from_config(
        working_dir=Path(__file__).parent, config_path="eval_config.json", openai_config=openai_config, num_questions=2
    )
