import argparse
import logging
import os
import re
from pathlib import Path
from typing import Any

import azure.identity
from dotenv import load_dotenv
from evaltools.eval.evaluate import run_evaluate_from_config
from evaltools.eval.evaluate_metrics import register_metric
from evaltools.eval.evaluate_metrics.base_metric import BaseMetric
from rich.logging import RichHandler

logger = logging.getLogger("ragapp")


class CitationsMatchedMetric(BaseMetric):
    METRIC_NAME = "citations_matched"

    @classmethod
    def evaluator_fn(cls, **kwargs):
        def citations_overlap(*, response, ground_truth, **kwargs):
            if response is None:
                logger.warning("Received response of None, can't compute citation_match metric. Setting to -1.")
                return {cls.METRIC_NAME: -1}
            truth_citations = set(re.findall(r"\[(\d+)\]", ground_truth))
            response_citations = set(re.findall(r"\[(\d+)\]", response))
            # Count the percentage of citations that are present in the response
            num_citations = len(truth_citations)
            num_matched_citations = len(truth_citations.intersection(response_citations))
            return {cls.METRIC_NAME: num_matched_citations / num_citations}

        return citations_overlap

    @classmethod
    def get_aggregate_stats(cls, df):
        df = df[df[cls.METRIC_NAME] != -1]
        return {"mean": round(df[cls.METRIC_NAME].mean(), 2)}


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
    elif os.environ.get("OPENAI_CHAT_HOST") == "ollama":
        raise NotImplementedError("Ollama is not supported. Switch to Azure or OpenAI.com")
    elif os.environ.get("OPENAI_CHAT_HOST") == "github":
        raise NotImplementedError("GitHub Models is not supported. Switch to Azure or OpenAI.com")
    else:
        logger.info("Using OpenAI Service with API Key from OPENAICOM_KEY")
        openai_config = {"api_key": os.environ["OPENAICOM_KEY"], "model": "gpt-4"}
    return openai_config


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
    )
    load_dotenv(".env", override=True)

    parser = argparse.ArgumentParser(description="Run evaluation with OpenAI configuration.")
    parser.add_argument("--targeturl", type=str, help="Specify the target URL.")
    parser.add_argument("--resultsdir", type=Path, help="Specify the results directory.")
    parser.add_argument("--numquestions", type=int, help="Specify the number of questions.")

    args = parser.parse_args()

    openai_config = get_openai_config()

    register_metric(CitationsMatchedMetric)
    run_evaluate_from_config(
        working_dir=Path(__file__).parent,
        config_path="eval_config.json",
        num_questions=args.numquestions,
        target_url=args.targeturl,
        results_dir=args.resultsdir,
        openai_config=openai_config,
    )
