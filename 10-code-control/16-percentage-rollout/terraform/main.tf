# LaunchDarkly: static percentage rollout on the default rule.
# https://launchdarkly.com/docs/home/flags/rollouts
# https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs/resources/feature_flag_environment

terraform {
  required_version = ">= 1.5"

  required_providers {
    launchdarkly = {
      source  = "launchdarkly/launchdarkly"
      version = "~> 2.0"
    }
  }
}

provider "launchdarkly" {
  access_token = var.access_token
  api_host     = var.api_host
}

variable "access_token" {
  type        = string
  description = "LaunchDarkly API access token"
  sensitive   = true
}

variable "api_host" {
  type        = string
  description = "LaunchDarkly API host"
  default     = "https://app.launchdarkly.com"
}

variable "project_key" {
  type        = string
  description = "LaunchDarkly project key"
}

variable "environment_key" {
  type        = string
  description = "LaunchDarkly environment key"
}

variable "green_percent" {
  type        = number
  description = "Static percentage of user contexts receiving green"
  default     = 30

  validation {
    condition     = var.green_percent >= 0 && var.green_percent <= 100
    error_message = "green_percent must be between 0 and 100."
  }
}

resource "launchdarkly_feature_flag" "highlight_pct" {
  project_key = var.project_key
  key         = "enable-grid-selection-highlight-pct"
  name        = "Enable: grid selection highlight (pct)"
  description = "16-percentage-rollout. Static green/none rollout on username context key. Dedicated key so 11 stays independent. Not a progressive rollout."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "none"
    name        = "No highlight"
    description = "X only — no color"
  }

  variations {
    value       = "green"
    name        = "Green"
    description = "Green selection highlight"
  }

  defaults {
    on_variation  = 1
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "enable",
    "ui",
    "string",
    "percentage-rollout",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "highlight_pct" {
  flag_id = launchdarkly_feature_flag.highlight_pct.id
  env_key = var.environment_key

  on = true

  fallthrough {
    # Weights are thousandths of a percent and follow variation order:
    # none first, green second.
    rollout_weights = [
      (100 - var.green_percent) * 1000,
      var.green_percent * 1000,
    ]
    context_kind = "user"
    bucket_by    = "key"
  }

  off_variation = 0
}

output "flag_key" {
  value = launchdarkly_feature_flag.highlight_pct.key
}

output "rollout" {
  value = "${var.green_percent}% green / ${100 - var.green_percent}% none"
}
