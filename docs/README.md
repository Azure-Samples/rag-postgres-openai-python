---
name: RAG on PostgreSQL
description: Deploy an app to chat with your PostgreSQL database using Azure OpenAI, Python, and the RAG technique.
languages:
- bicep
- azdeveloper
- python
- typescript
products:
- azure-database-postgresql
- azure
- azure-openai
- azure-container-apps
- azure-container-registry
page_type: sample
urlFragment: rag-postgres-openai-python
---

This project creates a web-based chat application with an API backend that can use OpenAI chat models to answer questions about the rows in a PostgreSQL database table. The frontend is built with React and FluentUI, while the backend is written with Python and FastAPI.

This project is designed for deployment to Azure using [the Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/), hosting the app on Azure Container Apps, the database in Azure PostgreSQL Flexible Server, and the models in Azure OpenAI.

For instructions on deploying this project to Azure, please refer to the [README on GitHub](https://github.com/Azure-Samples/rag-postgres-openai-python/?tab=readme-ov-file#rag-on-postgresql).
