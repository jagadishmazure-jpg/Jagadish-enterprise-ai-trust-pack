// Residency guardrails as Azure Policy, at subscription scope. Parity with ../terraform:
// both load the same rule files from ../policies. Creates no billable resources.
targetScope = 'subscription'

@description('Regions allowed to hold resources tagged with a data-class.')
param allowedLocations array = [
  'swedencentral'
  'swedensouth'
  'francecentral'
]

// Must match trustpack.residency.policy.denied_skus('data_zone'); a pytest checks this.
@description('Microsoft Foundry deployment SKUs that may process data outside the boundary.')
param deniedSkus array = [
  'DeveloperTier'
  'GlobalBatch'
  'GlobalProvisionedManaged'
  'GlobalStandard'
]

@allowed([
  'Audit'
  'Deny'
  'Disabled'
])
param effect string = 'Deny'

var denyLoose = loadJsonContent('../policies/deny-loose-ai-deployments.json')
var allowedLocs = loadJsonContent('../policies/allowed-locations-ai-data.json')

resource denyLooseDef 'Microsoft.Authorization/policyDefinitions@2023-04-01' = {
  name: 'trustpack-deny-loose-ai-deployments'
  properties: {
    policyType: 'Custom'
    mode: denyLoose.mode
    displayName: denyLoose.displayName
    parameters: denyLoose.parameters
    policyRule: denyLoose.policyRule
    metadata: {
      category: 'Trust pack residency'
      version: '1.0.0'
    }
  }
}

resource allowedLocsDef 'Microsoft.Authorization/policyDefinitions@2023-04-01' = {
  name: 'trustpack-allowed-locations-ai-data'
  properties: {
    policyType: 'Custom'
    mode: allowedLocs.mode
    displayName: allowedLocs.displayName
    parameters: allowedLocs.parameters
    policyRule: allowedLocs.policyRule
    metadata: {
      category: 'Trust pack residency'
      version: '1.0.0'
    }
  }
}

resource denyLooseAssign 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'trustpack-deny-loose-ai'
  properties: {
    policyDefinitionId: denyLooseDef.id
    parameters: {
      deniedSkus: { value: deniedSkus }
      effect: { value: effect }
    }
  }
}

resource allowedLocsAssign 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'trustpack-allowed-locs-ai'
  properties: {
    policyDefinitionId: allowedLocsDef.id
    parameters: {
      allowedLocations: { value: allowedLocations }
      effect: { value: effect }
    }
  }
}

output policyDefinitionIds array = [
  denyLooseDef.id
  allowedLocsDef.id
]
