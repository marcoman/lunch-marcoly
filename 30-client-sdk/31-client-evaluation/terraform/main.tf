# LaunchDarkly capability: Terraform — client-side-available feature flags
# https://launchdarkly.com/docs/guides/infrastructure/terraform
# Keywords: client-side availability, using_environment_id

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
  description = "LaunchDarkly API host (set LD_API_HOST)"
  default     = "https://app.launchdarkly.com"
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

resource "launchdarkly_feature_flag" "enable_client_grid_highlight" {
  project_key = var.project_key
  key         = "enable-client-grid-highlight"
  name        = "Enable: client grid highlight"
  description = "Browser-evaluated string flag. Off serves none (X only). On serves the fallthrough color."
  temporary   = false

  variation_type = "string"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = false
  }

  variations {
    value       = "none"
    name        = "No highlight"
    description = "X only — matches 02-reference-client-code"
  }

  dynamic "variations" {
    for_each = local.highlight_colors
    content {
      value       = variations.value
      name        = title(variations.value)
      description = "${title(variations.value)} selection highlight"
    }
  }

  defaults {
    on_variation  = 1
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "client-sdk",
    "enable",
    "ui",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag" "show_client_move_count" {
  project_key = var.project_key
  key         = "show-client-move-count"
  name        = "Show: client move count"
  description = "Browser-evaluated boolean flag. When on, the grid header shows Count: N."
  temporary   = true

  variation_type = "boolean"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = false
  }

  variations {
    value       = true
    name        = "Visible"
    description = "Display Count: N"
  }

  variations {
    value       = false
    name        = "Hidden"
    description = "Hide the navigation count"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "client-sdk",
    "show",
    "header",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "enable_client_grid_highlight_env" {
  flag_id = launchdarkly_feature_flag.enable_client_grid_highlight.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 0
}

resource "launchdarkly_feature_flag_environment" "show_client_move_count_env" {
  flag_id = launchdarkly_feature_flag.show_client_move_count.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 1
}

output "flag_keys" {
  value = [
    launchdarkly_feature_flag.enable_client_grid_highlight.key,
    launchdarkly_feature_flag.show_client_move_count.key,
  ]
}
