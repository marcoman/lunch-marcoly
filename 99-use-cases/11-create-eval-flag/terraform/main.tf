# LaunchDarkly capability: Terraform provider — create/eval highlight flag
# See: https://launchdarkly.com/docs/guides/infrastructure/terraform

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
  description = "LaunchDarkly API access token (set LD_ACCESS_TOKEN)"
  sensitive   = true
}

variable "api_host" {
  type        = string
  default     = "https://app.launchdarkly.com"
  description = "LaunchDarkly API host"
}

variable "project_key" {
  type        = string
  description = "LaunchDarkly project key (set LD_PROJECT_KEY)"
}

variable "environment_key" {
  type        = string
  description = "LaunchDarkly environment key (set LD_ENVIRONMENT_KEY)"
}

locals {
  highlight_colors = ["green", "yellow", "red", "blue", "purple"]
}

resource "launchdarkly_feature_flag" "enable_grid_selection_highlight" {
  project_key = var.project_key
  key         = "enable-grid-selection-highlight"
  name        = "Enable: grid selection highlight"
  description = "When on, the selected grid cell shows a colored highlight in addition to the X marker. When off, evaluations receive none (X only, no color). Fallthrough chooses the base color."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "none"
    name        = "No highlight"
    description = "X only — no colors"
  }

  dynamic "variations" {
    for_each = local.highlight_colors
    content {
      value       = variations.value
      name        = title(variations.value)
      description = "${title(variations.value)} highlight"
    }
  }

  defaults {
    on_variation  = 1
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "use-case",
    "create-eval-flag",
    "configure",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "enable_grid_selection_highlight_env" {
  flag_id = launchdarkly_feature_flag.enable_grid_selection_highlight.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 0
}

output "flag_key" {
  value = launchdarkly_feature_flag.enable_grid_selection_highlight.key
}
