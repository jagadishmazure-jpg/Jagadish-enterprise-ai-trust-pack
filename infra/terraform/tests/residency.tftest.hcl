# Offline plan with a mocked provider: no Azure credentials, nothing created.
mock_provider "azurerm" {}

variables {
  subscription_id = "/subscriptions/00000000-0000-0000-0000-000000000000"
}

run "policies_plan" {
  command = plan

  assert {
    condition     = azurerm_policy_definition.deny_loose_ai_deployments.mode == "All"
    error_message = "deployment rule must use mode All"
  }
  assert {
    condition     = contains(var.denied_skus, "GlobalStandard") && !contains(var.denied_skus, "DataZoneStandard")
    error_message = "EU data-zone default must deny Global types and allow Data Zone types"
  }
  assert {
    condition     = jsondecode(azurerm_subscription_policy_assignment.allowed_locations_ai_data.parameters).effect.value == "Deny"
    error_message = "default effect must be Deny"
  }
}

run "bad_effect_rejected" {
  command = plan
  variables {
    effect = "Allow"
  }
  expect_failures = [var.effect]
}
