import logging
import os

from azure.identity import AzureDeveloperCliCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from dotenv_azd import load_azd_env

logger = logging.getLogger("ragapp")


def delete_deployments(resource_name: str, resource_group: str, subscription_id: str, tenant_id: str | None = None):
    """
    Delete all deployments for an Azure OpenAI resource
    """
    if tenant_id:
        logger.info("Authenticating to Azure using Azure Developer CLI Credential for tenant %s", tenant_id)
        azure_credential = AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
    else:
        logger.info("Authenticating to Azure using Azure Developer CLI Credential")
        azure_credential = AzureDeveloperCliCredential(process_timeout=60)

    # Initialize the Cognitive Services client
    client = CognitiveServicesManagementClient(azure_credential, subscription_id=subscription_id)

    # List all deployments
    deployments = client.deployments.list(resource_group_name=resource_group, account_name=resource_name)

    # Delete each deployment and wait for the operation to complete
    for deployment in deployments:
        deployment_name = deployment.name
        if not deployment_name:
            continue
        poller = client.deployments.begin_delete(
            resource_group_name=resource_group, account_name=resource_name, deployment_name=deployment_name
        )
        poller.result()
        logger.info(f"Deployment {deployment_name} deleted successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_azd_env()

    try:
        resource_name = os.environ["AZURE_OPENAI_SERVICE"]
        resource_group = os.environ["AZURE_OPENAI_RESOURCE_GROUP"]
        subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        tenant_id = os.environ["AZURE_TENANT_ID"]
    except KeyError as e:
        logger.error("Missing azd environment variable %s", e)
        exit(1)

    delete_deployments(resource_name, resource_group, subscription_id, tenant_id)
