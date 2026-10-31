variable "subscription_id" {
  description = "Subscription to assign the residency policies to (full resource ID, /subscriptions/<guid>)."
  type        = string
}

variable "allowed_locations" {
  description = "Regions allowed to hold resources tagged with a data-class."
  type        = list(string)
  default     = ["swedencentral", "swedensouth", "francecentral"]
}

# Must match trustpack.residency.policy.denied_skus("data_zone"); a pytest checks this.
variable "denied_skus" {
  description = "Microsoft Foundry deployment SKUs that may process data outside the boundary."
  type        = list(string)
  default     = ["DeveloperTier", "GlobalBatch", "GlobalProvisionedManaged", "GlobalStandard"]
}

variable "effect" {
  description = "Policy effect: Audit first, then Deny."
  type        = string
  default     = "Deny"

  validation {
    condition     = contains(["Audit", "Deny", "Disabled"], var.effect)
    error_message = "effect must be Audit, Deny or Disabled."
  }
}
