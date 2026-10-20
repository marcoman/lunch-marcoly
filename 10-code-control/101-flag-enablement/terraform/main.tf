# LaunchDarkly capability: Terraform provider — feature flag resources
# Manages base flag configuration (name, key, variations, tags).
# Per-environment targeting is configured separately via launchdarkly_feature_flag_environment.
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

locals {
  # String multivariate colors for enable-grid-selection-highlight (shared with 99-use-cases).
  highlight_colors = ["green", "yellow", "red", "blue", "purple"]
}

# Enable flag: colored highlight on the selected grid cell (string: none | colors).
resource "launchdarkly_feature_flag" "enable_grid_selection_highlight" {
  project_key = var.project_key
  key         = "enable-grid-selection-highlight"
  name        = "Enable: grid selection highlight"
  description = "When on, the selected grid cell shows a colored highlight in addition to the X marker. When off, evaluations receive none (X only, no color). Fallthrough chooses the base color; enable-grid-highlight-color-override can replace that with cohort colors from the login name."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "none"
    name        = "No highlight"
    description = "X only — no colors (matches 00-reference-code)"
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
    on_variation  = 1 # green
    off_variation = 0 # none
  }

  tags = [
    "grid-navigator",
    "enable",
    "ui",
    "string",
    "managed-by-terraform",
  ]
}

# Show flag: display navigation move count in the grid header.
resource "launchdarkly_feature_flag" "show_navigation_move_count" {
  project_key = var.project_key
  key         = "show-navigation-move-count"
  name        = "Show: navigation move count"
  description = "When enabled, the grid header displays Count: N where N is the number of successful navigation moves. Default is hidden."
  temporary   = true

  variation_type = "boolean"

  variations {
    value       = true
    name        = "Visible"
    description = "Display Count: N in the grid header"
  }

  variations {
    value       = false
    name        = "Hidden"
    description = "Do not display the navigation count"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "show",
    "header",
    "managed-by-terraform",
  ]
}

# Enable flag: override highlight color using cohort words in the login name.
resource "launchdarkly_feature_flag" "enable_grid_highlight_color_override" {
  project_key = var.project_key
  key         = "enable-grid-highlight-color-override"
  name        = "Enable: grid highlight color override"
  description = "When on (and enable-grid-selection-highlight serves a color), selection and username colors follow cohort rules parsed from the login name (human, robot, beta). When off, highlight uses the base fallthrough color from enable-grid-selection-highlight."
  temporary   = false

  variation_type = "boolean"

  variations {
    value       = true
    name        = "Override on"
    description = "Apply cohort-based highlight and username colors from login name"
  }

  variations {
    value       = false
    name        = "Override off"
    description = "Use the base fallthrough color from enable-grid-selection-highlight"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "enable",
    "ui",
    "context",
    "override",
    "managed-by-terraform",
  ]
}

# Default show-navigation-move-count to OFF (hidden) in the target environment.
resource "launchdarkly_feature_flag_environment" "show_navigation_move_count_env" {
  flag_id = launchdarkly_feature_flag.show_navigation_move_count.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 1
}

# Default highlight flag to OFF (none) in the target environment.
resource "launchdarkly_feature_flag_environment" "enable_grid_selection_highlight_env" {
  flag_id = launchdarkly_feature_flag.enable_grid_selection_highlight.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1 # green when turned on
  }

  off_variation = 0 # none
}

# Default color-override flag to OFF in the target environment.
resource "launchdarkly_feature_flag_environment" "enable_grid_highlight_color_override_env" {
  flag_id = launchdarkly_feature_flag.enable_grid_highlight_color_override.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 1
}

# Show flag: host OS emoji beside username (uses private hostOs context attribute).
resource "launchdarkly_feature_flag" "show_host_os_emoji" {
  project_key = var.project_key
  key         = "show-host-os-emoji"
  name        = "Show: host OS emoji"
  description = "When enabled, displays an OS emoji before the username. The host OS is sent as a private context attribute (hostOs) for targeting."
  temporary   = true

  variation_type = "boolean"

  variations {
    value       = true
    name        = "Visible"
    description = "Show OS emoji before username (linux penguin, macOS apple, Windows window, other smiley)"
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
    "private-attributes",
    "managed-by-terraform",
  ]
}

# Default show-host-os-emoji to OFF in the target environment.
resource "launchdarkly_feature_flag_environment" "show_host_os_emoji_env" {
  flag_id = launchdarkly_feature_flag.show_host_os_emoji.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 1
}

output "flag_keys" {
  description = "Feature flag keys provisioned by this configuration"
  value = [
    launchdarkly_feature_flag.enable_grid_selection_highlight.key,
    launchdarkly_feature_flag.enable_grid_highlight_color_override.key,
    launchdarkly_feature_flag.show_navigation_move_count.key,
    launchdarkly_feature_flag.show_host_os_emoji.key,
  ]
}
