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

resource "launchdarkly_feature_flag" "configure_grid_selection_green_highlight" {
  project_key = var.project_key
  key         = "configure-grid-selection-green-highlight"
  name        = "Configure: grid selection green highlight"
  description = "Guarded rollout example: highlight color for selected grid cell."
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
    "guarded-rollout",
    "configure",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "configure_grid_selection_green_highlight_env" {
  flag_id = launchdarkly_feature_flag.configure_grid_selection_green_highlight.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 0
}

output "flag_key" {
  value = launchdarkly_feature_flag.configure_grid_selection_green_highlight.key
}

resource "launchdarkly_metric" "grid_nav_latency" {
  project_key      = var.project_key
  key              = "grid-nav-latency"
  name             = "Grid navigation latency"
  description      = "Milliseconds from navigation input to grid update when green highlight is enabled. Guardrail threshold: 200 ms."
  kind             = "custom"
  event_key        = "grid-navigation-latency"
  is_numeric       = true
  unit             = "milliseconds"
  success_criteria = "LowerThanBaseline"
  analysis_type    = "mean"
  unit_aggregation_type = "average"
  randomization_units = ["user"]

  tags = [
    "grid-navigator",
    "use-case",
    "guarded-rollout",
    "latency",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_metric" "grid_highlight_error_rate" {
  project_key      = var.project_key
  key              = "grid-highlight-error-rate"
  name             = "Grid highlight error rate"
  description      = "Incorrect highlight color displayed when green highlight is enabled. Guardrail threshold: 0% error rate."
  kind             = "custom"
  event_key        = "grid-highlight-color-error"
  is_numeric       = false
  success_criteria = "LowerThanBaseline"
  randomization_units = ["user"]

  tags = [
    "grid-navigator",
    "use-case",
    "guarded-rollout",
    "error-rate",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_metric" "grid_nav_movement" {
  project_key      = var.project_key
  key              = "grid-nav-movement"
  name             = "Grid navigation movement"
  description      = "Number of grid navigations per user session. Guardrail threshold: at least 1 navigation."
  kind             = "custom"
  event_key        = "grid-navigation-count"
  is_numeric       = true
  unit             = "navigations"
  success_criteria = "HigherThanBaseline"
  analysis_type    = "mean"
  unit_aggregation_type = "sum"
  randomization_units = ["user"]

  tags = [
    "grid-navigator",
    "use-case",
    "guarded-rollout",
    "movement",
    "managed-by-terraform",
  ]
}

output "metric_keys" {
  value = [
    launchdarkly_metric.grid_nav_latency.key,
    launchdarkly_metric.grid_highlight_error_rate.key,
    launchdarkly_metric.grid_nav_movement.key,
  ]
}
