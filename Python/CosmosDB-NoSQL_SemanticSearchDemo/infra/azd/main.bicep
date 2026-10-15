targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('Unique azd environment name. Use lowercase letters, digits and hyphens.')
param environmentName string

@allowed([
  'uksouth'
  'eastus2'
  'westus3'
])
param location string = 'uksouth'

@minLength(36)
@maxLength(36)
@description('Signed-in azd user object ID, supplied by AZURE_PRINCIPAL_ID.')
param principalId string

@minLength(36)
@maxLength(36)
@description('Persisted lowercase UUID starting a-f. Validated by the preprovision hook; never invent or change an existing name.')
param cosmosAccountName string
@allowed(['true', 'false'])
param createInference string

resource group 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-reranker-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
    'sample': 'standalone-semantic-reranker'
  }
}

module backend 'resources.bicep' = {
  name: 'reranker-backend'
  scope: group
  params: {
    cosmosAccountName: cosmosAccountName
    createInference: createInference
    location: location
    principalId: principalId
    includeDotnet: false
  }
}

output AZURE_RESOURCE_GROUP string = group.name
output COSMOS_ACCOUNT_NAME string = backend.outputs.accountName
output COSMOS_ACCOUNT_ID string = backend.outputs.cosmosAccountId
output COSMOS_URI string = backend.outputs.cosmosEndpoint
output COSMOS_DB_DATABASE string = backend.outputs.databaseName
output INFERENCE_ACCOUNT_NAME string = backend.outputs.accountName
output INFERENCE_ACCOUNT_ID string = backend.outputs.inferenceAccountId
output AZURE_AI_INFERENCE_ENDPOINT string = backend.outputs.inferenceEndpoint
