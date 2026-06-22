# LaunchDarkly capability: Terraform provider — ABCD test flag
# Provisions configure-navigation-count-label (off by default in target environment).
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

resource "launchdarkly_feature_flag" "configure_navigation_count_label" {
  project_key = var.project_key
  key         = "configure-navigation-count-label"
  name        = "Configure: navigation count label"
  description = "ABCD test: string label for navigation move counter (Count, Move Count, Moves, Navigation Counts)."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "Count"
    name        = "Count"
    description = "Variation A — Count: N"
  }

  variations {
    value       = "Move Count"
    name        = "Move Count"
    description = "Variation B — Move Count: N"
  }

  variations {
    value       = "Moves"
    name        = "Moves"
    description = "Variation C — Moves: N"
  }

  variations {
    value       = "Navigation Counts"
    name        = "Navigation Counts"
    description = "Variation D — Navigation Counts: N"
  }

  defaults {
    on_variation  = 0
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "use-case",
    "abcd-test",
    "configure",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "configure_navigation_count_label_env" {
  flag_id = launchdarkly_feature_flag.configure_navigation_count_label.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 0
  }

  off_variation = 0
}

output "flag_key" {
  value = launchdarkly_feature_flag.configure_navigation_count_label.key
}
