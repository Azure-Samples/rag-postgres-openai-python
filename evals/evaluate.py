import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from evaltools.eval.evaluate import run_evaluate_from_config
from promptflow.core import AzureOpenAIModelConfiguration, ModelConfiguration, OpenAIModelConfiguration

logger = logging.getLogger("ragapp")


def get_openai_config() -> ModelConfiguration:
    if os.environ.get("OPENAI_CHAT_HOST") == "azure":
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        azure_deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
        api_version = "2023-07-01-preview"
        if os.environ.get("AZURE_OPENAI_KEY"):
            logger.info("Using Azure OpenAI Service with API Key from AZURE_OPENAI_KEY")
            openai_config = AzureOpenAIModelConfiguration(
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
                api_key=os.environ["AZURE_OPENAI_KEY"],
            )
        else:
            logger.info("Using Azure OpenAI Service with Azure Developer CLI Credential")
            openai_config = AzureOpenAIModelConfiguration(
                azure_endpoint=azure_endpoint, azure_deployment=azure_deployment, api_version=api_version
            )
            # PromptFlow will call DefaultAzureCredential behind the scenes
        openai_config.model = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
    else:
        logger.info("Using OpenAI Service with API Key from OPENAICOM_KEY")
        openai_config = OpenAIModelConfiguration(
            model=os.environ["OPENAICOM_CHAT_MODEL"], api_key=os.environ.get("OPENAICOM_KEY")
        )
    return openai_config


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(".env", override=True)

    openai_config = get_openai_config()
    run_evaluate_from_config(
        working_dir=Path(__file__).parent, config_path="eval_config.json", openai_config=openai_config, num_questions=20
    )
