# LaunchDarkly capability: Terraform provider — feature flag resources
# Provisions string, number, JSON, and boolean (anonymous context) flags.
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
  description = "LaunchDarkly API access token (set LD_ACCESS_TOKEN in the environment)"
  sensitive   = true
}

variable "api_host" {
  type        = string
  description = "LaunchDarkly API host (set LD_API_HOST; defaults to https://app.launchdarkly.com)"
  default     = "https://app.launchdarkly.com"
}

variable "project_key" {
  type        = string
  description = "LaunchDarkly project key (set LD_PROJECT_KEY)"
}

variable "environment_key" {
  type        = string
  description = "LaunchDarkly environment key for per-environment defaults (set LD_ENVIRONMENT_KEY)"
}

resource "launchdarkly_feature_flag" "show_anonymous_host_os_emoji" {
  project_key = var.project_key
  key         = "show-anonymous-host-os-emoji"
  name        = "Show: anonymous host OS emoji"
  description = "When enabled, displays an OS emoji before the username. Evaluated with an anonymous context and private hostOs attribute."
  temporary   = true

  variation_type = "boolean"

  variations {
    value       = true
    name        = "Visible"
    description = "Show OS emoji before username (anonymous context evaluation)"
  }

  variations {
    value       = false
    name        = "Hidden"
    description = "No OS emoji (default)"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "show",
    "header",
    "anonymous",
    "private-attributes",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag" "configure_navigation_count_label" {
  project_key = var.project_key
  key         = "configure-navigation-count-label"
  name        = "Configure: navigation count label"
  description = "String label prefix for the navigation move counter in the header (e.g. Count: N)."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "Count"
    name        = "Count"
    description = "Display Count: N (default)"
  }

  variations {
    value       = "Move Count"
    name        = "Move Count"
    description = "Display Move Count: N"
  }

  variations {
    value       = "Moves"
    name        = "Moves"
    description = "Display Moves: N"
  }

  variations {
    value       = "Navigation Counts"
    name        = "Navigation Counts"
    description = "Display Navigation Counts: N"
  }

  defaults {
    on_variation  = 0
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "configure",
    "header",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag" "configure_lucky_number" {
  project_key = var.project_key
  key         = "configure-lucky-number"
  name        = "Configure: lucky number"
  description = "Numeric value displayed in the header as Lucky Number is: N."
  temporary   = false

  variation_type = "number"

  variations {
    value       = 0
    name        = "Zero"
    description = "Lucky Number is: 0 (default)"
  }

  variations {
    value       = 1
    name        = "One"
    description = "Lucky Number is: 1"
  }

  variations {
    value       = 2
    name        = "Two"
    description = "Lucky Number is: 2"
  }

  variations {
    value       = 3
    name        = "Three"
    description = "Lucky Number is: 3"
  }

  variations {
    value       = 4
    name        = "Four"
    description = "Lucky Number is: 4"
  }

  variations {
    value       = 5
    name        = "Five"
    description = "Lucky Number is: 5"
  }

  defaults {
    on_variation  = 0
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "configure",
    "header",
    "number",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag" "configure_max_navigation_moves" {
  project_key = var.project_key
  key         = "configure-max-navigation-moves"
  name        = "Configure: max navigation moves"
  description = "JSON object with maxMoves limiting successful navigation moves per grid session."
  temporary   = false

  variation_type = "json"

  variations {
    value       = jsonencode({ maxMoves = 100 })
    name        = "Standard (100)"
    description = "Standard users: 100 total moves"
  }

  variations {
    value       = jsonencode({ maxMoves = 10 })
    name        = "Limited (10)"
    description = "Short limit for testing"
  }

  variations {
    value       = jsonencode({ maxMoves = 1000 })
    name        = "Extended (1000)"
    description = "High limit"
  }

  defaults {
    on_variation  = 0
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "configure",
    "navigation",
    "json",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "show_anonymous_host_os_emoji_env" {
  flag_id = launchdarkly_feature_flag.show_anonymous_host_os_emoji.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 1
}

resource "launchdarkly_feature_flag_environment" "configure_navigation_count_label_env" {
  flag_id = launchdarkly_feature_flag.configure_navigation_count_label.id
  env_key = var.environment_key

  on = true

  fallthrough {
    variation = 0
  }

  off_variation = 0
}

resource "launchdarkly_feature_flag_environment" "configure_lucky_number_env" {
  flag_id = launchdarkly_feature_flag.configure_lucky_number.id
  env_key = var.environment_key

  on = true

  fallthrough {
    variation = 0
  }

  off_variation = 0
}

resource "launchdarkly_feature_flag_environment" "configure_max_navigation_moves_env" {
  flag_id = launchdarkly_feature_flag.configure_max_navigation_moves.id
  env_key = var.environment_key

  on = true

  fallthrough {
    variation = 0
  }

  off_variation = 0
}

output "flag_keys" {
  description = "Feature flag keys provisioned by this configuration"
  value = [
    launchdarkly_feature_flag.show_anonymous_host_os_emoji.key,
    launchdarkly_feature_flag.configure_navigation_count_label.key,
    launchdarkly_feature_flag.configure_lucky_number.key,
    launchdarkly_feature_flag.configure_max_navigation_moves.key,
  ]
}
