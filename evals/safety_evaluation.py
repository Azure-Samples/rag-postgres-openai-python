import argparse
import asyncio
import logging
import os
import pathlib
import sys

import requests
from azure.ai.evaluation import AzureAIProject
from azure.ai.evaluation.red_team import AttackStrategy, RedTeam, RiskCategory
from azure.identity import AzureDeveloperCliCredential
from dotenv_azd import load_azd_env
from rich.logging import RichHandler

logger = logging.getLogger("ragapp")

# Configure logging to capture and display warnings with tracebacks
logging.captureWarnings(True)  # Capture warnings as log messages

root_dir = pathlib.Path(__file__).parent


def get_azure_credential():
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    if AZURE_TENANT_ID:
        logger.info("Setting up Azure credential using AzureDeveloperCliCredential with tenant_id %s", AZURE_TENANT_ID)
        azure_credential = AzureDeveloperCliCredential(tenant_id=AZURE_TENANT_ID, process_timeout=60)
    else:
        logger.info("Setting up Azure credential using AzureDeveloperCliCredential for home tenant")
        azure_credential = AzureDeveloperCliCredential(process_timeout=60)
    return azure_credential


async def callback(
    messages: list,
    target_url: str = "http://127.0.0.1:8000/chat",
):
    query = messages[-1].content
    headers = {"Content-Type": "application/json"}
    body = {
        "messages": [{"content": query, "role": "user"}],
        "stream": False,
        "context": {"overrides": {"use_advanced_flow": True, "top": 3, "retrieval_mode": "hybrid", "temperature": 0.3}},
    }
    url = target_url
    r = requests.post(url, headers=headers, json=body)
    response = r.json()
    if "error" in response:
        message = {"content": response["error"], "role": "assistant"}
    else:
        message = response["message"]
    return {"messages": messages + [message]}


async def run_simulator(target_url: str, max_simulations: int):
    credential = get_azure_credential()
    azure_ai_project: AzureAIProject = {
        "subscription_id": os.getenv("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.getenv("AZURE_RESOURCE_GROUP"),
        "project_name": "pf-testprojforaisaety",
    }
    model_red_team = RedTeam(
        azure_ai_project=azure_ai_project,
        credential=credential,
        risk_categories=[
            RiskCategory.Violence,
            # RiskCategory.HateUnfairness,
            # RiskCategory.Sexual,
            # RiskCategory.SelfHarm,
        ],
        num_objectives=1,
    )
    await model_red_team.scan(
        target=lambda messages, stream=False, session_state=None, context=None: callback(messages, target_url),
        scan_name="Advanced-Callback-Scan",
        attack_strategies=[
            AttackStrategy.EASY,  # Group of easy complexity attacks
            # AttackStrategy.MODERATE,  # Group of moderate complexity attacks
            # AttackStrategy.CharacterSpace,  # Add character spaces
            # AttackStrategy.ROT13,  # Use ROT13 encoding
            # AttackStrategy.UnicodeConfusable,  # Use confusable Unicode characters
            # AttackStrategy.CharSwap,  # Swap characters in prompts
            # AttackStrategy.Morse,  # Encode prompts in Morse code
            # AttackStrategy.Leetspeak,  # Use Leetspeak
            # AttackStrategy.Url,  # Use URLs in prompts
            # AttackStrategy.Binary,  # Encode prompts in binary
        ],
        output_path="Advanced-Callback-Scan.json",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run safety evaluation simulator.")
    parser.add_argument(
        "--target_url", type=str, default="http://127.0.0.1:8000/chat", help="Target URL for the callback."
    )
    parser.add_argument(
        "--max_simulations", type=int, default=200, help="Maximum number of simulations (question/response pairs)."
    )
    args = parser.parse_args()

    # Configure logging to show tracebacks for warnings and above
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=False, show_path=True)],
    )

    # Set urllib3 and azure libraries to WARNING level to see connection issues
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.DEBUG)
    logging.getLogger("RedTeamLogger").setLevel(logging.DEBUG)

    # Set our application logger to INFO level
    logger.setLevel(logging.INFO)

    load_azd_env()

    try:
        asyncio.run(run_simulator(args.target_url, args.max_simulations))
    except Exception:
        logging.exception("Unhandled exception in safety evaluation")
        sys.exit(1)
