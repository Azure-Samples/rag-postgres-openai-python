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
// Look for desired models on the availability table:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#global-standard-model-availability
@allowed([
  'australiaeast'
  'brazilsouth'
  'canadaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'germanywestcentral'
  'japaneast'
  'koreacentral'
  'northcentralus'
  'norwayeast'
  'polandcentral'
  'spaincentral'
  'southafricanorth'
  'southcentralus'
  'southindia'
  'swedencentral'
  'switzerlandnorth'
  'uksouth'
  'westeurope'
  'westus'
  'westus3'
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

@allowed([
  'azure'
  'openaicom'
])
param openAIChatHost string = 'azure'

@allowed([
  'azure'
  'openaicom'
])
param openAIEmbedHost string = 'azure'

@secure()
param openAIComKey string = ''

param azureOpenAIAPIVersion string = '2024-03-01-preview'
@secure()
param azureOpenAIKey string = ''

@description('Azure OpenAI endpoint to use, if not using the one deployed here.')
param azureOpenAIEndpoint string = ''

// Chat completion model
@description('Name of the chat model to deploy')
param chatModelName string // Set in main.parameters.json
@description('Name of the model deployment')
param chatDeploymentName string // Set in main.parameters.json

@description('Version of the chat model to deploy')
// See version availability in this table:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#global-standard-model-availability
param chatDeploymentVersion string // Set in main.parameters.json

@description('Sku of the chat deployment')
param chatDeploymentSku string // Set in main.parameters.json

@description('Capacity of the chat deployment')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param chatDeploymentCapacity int // Set in main.parameters.json

@description('Whether to deploy the evaluation model')
param deployEvalModel bool // Set in main.parameters.json

// Chat completion model used for evaluations (use most powerful model)
@description('Name of the chat model to use for evaluations')
param evalModelName string // Set in main.parameters.json
@description('Name of the model deployment for the evaluation model')
param evalDeploymentName string // Set in main.parameters.json

@description('Version of the chat model to deploy for evaluations')
// See version availability in this table:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#global-standard-model-availability
param evalDeploymentVersion string // Set in main.parameters.json

@description('Sku of the model deployment for evaluations')
param evalDeploymentSku string // Set in main.parameters.json

@description('Capacity of the chat deployment for evaluations (Go as high as possible)')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param evalDeploymentCapacity string // Set in main.parameters.json


// Embedding model
@description('Name of the embedding model to deploy')
param embedModelName string // Set in main.parameters.json
@description('Name of the embedding model deployment')
param embedDeploymentName string // Set in main.parameters.json

@description('Version of the embedding model to deploy')
// See version availability in this table:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#embeddings-models
param embedDeploymentVersion string // Set in main.parameters.json

@description('Sku of the embeddings model deployment')
param embedDeploymentSku string // Set in main.parameters.json

@description('Capacity of the embedding deployment')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param embedDeploymentCapacity int // Set in main.parameters.json

@description('Dimensions of the embedding model')
param embedDimensions int // Set in main.parameters.json

@description('Use AI project')
param useAiProject bool = false

param webAppExists bool = false

var resourceToken = toLower(uniqueString(subscription().id, name, location))
var prefix = '${toLower(name)}-${resourceToken}'
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
    applicationInsightsName: '${prefix}-appinsights'
    logAnalyticsName: '${take(prefix, 50)}-loganalytics' // Max 63 chars
  }
}


