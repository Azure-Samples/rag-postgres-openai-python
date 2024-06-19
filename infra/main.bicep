targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name which is used to generate a short unique hash for each resource')
param name string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Whether the deployment is running on GitHub Actions')
param runningOnGh string = ''

@description('Id of the user or app to assign application roles')
param principalId string = ''

@minLength(1)
@description('Location for the OpenAI resource')
// Look for gpt-35-turbo 0125 on the availability table:
// https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#standard-deployment-model-availability
@allowed([
  'canadaeast'
  'northcentralus'
  'southcentralus'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param openAILocation string

@description('Name of the OpenAI resource group. If not specified, the resource group name will be generated.')
param openAIResourceGroupName string = ''

@description('Whether to deploy Azure OpenAI resources')
param deployAzureOpenAI bool = true

@description('Name of the GPT model to deploy')
param chatModelName string = ''
@description('Name of the model deployment')
param chatDeploymentName string = ''

@description('Version of the GPT model to deploy')
// See version availability in this table:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#gpt-4-and-gpt-4-turbo-preview-models
param chatDeploymentVersion string = ''

param azureOpenAIAPIVersion string = '2024-03-01-preview'
@secure()
param azureOpenAIKey string = ''
@description('Azure OpenAI endpoint to use, if not using the one deployed here.')
param azureOpenAIEndpoint string = ''

@description('Whether to use Azure OpenAI (either deployed here or elsewhere) or OpenAI.com')
var useAzureOpenAI = deployAzureOpenAI || !empty(azureOpenAIEndpoint)

@description('Capacity of the GPT deployment')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param chatDeploymentCapacity int = 0
var chatConfig = {
  modelName: !empty(chatModelName) ? chatModelName : (useAzureOpenAI ? 'gpt-35-turbo' : 'gpt-3.5-turbo')
  deploymentName: !empty(chatDeploymentName) ? chatDeploymentName : 'gpt-35-turbo'
  deploymentVersion: !empty(chatDeploymentVersion) ? chatDeploymentVersion : '0125'
  deploymentCapacity: chatDeploymentCapacity != 0 ? chatDeploymentCapacity : 30
}

param embedModelName string = ''
param embedDeploymentName string = ''
param embedDeploymentVersion string = ''
param embedDeploymentCapacity int = 0
param embedDimensions int = 0

var embedConfig = {
  modelName: !empty(embedModelName) ? embedModelName : 'text-embedding-ada-002'
  deploymentName: !empty(embedDeploymentName) ? embedDeploymentName : 'text-embedding-ada-002'
  deploymentVersion: !empty(embedDeploymentVersion) ? embedDeploymentVersion : '2'
  deploymentCapacity: embedDeploymentCapacity != 0 ? embedDeploymentCapacity : 30
  dimensions: embedDimensions != 0 ? embedDimensions : 1536
}

param webAppExists bool = false

var resourceToken = toLower(uniqueString(subscription().id, name, location))
var prefix = '${name}-${resourceToken}'
var tags = { 'azd-env-name': name }

resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${name}-rg'
  location: location
  tags: tags
}

var postgresServerName = '${prefix}-postgresql'
var postgresDatabaseName = 'postgres'
var postgresEntraAdministratorObjectId = principalId
var postgresEntraAdministratorType = empty(runningOnGh) ? 'User' : 'ServicePrincipal'
var postgresEntraAdministratorName = 'admin${uniqueString(resourceGroup.id, principalId)}'

module postgresServer 'core/database/postgresql/flexibleserver.bicep' = {
  name: 'postgresql'
  scope: resourceGroup
  params: {
    name: postgresServerName
    location: location
    tags: tags
    sku: {
      name: 'Standard_B1ms'
      tier: 'Burstable'
    }
    storage: {
      storageSizeGB: 32
    }
    version: '15'
    authType: 'EntraOnly'
    entraAdministratorName: postgresEntraAdministratorName
    entraAdministratorObjectId: postgresEntraAdministratorObjectId
    entraAdministratorType: postgresEntraAdministratorType
    allowAzureIPsFirewall: true
    allowAllIPsFirewall: true // Necessary for post-provision script, can be disabled after
  }
}

// Monitor application with Azure Monitor
module monitoring 'core/monitor/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    applicationInsightsDashboardName: '${prefix}-appinsights-dashboard'
    applicationInsightsName: '${prefix}-appinsights'
    logAnalyticsName: '${take(prefix, 50)}-loganalytics' // Max 63 chars
  }
}

