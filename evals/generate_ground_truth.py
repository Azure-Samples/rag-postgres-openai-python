import argparse
import json
import logging
import os
from collections.abc import Generator
from pathlib import Path

from azure.identity import AzureDeveloperCliCredential, get_bearer_token_provider
from dotenv_azd import load_azd_env
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletionToolParam
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from rich.logging import RichHandler

from fastapi_app.postgres_models import Item

logger = logging.getLogger("ragapp")



def qa_pairs_tool(num_questions: int = 1) -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {
            "name": "qa_pairs",
            "description": "Send in question and answer pairs for a customer-facing chat app",
            "parameters": {
                "type": "object",
                "properties": {
                    "qa_list": {
                        "type": "array",
                        "description": f"List of {num_questions} question and answer pairs",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string", "description": "The question text"},
                                "answer": {"type": "string", "description": "The answer text"},
                            },
                            "required": ["question", "answer"],
                        },
                        "minItems": num_questions,
                        "maxItems": num_questions,
                    }
                },
                "required": ["qa_list"],
            },
        },
    }


def source_retriever() -> Generator[str, None, None]:
    # Connect to the local database
    DBHOST = os.environ["POSTGRES_HOST"]
    DBUSER = os.environ["POSTGRES_USERNAME"]
    DBPASS = os.environ["POSTGRES_PASSWORD"]
    DBNAME = os.environ["POSTGRES_DATABASE"]
    DATABASE_URI = f"postgresql://{DBUSER}:{DBPASS}@{DBHOST}/{DBNAME}"
    engine = create_engine(DATABASE_URI, echo=False)
    with Session(engine) as session:
        while True:
            # Fetch all the rows from the database
            random_rows = list(session.scalars(select(Item).order_by(func.random())))
            logger.info("Fetched %d random rows", len(random_rows))
            yield "\n\n".join([f"## Row ID: [{row.id}]\n" + row.to_str_for_rag() for row in random_rows])


def source_to_text(source) -> str:
    return source["content"]


def answer_formatter(answer, source) -> str:
    return f"{answer} [{source['id']}]"


def get_openai_client() -> tuple[AzureOpenAI | OpenAI, str]:
    """Return an OpenAI client based on the environment variables"""
    openai_client: AzureOpenAI | OpenAI
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_CHAT_HOST == "azure":
        if api_key := os.getenv("AZURE_OPENAI_KEY"):
            logger.info("Using Azure OpenAI Service with API Key from AZURE_OPENAI_KEY")
            openai_client = AzureOpenAI(
                api_version=os.environ["AZURE_OPENAI_VERSION"],
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=api_key,
            )
        else:
            logger.info("Using Azure OpenAI Service with Azure Developer CLI Credential")
            azure_credential = AzureDeveloperCliCredential(process_timeout=60, tenant_id=os.environ["AZURE_TENANT_ID"])
            token_provider = get_bearer_token_provider(azure_credential, "https://cognitiveservices.azure.com/.default")
            openai_client = AzureOpenAI(
                api_version=os.environ["AZURE_OPENAI_VERSION"],
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                azure_ad_token_provider=token_provider,
            )
        model = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
    elif OPENAI_CHAT_HOST == "ollama":
        raise NotImplementedError("Ollama OpenAI Service is not supported. Switch to Azure or OpenAI.com")
    else:
        logger.info("Using OpenAI Service with API Key from OPENAICOM_KEY")
        openai_client = OpenAI(api_key=os.environ["OPENAICOM_KEY"])
        model = os.environ["OPENAICOM_CHAT_MODEL"]
    return openai_client, model


def generate_ground_truth_data(num_questions_total: int, num_questions_per_source):
    logger.info("Generating %d questions total", num_questions_total)
    openai_client, model = get_openai_client()
    current_dir = Path(__file__).parent

    # Load the template from the file system
    jinja_file_loader = FileSystemLoader(current_dir)
    jinja_env = Environment(loader=jinja_file_loader)
    prompt_template = jinja_env.get_template('generate_prompt.jinja2')

    output_file = Path(__file__).parent / "ground_truth.jsonl"

    qa: list[dict] = []
    while len(qa) < num_questions_total:
        sources = next(source_retriever())
        previous_questions = [qa_pair["question"] for qa_pair in qa]
        result = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt_template.render(num_questions=num_questions_per_source, previous_questions=previous_questions)},
                {"role": "user", "content": json.dumps(sources)},
            ],
            tools=[qa_pairs_tool(num_questions=num_questions_per_source)],
        )
        if not result.choices[0].message.tool_calls:
            logger.warning("No tool calls found in response, skipping")
            continue
        qa_pairs = json.loads(result.choices[0].message.tool_calls[0].function.arguments)["qa_list"]
        qa_pairs = [{"question": qa_pair["question"], "truth": qa_pair["answer"]} for qa_pair in qa_pairs]
        logger.info("Received %d suggested questions", len(qa_pairs))
        qa.extend(qa_pairs)

    logger.info("Writing %d questions to %s", num_questions_total, output_file)
    directory = Path(output_file).parent
    if not directory.exists():
        directory.mkdir(parents=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in qa[0:num_questions_total]:
            f.write(json.dumps(item) + "\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
    )
    logger.setLevel(logging.INFO)
    load_dotenv(".env", override=True)

    parser = argparse.ArgumentParser(description="Run evaluation with OpenAI configuration.")
    parser.add_argument("--numquestions", type=int, help="Specify the number of questions.", default=50)
    parser.add_argument("--persource", type=int, help="Specify the number of questions per retrieved sources.", default=5)

    args = parser.parse_args()

    generate_ground_truth_data(num_questions_total=args.numquestions, num_questions_per_source=args.persource)
