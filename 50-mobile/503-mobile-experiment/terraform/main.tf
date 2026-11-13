# LaunchDarkly feature flag, environment targeting, and conversion metric.
# https://launchdarkly.com/docs/guides/infrastructure/terraform

terraform {
  required_version = ">= 1.5"

  required_providers {
    launchdarkly = {
      source  = "launchdarkly/launchdarkly"
      version = "~> 2.29"
    }
  }
}

provider "launchdarkly" {
  access_token = var.access_token
  api_host     = var.api_host
}

variable "access_token" {
  type        = string
  description = "LaunchDarkly API access token."
  sensitive   = true
}

variable "api_host" {
  type        = string
  description = "LaunchDarkly API host."
  default     = "https://app.launchdarkly.com"
}

variable "project_key" {
  type        = string
  description = "LaunchDarkly project key."
}

variable "environment_key" {
  type        = string
  description = "LaunchDarkly environment key."
}

# Feature flags — boolean variations and mobile SDK availability.
# https://registry.terraform.io/providers/launchdarkly/launchdarkly/2.29.0/docs/resources/feature_flag
resource "launchdarkly_feature_flag" "mobile_onboarding" {
  project_key = var.project_key
  key         = "acme-mobile-onboarding-v2"
  name        = "Acme: mobile onboarding helper"
  description = "False is control; true shows the onboarding helper."
  temporary   = true

  variation_type = "boolean"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = true
  }

  variations {
    value       = false
    name        = "Control"
    description = "Open the grid immediately"
  }

  variations {
    value       = true
    name        = "Treatment"
    description = "Show How to play before the grid"
  }

  defaults {
    on_variation  = 1
    off_variation = 0
  }

  tags = ["acme", "mobile-sdk", "experimentation", "onboarding", "managed-by-terraform"]
}

# Environment configuration starts safely off. Experimentation can later own
# its allocation without changing the flag's false off variation.
resource "launchdarkly_feature_flag_environment" "mobile_onboarding" {
  flag_id = launchdarkly_feature_flag.mobile_onboarding.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 0
}

# Metrics — a non-numeric custom conversion measured per user.
# https://registry.terraform.io/providers/launchdarkly/launchdarkly/2.29.0/docs/resources/metric
resource "launchdarkly_metric" "mobile_onboarding_completed" {
  project_key         = var.project_key
  key                 = "mobile_onboarding_completed"
  name                = "Acme: mobile onboarding completed"
  description         = "Conversion after the first successful orthogonal grid move."
  kind                = "custom"
  event_key           = "mobile_onboarding_completed"
  is_numeric          = false
  success_criteria    = "HigherThanBaseline"
  randomization_units = ["user"]

  tags = ["acme", "mobile", "experimentation", "onboarding", "managed-by-terraform"]
}

output "flag_key" {
  value = launchdarkly_feature_flag.mobile_onboarding.key
}

output "metric_key" {
  value = launchdarkly_metric.mobile_onboarding_completed.key
}