// Container apps host (including container registry)
module containerApps 'core/host/container-apps.bicep' = {
  name: 'container-apps'
  scope: resourceGroup
  params: {
    name: 'app'
    location: location
    containerAppsEnvironmentName: '${prefix}-containerapps-env'
    containerRegistryName: '${replace(prefix, '-', '')}registry'
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsWorkspaceName
  }
}

// Web frontend
var webAppName = replace('${take(prefix, 19)}-ca', '--', '-')
var webAppIdentityName = '${prefix}-id-web'
var webAppEnv = [
  {
    name: 'POSTGRES_HOST'
    value: postgresServer.outputs.POSTGRES_DOMAIN_NAME
  }
  {
    name: 'POSTGRES_USERNAME'
    value: webAppIdentityName
  }
  {
    name: 'POSTGRES_DATABASE'
    value: postgresDatabaseName
  }
  {
    name: 'POSTGRES_SSL'
    value: 'require'
  }
  {
    name: 'RUNNING_IN_PRODUCTION'
    value: 'true'
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: monitoring.outputs.applicationInsightsConnectionString
  }
  {
    name: 'OPENAI_CHAT_HOST'
    value: useAzureOpenAI ? 'azure' : 'openaicom'
  }
  {
    name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
    value: useAzureOpenAI ? chatConfig.deploymentName : ''
  }
  {
    name: 'AZURE_OPENAI_CHAT_MODEL'
    value: useAzureOpenAI ? chatConfig.modelName : ''
  }
  {
    name: 'OPENAICOM_CHAT_MODEL'
    value: useAzureOpenAI ? '' : 'gpt-3.5-turbo'
  }
  {
    name: 'OPENAI_EMBED_HOST'
    value: useAzureOpenAI ? 'azure' : 'openaicom'
  }
  {
    name: 'OPENAICOM_EMBED_MODEL_DIMENSIONS'
    value: useAzureOpenAI ? '' : '1536'
  }
  {
    name: 'OPENAICOM_EMBED_MODEL'
    value: useAzureOpenAI ? '' : 'text-embedding-ada-002'
  }
  {
    name: 'AZURE_OPENAI_EMBED_MODEL'
    value: useAzureOpenAI ? embedConfig.modelName : ''
  }
  {
    name: 'AZURE_OPENAI_EMBED_DEPLOYMENT'
    value: useAzureOpenAI ? embedConfig.deploymentName : ''
  }
  {
    name: 'AZURE_OPENAI_EMBED_MODEL_DIMENSIONS'
    value: useAzureOpenAI ? string(embedConfig.dimensions) : ''
  }
  {
    name: 'AZURE_OPENAI_ENDPOINT'
    value: useAzureOpenAI ? (deployAzureOpenAI ? openAI.outputs.endpoint : azureOpenAIEndpoint) : ''
  }
  {
    name: 'AZURE_OPENAI_VERSION'
    value: useAzureOpenAI ? azureOpenAIAPIVersion : ''
  }
]
var webAppEnvWithSecret = !empty(azureOpenAIKey) ? union(webAppEnv, [
  {
    name: 'AZURE_OPENAI_KEY'
    secretRef: 'azure-openai-key'
  }
]) : webAppEnv

var secrets = !empty(azureOpenAIKey) ? {
  'azure-openai-key': azureOpenAIKey
} : {}

