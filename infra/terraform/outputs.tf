output "policy_definition_ids" {
  description = "IDs of the two residency policy definitions."
  value = [
    azurerm_policy_definition.deny_loose_ai_deployments.id,
    azurerm_policy_definition.allowed_locations_ai_data.id,
  ]
}
