targetScope = 'resourceGroup'

param accountName string
param location string

resource inference 'Microsoft.InferenceService/inferenceAccounts@2026-08-01-preview' = {
  name: accountName
  location: location
}

output endpoint string = inference.properties.endpoint