module applicationInsightsDashboard 'backend-dashboard.bicep' = {
  name: 'application-insights-dashboard'
  scope: resourceGroup
  params: {
    name: '${prefix}-appinsights-dashboard'
    location: location
    applicationInsightsName: monitoring.outputs.applicationInsightsName
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

var azureOpenAIKeySecret = !empty(azureOpenAIKey)
  ? {
      'azure-openai-key': azureOpenAIKey
    }
  : {}
var openAIComKeySecret = !empty(openAIComKey)
  ? {
      'openaicom-key': openAIComKey
    }
  : {}
var secrets = union(azureOpenAIKeySecret, openAIComKeySecret)

var azureOpenAIKeyEnv = !empty(azureOpenAIKey)
  ? [
      {
        name: 'AZURE_OPENAI_KEY'
        secretRef: 'azure-openai-key'
      }
    ]
  : []
var openAIComKeyEnv = !empty(openAIComKey)
  ? [
      {
        name: 'OPENAICOM_KEY'
        secretRef: 'openaicom-key'
      }
    ]
  : []

var webAppEnv = union(azureOpenAIKeyEnv, openAIComKeyEnv, [
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
    value: openAIChatHost
  }
  {
    name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
    value: openAIChatHost == 'azure' ? chatDeploymentName : ''
  }
  {
    name: 'AZURE_OPENAI_CHAT_MODEL'
    value: openAIChatHost == 'azure' ? chatModelName : ''
  }
  {
    name: 'OPENAICOM_CHAT_MODEL'
    value: openAIChatHost == 'openaicom' ? 'gpt-3.5-turbo' : ''
  }
  {
    name: 'OPENAI_EMBED_HOST'
    value: openAIEmbedHost
  }
  {
    name: 'OPENAICOM_EMBED_DIMENSIONS'
    value: openAIEmbedHost == 'openaicom' ? '1024' : ''
  }
  {
    name: 'OPENAICOM_EMBED_MODEL'
    value: openAIEmbedHost == 'openaicom' ? 'text-embedding-3-large' : ''
  }
  {
    name: 'AZURE_OPENAI_EMBED_MODEL'
    value: openAIEmbedHost == 'azure' ? embedModelName : ''
  }
  {
    name: 'AZURE_OPENAI_EMBED_DEPLOYMENT'
    value: openAIEmbedHost == 'azure' ? embedDeploymentName : ''
  }
  {
    name: 'AZURE_OPENAI_EMBED_DIMENSIONS'
    value: openAIEmbedHost == 'azure' ? string(embedDimensions) : ''
  }
  {
    name: 'AZURE_OPENAI_ENDPOINT'
    value: !empty(azureOpenAIEndpoint) ? azureOpenAIEndpoint : (deployAzureOpenAI ? openAI.outputs.endpoint : '')
  }
  {
    name: 'AZURE_OPENAI_VERSION'
    value: openAIChatHost == 'azure' ? azureOpenAIAPIVersion : ''
  }
])

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
    environmentVariables: webAppEnv
    secrets: secrets
  }
}

resource openAIResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(openAIResourceGroupName)) {
  name: !empty(openAIResourceGroupName) ? openAIResourceGroupName : resourceGroup.name
}

var defaultDeployments = [
  {
  name: chatDeploymentName
  model: {
    format: 'OpenAI'
    name: chatModelName
    version: chatDeploymentVersion
  }
  sku: {
    name: chatDeploymentSku
    capacity: chatDeploymentCapacity
  }
}
{
  name: embedDeploymentName
  model: {
    format: 'OpenAI'
    name: embedModelName
    version: embedDeploymentVersion
  }
  sku: {
    name: embedDeploymentSku
    capacity: embedDeploymentCapacity
  }
}]

var evalDeployment = {
  name: evalDeploymentName
  model: {
    format: 'OpenAI'
    name: evalModelName
    version: evalDeploymentVersion
  }
  sku: {
    name: evalDeploymentSku
    capacity: evalDeploymentCapacity
  }
}

var openAiDeployments = deployEvalModel ? union([evalDeployment], defaultDeployments) : defaultDeployments


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
    deployments: openAiDeployments
  }
}

module ai 'core/ai/ai-environment.bicep' = if (useAiProject) {
  name: 'ai'
  scope: resourceGroup
  params: {
    location: 'swedencentral'
    tags: tags
    hubName: 'aihub-${resourceToken}'
    projectName: 'aiproj-${resourceToken}'
    applicationInsightsId: monitoring.outputs.applicationInsightsId
  }
}

