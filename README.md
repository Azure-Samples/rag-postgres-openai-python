# RAG on PostgreSQL

1. Copy `.env.sample` into a `.env` file.

2. Run these commands to install the web app as a local package (named `rag_app`), set up the local database, and seed it with test data:

    ```bash
    python -m pip install -e src/backend
    python ./src/backend/rag_app/setup_postgres_database.py
    python ./src/backend/rag_app/setup_postgres_seeddata.py
    ```

3. Run the FastAPI backend (with hot reloading). This should be run from the root of the project:

    ```shell
    python -m uvicorn rag_app:create_app --factory --reload
    ```
