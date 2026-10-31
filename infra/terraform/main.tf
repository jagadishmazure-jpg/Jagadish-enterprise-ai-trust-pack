# Residency guardrails as Azure Policy. Policy definitions and assignments are free; this stack
# creates no billable resources. Both rules are read from ../policies/*.json, the same files Bicep loads.
locals {
  deny_loose   = jsondecode(file("${path.module}/../policies/deny-loose-ai-deployments.json"))
  allowed_locs = jsondecode(file("${path.module}/../policies/allowed-locations-ai-data.json"))
}

resource "azurerm_policy_definition" "deny_loose_ai_deployments" {
  name         = "trustpack-deny-loose-ai-deployments"
  policy_type  = "Custom"
  mode         = local.deny_loose.mode
  display_name = local.deny_loose.displayName
  parameters   = jsonencode(local.deny_loose.parameters)
  policy_rule  = jsonencode(local.deny_loose.policyRule)
  metadata     = jsonencode({ category = "Trust pack residency", version = "1.0.0" })
}

resource "azurerm_policy_definition" "allowed_locations_ai_data" {
  name         = "trustpack-allowed-locations-ai-data"
  policy_type  = "Custom"
  mode         = local.allowed_locs.mode
  display_name = local.allowed_locs.displayName
  parameters   = jsonencode(local.allowed_locs.parameters)
  policy_rule  = jsonencode(local.allowed_locs.policyRule)
  metadata     = jsonencode({ category = "Trust pack residency", version = "1.0.0" })
}

resource "azurerm_subscription_policy_assignment" "deny_loose_ai_deployments" {
  name                 = "trustpack-deny-loose-ai"
  subscription_id      = var.subscription_id
  policy_definition_id = azurerm_policy_definition.deny_loose_ai_deployments.id
  parameters = jsonencode({
    deniedSkus = { value = var.denied_skus }
    effect     = { value = var.effect }
  })
}

resource "azurerm_subscription_policy_assignment" "allowed_locations_ai_data" {
  name                 = "trustpack-allowed-locs-ai"
  subscription_id      = var.subscription_id
  policy_definition_id = azurerm_policy_definition.allowed_locations_ai_data.id
  parameters = jsonencode({
    allowedLocations = { value = var.allowed_locations }
    effect           = { value = var.effect }
  })
}
