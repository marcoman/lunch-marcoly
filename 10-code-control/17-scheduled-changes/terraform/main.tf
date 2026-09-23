# LaunchDarkly flag prepared for a scheduled turn-on change.
# https://launchdarkly.com/docs/home/flags/scheduled-changes

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

resource "launchdarkly_feature_flag" "highlight_scheduled" {
  project_key = var.project_key
  key         = "enable-grid-selection-highlight-sched"
  name        = "Enable: grid selection highlight (scheduled)"
  description = "17-scheduled-changes. Starts off; the lab schedules a turnFlagOn change after a selected delay."
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
    "scheduled-changes",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "highlight_scheduled" {
  flag_id = launchdarkly_feature_flag.highlight_scheduled.id
  env_key = var.environment_key

  on            = false
  off_variation = 0

  fallthrough {
    variation = 1
  }
}

output "flag_key" {
  value = launchdarkly_feature_flag.highlight_scheduled.key
}
