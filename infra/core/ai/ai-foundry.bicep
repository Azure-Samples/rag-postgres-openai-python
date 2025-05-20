@minLength(1)
@description('Primary location for all resources')
param location string

@description('The AI Foundry resource name.')
param foundryName string

@description('The AI Project resource name.')
param projectName string = foundryName

param projectDescription string = ''
param projectDisplayName string = projectName

@description('The Storage Account resource name.')
param storageAccountName string

param principalId string
param principalType string

param tags object = {}

// Step 1: Create an AI Foundry resource
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: foundryName
  location: location
  tags: tags
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: toLower(foundryName)
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// Step 2: Create an AI Foundry project
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDescription
    displayName: projectDisplayName
  }
}

// Step 4: Create a storage account, needed for evaluations
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}

// Create a storage account connection for the foundry resource
resource storageAccountConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: account
  name: 'default-storage'
  properties: {
    authType: 'AAD'
    category: 'AzureStorageAccount'
    isSharedToAll: true
    target: storageAccount.properties.primaryEndpoints.blob
    metadata: {
      ApiType: 'Azure'
      ResourceId: storageAccount.id
    }
  }
}

// Assign a role to the project's managed identity for the storage account
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, 'Storage Blob Data Contributor', project.name)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Assign a role to the calling user for the AI Foundry project (needed for projects (including agents) API)
resource projectRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, 'Azure AI User', principalId)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d') // Azure AI User
    principalId: principalId
    principalType: 'User'
  }
}

// Assign a role to the calling user for the AI Foundry account (needed for Azure OpenAI API)
resource accountRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, 'Azure AI User', principalId)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d') // Azure AI User
    principalId: principalId
    principalType: 'User'
  }
}

output foundryName string = account.name
output projectName string = project.name
