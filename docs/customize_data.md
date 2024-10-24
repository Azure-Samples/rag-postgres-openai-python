# RAG on PostgreSQL: Customizing the data

This guide shows you how to bring in a table with a different schema than the sample table.
For a full example of code changes needed, check out [this branch](https://github.com/Azure-Samples/rag-postgres-openai-python/compare/main...otherdata).

## Define the table schema

1. Update seed_data.json file with the new data
2. Update the SQLAlchemy models in postgres_models.py to reflect the new schema
3. Add the new table to the database:

    ```shell
    python src/backend/fastapi_app/setup_postgres_database.py
    ```

    These scripts will run on the local database by default. They will run on the production database as part of the `azd up` deployment process.

## Add embeddings to the seed data

If you don't yet have any embeddings in `seed_data.json`:

1. Update the references to models in update_embeddings.py
2. Generate new embeddings for the seed data:

    ```shell
    python src/backend/fastapi_app/update_embeddings.py  --in_seed_data
    ```

    That script will use whatever OpenAI host is defined in the `.env` file.
    You may want to run it twice for multiple models, once for Azure OpenAI embedding model and another for Ollama embedding model. Change `OPENAI_EMBED_HOST` between runs.

## Add the seed data to the database

Now that you have the new table schema and `seed_data.json` populated with embeddings, you can add the seed data to the database:

    ```shell
    python src/backend/fastapi_app/setup_postgres_seeddata.py
    ```

## Update the LLM prompts

3. Update the question answering prompt at `src/backend/fastapi_app/prompts/answer.txt` to reflect the new domain.
4. Update the function calling definition in `src/backend/fastapi_app/query_rewriter.py` to reflect the new schema and domain. Replace the `brand_filter` and `price_filter` with any filters that are relevant to your new schema.
5. Update the query rewriting prompt at `src/backend/fastapi_app/prompts/query.txt` to reflect the new domain and filters.
6. Update the query rewriting examples at `src/backend/fastapi_app/prompts/query_fewshots.json` to match the new domain and filters.

## Update the API

The FastAPI routes use type annotations to define the schema of the data that they accept and return, so you'll need to update the API to reflect the new schema.

1. Modify `ItemPublic` in `src/backend/fastapi_app/api_models.py` to reflect the new schema.
2. Modify `RAGContext` if your schema uses a string ID instead of integer ID.

## Update the frontend

1. Modify the Answer component in `src/frontend/src/components/Answer/Answer.tsx` to display the desired fields from the new schema.
2. Modify the examples in `/workspace/src/frontend/src/components/Example/ExampleList.tsx` to examples for the new domain.