module web 'web.bicep' = {
  name: 'web'
  scope: resourceGroup
  params: {
    name: webAppName
    location: location
    tags: tags
    identityName: webAppIdentityName
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    exists: webAppExists
    environmentVariables: webAppEnvWithSecret
    secrets: secrets
  }
}

resource openAIResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing =
  if (!empty(openAIResourceGroupName)) {
    name: !empty(openAIResourceGroupName) ? openAIResourceGroupName : resourceGroup.name
  }

module openAI 'core/ai/cognitiveservices.bicep' = if (deployAzureOpenAI) {
  name: 'openai'
  scope: openAIResourceGroup
  params: {
    name: '${prefix}-openai'
    location: openAILocation
    tags: tags
    sku: {
      name: 'S0'
    }
    disableLocalAuth: true
    deployments: [
      {
        name: chatConfig.deploymentName
        model: {
          format: 'OpenAI'
          name: chatConfig.modelName
          version: chatConfig.deploymentVersion
        }
        sku: {
          name: 'Standard'
          capacity: chatConfig.deploymentCapacity
        }
      }
      {
        name: embedConfig.deploymentName
        model: {
          format: 'OpenAI'
          name: embedConfig.modelName
          version: embedConfig.deploymentVersion
        }
        sku: {
          name: 'Standard'
          capacity: embedConfig.deploymentCapacity
        }
      }
    ]
  }
}

// USER ROLES
module openAIRoleUser 'core/security/role.bicep' =
  if (empty(runningOnGh)) {
    scope: openAIResourceGroup
    name: 'openai-role-user'
    params: {
      principalId: principalId
      roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
      principalType: 'User'
    }
  }

// Backend roles
module openAIRoleBackend 'core/security/role.bicep' = {
  scope: openAIResourceGroup
  name: 'openai-role-backend'
  params: {
    principalId: web.outputs.SERVICE_WEB_IDENTITY_PRINCIPAL_ID
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}

output AZURE_LOCATION string = location
output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.applicationInsightsName

output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerApps.outputs.environmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName

output SERVICE_WEB_IDENTITY_PRINCIPAL_ID string = web.outputs.SERVICE_WEB_IDENTITY_PRINCIPAL_ID
output SERVICE_WEB_IDENTITY_NAME string = web.outputs.SERVICE_WEB_IDENTITY_NAME
output SERVICE_WEB_NAME string = web.outputs.SERVICE_WEB_NAME
output SERVICE_WEB_URI string = web.outputs.SERVICE_WEB_URI
output SERVICE_WEB_IMAGE_NAME string = web.outputs.SERVICE_WEB_IMAGE_NAME

output AZURE_OPENAI_ENDPOINT string = useAzureOpenAI ? (deployAzureOpenAI ? openAI.outputs.endpoint : azureOpenAIEndpoint) : ''
output AZURE_OPENAI_VERSION string =  useAzureOpenAI ? azureOpenAIAPIVersion : ''
output AZURE_OPENAI_CHAT_DEPLOYMENT string = useAzureOpenAI ? chatConfig.deploymentName : ''
output AZURE_OPENAI_EMBED_DEPLOYMENT string = useAzureOpenAI ? embedConfig.deploymentName : ''
output AZURE_OPENAI_CHAT_MODEL string = useAzureOpenAI ? chatConfig.modelName : ''
output AZURE_OPENAI_EMBED_MODEL string = useAzureOpenAI ? embedConfig.modelName : ''
output AZURE_OPENAI_EMBED_MODEL_DIMENSIONS int = useAzureOpenAI ? embedConfig.dimensions : 0

output POSTGRES_HOST string = postgresServer.outputs.POSTGRES_DOMAIN_NAME
output POSTGRES_USERNAME string = postgresEntraAdministratorName
output POSTGRES_DATABASE string = postgresDatabaseName

output BACKEND_URI string = web.outputs.uri
