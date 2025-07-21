import argparse
import asyncio
import datetime
import logging
import os
import pathlib
import sys
from typing import Optional

import requests
from azure.ai.evaluation.red_team import AttackStrategy, RedTeam, RiskCategory
from azure.identity import AzureDeveloperCliCredential
from dotenv_azd import load_azd_env

root_dir = pathlib.Path(__file__).parent


def get_azure_credential():
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    if AZURE_TENANT_ID:
        print("Setting up Azure credential using AzureDeveloperCliCredential with tenant_id %s", AZURE_TENANT_ID)
        azure_credential = AzureDeveloperCliCredential(tenant_id=AZURE_TENANT_ID, process_timeout=60)
    else:
        print("Setting up Azure credential using AzureDeveloperCliCredential for home tenant")
        azure_credential = AzureDeveloperCliCredential(process_timeout=60)
    return azure_credential


def callback(
    question: str,
    target_url: str = "http://127.0.0.1:8000/chat",
):
    headers = {"Content-Type": "application/json"}
    body = {
        "messages": [{"content": question, "role": "user"}],
        "stream": False,
        "context": {
            "overrides": {"use_advanced_flow": False, "top": 3, "retrieval_mode": "hybrid", "temperature": 0.3}
        },
    }
    url = target_url
    r = requests.post(url, headers=headers, json=body)
    response = r.json()
    if "error" in response:
        return f"Error received: {response['error']}"
    else:
        return response["message"]["content"]


async def run_redteaming(target_url: str, questions_per_category: int = 1, scan_name: Optional[str] = None):
    AZURE_AI_FOUNDRY = os.getenv("AZURE_AI_FOUNDRY")
    AZURE_AI_PROJECT = os.getenv("AZURE_AI_PROJECT")
    model_red_team = RedTeam(
        azure_ai_project=f"https://{AZURE_AI_FOUNDRY}.services.ai.azure.com/api/projects/{AZURE_AI_PROJECT}",
        credential=get_azure_credential(),
        risk_categories=[
            RiskCategory.Violence,
            RiskCategory.HateUnfairness,
            RiskCategory.Sexual,
            RiskCategory.SelfHarm,
        ],
        num_objectives=questions_per_category,
    )

    if scan_name is None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        scan_name = f"Safety evaluation {timestamp}"

    await model_red_team.scan(
        scan_name=scan_name,
        output_path=f"{root_dir}/redteams/{scan_name}.json",
        attack_strategies=[
            AttackStrategy.Baseline,
            # Easy Complexity:
            AttackStrategy.Morse,
            AttackStrategy.UnicodeConfusable,
            AttackStrategy.Url,
            # Moderate Complexity:
            AttackStrategy.Tense,
            # Difficult Complexity:
            AttackStrategy.Compose([AttackStrategy.Tense, AttackStrategy.Url]),
        ],
        target=lambda query: callback(query, target_url),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run safety evaluation simulator.")
    parser.add_argument(
        "--target_url", type=str, default="http://127.0.0.1:8000/chat", help="Target URL for the callback."
    )
    parser.add_argument(
        "--questions_per_category",
        type=int,
        default=5,
        help="Number of questions per risk category to ask during the scan.",
    )
    parser.add_argument("--scan_name", type=str, default=None, help="Name of the safety evaluation (optional).")
    args = parser.parse_args()

    load_azd_env()
    try:
        asyncio.run(run_redteaming(args.target_url, args.questions_per_category, args.scan_name))
    except Exception:
        logging.exception("Unhandled exception in safety evaluation")
        sys.exit(1)