// USER ROLES
module openAIRoleUser 'core/security/role.bicep' = {
  scope: openAIResourceGroup
  name: 'openai-role-user'
  params: {
    principalId: principalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: empty(runningOnGh) ? 'User' : 'ServicePrincipal'
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
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name

output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.applicationInsightsName

output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerApps.outputs.environmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName

output SERVICE_WEB_IDENTITY_PRINCIPAL_ID string = web.outputs.SERVICE_WEB_IDENTITY_PRINCIPAL_ID
output SERVICE_WEB_IDENTITY_NAME string = web.outputs.SERVICE_WEB_IDENTITY_NAME
output SERVICE_WEB_NAME string = web.outputs.SERVICE_WEB_NAME
output SERVICE_WEB_URI string = web.outputs.SERVICE_WEB_URI
output SERVICE_WEB_IMAGE_NAME string = web.outputs.SERVICE_WEB_IMAGE_NAME

output OPENAI_CHAT_HOST string = openAIChatHost
output OPENAI_EMBED_HOST string = openAIEmbedHost
output AZURE_OPENAI_SERVICE string = deployAzureOpenAI ? openAI.outputs.name : ''
output AZURE_OPENAI_RESOURCE_GROUP string = deployAzureOpenAI ? openAIResourceGroup.name : ''
output AZURE_OPENAI_ENDPOINT string = !empty(azureOpenAIEndpoint)
  ? azureOpenAIEndpoint
  : (deployAzureOpenAI ? openAI.outputs.endpoint : '')
output AZURE_OPENAI_VERSION string = azureOpenAIAPIVersion
output AZURE_OPENAI_CHAT_DEPLOYMENT string = deployAzureOpenAI ? chatDeploymentName : ''
output AZURE_OPENAI_CHAT_DEPLOYMENT_VERSION string = deployAzureOpenAI ? chatDeploymentVersion : ''
output AZURE_OPENAI_CHAT_DEPLOYMENT_CAPACITY int = deployAzureOpenAI ? chatDeploymentCapacity : 0
output AZURE_OPENAI_CHAT_DEPLOYMENT_SKU string = deployAzureOpenAI ? chatDeploymentSku : ''
output AZURE_OPENAI_CHAT_MODEL string = deployAzureOpenAI ? chatModelName : ''
output AZURE_OPENAI_EMBED_DEPLOYMENT string = deployAzureOpenAI ? embedDeploymentName : ''
output AZURE_OPENAI_EMBED_DEPLOYMENT_VERSION string = deployAzureOpenAI ? embedDeploymentVersion : ''
output AZURE_OPENAI_EMBED_DEPLOYMENT_CAPACITY int = deployAzureOpenAI ? embedDeploymentCapacity : 0
output AZURE_OPENAI_EMBED_DEPLOYMENT_SKU string = deployAzureOpenAI ? embedDeploymentSku : ''
output AZURE_OPENAI_EMBED_MODEL string = deployAzureOpenAI ? embedModelName : ''
output AZURE_OPENAI_EMBED_DIMENSIONS string = deployAzureOpenAI ? string(embedDimensions) : ''

output AZURE_OPENAI_EVAL_DEPLOYMENT string = deployAzureOpenAI ? evalDeploymentName : ''
output AZURE_OPENAI_EVAL_DEPLOYMENT_VERSION string = deployAzureOpenAI ? evalDeploymentVersion : ''
output AZURE_OPENAI_EVAL_DEPLOYMENT_CAPACITY string = deployAzureOpenAI ? evalDeploymentCapacity : ''
output AZURE_OPENAI_EVAL_DEPLOYMENT_SKU string = deployAzureOpenAI ? evalDeploymentSku : ''
output AZURE_OPENAI_EVAL_MODEL string = deployAzureOpenAI ? evalModelName : ''

output AZURE_AI_PROJECT string = useAiProject ? ai.outputs.projectName : ''

output POSTGRES_HOST string = postgresServer.outputs.POSTGRES_DOMAIN_NAME
output POSTGRES_USERNAME string = postgresEntraAdministratorName
output POSTGRES_DATABASE string = postgresDatabaseName

output BACKEND_URI string = web.outputs.uri
