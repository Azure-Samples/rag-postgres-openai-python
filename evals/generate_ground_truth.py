import logging
import os
from collections.abc import Generator
from pathlib import Path

from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv
from evaltools.gen.generate import generate_test_qa_data
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fastapi_app.postgres_models import Item

logger = logging.getLogger("ragapp")


def source_retriever() -> Generator[dict, None, None]:
    # Connect to the database
    DBHOST = os.environ["POSTGRES_HOST"]
    DBUSER = os.environ["POSTGRES_USERNAME"]
    DBPASS = os.environ["POSTGRES_PASSWORD"]
    DBNAME = os.environ["POSTGRES_DATABASE"]
    DATABASE_URI = f"postgresql://{DBUSER}:{DBPASS}@{DBHOST}/{DBNAME}"
    engine = create_engine(DATABASE_URI, echo=False)
    with Session(engine) as session:
        # Fetch all products for a particular type
        item_types = session.scalars(select(Item.type).distinct())
        for item_type in item_types:
            records = list(session.scalars(select(Item).filter(Item.type == item_type).order_by(Item.id)))
            # logger.info(f"Processing database records for type: {item_type}")
            # yield {
            #    "citations": " ".join([f"[{record.id}] - {record.name}" for record in records]),
            #    "content": "\n\n".join([record.to_str_for_rag() for record in records]),
            # }
        # Fetch each item individually
        records = list(session.scalars(select(Item).order_by(Item.id)))
        for record in records:
            logger.info(f"Processing database record: {record.name}")
            yield {"id": record.id, "content": record.to_str_for_rag()}


def source_to_text(source) -> str:
    return source["content"]


def answer_formatter(answer, source) -> str:
    return f"{answer} [{source['id']}]"


def get_openai_config_dict() -> dict:
    """Return a dictionary with OpenAI configuration based on environment variables."""
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")
    if OPENAI_CHAT_HOST == "azure":
        if api_key := os.getenv("AZURE_OPENAI_KEY"):
            logger.info("Using Azure OpenAI Service with API Key from AZURE_OPENAI_KEY")
            api_key = os.environ["AZURE_OPENAI_KEY"]
        else:
            logger.info("Using Azure OpenAI Service with Azure Developer CLI Credential")
            azure_credential = AzureDeveloperCliCredential(process_timeout=60)
            api_key = azure_credential.get_token("https://cognitiveservices.azure.com/.default").token
        openai_config = {
            "api_type": "azure",
            "api_base": os.environ["AZURE_OPENAI_ENDPOINT"],
            "api_key": api_key,
            "api_version": os.environ["AZURE_OPENAI_VERSION"],
            "deployment": os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
            "model": os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        }
    elif OPENAI_CHAT_HOST == "ollama":
        raise NotImplementedError("Ollama OpenAI Service is not supported. Switch to Azure or OpenAI.com")
    else:
        logger.info("Using OpenAI Service with API Key from OPENAICOM_KEY")
        openai_config = {
            "api_type": "openai",
            "api_key": os.environ["OPENAICOM_KEY"],
            "model": os.environ["OPENAICOM_CHAT_MODEL"],
            "deployment": "none-needed-for-openaicom",
        }
    return openai_config


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(".env", override=True)

    generate_test_qa_data(
        openai_config=get_openai_config_dict(),
        num_questions_total=202,
        num_questions_per_source=2,
        output_file=Path(__file__).parent / "ground_truth.jsonl",
        source_retriever=source_retriever,
        source_to_text=source_to_text,
        answer_formatter=answer_formatter,
    )
