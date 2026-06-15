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

# Configure flag: enable highlight on the selected grid cell (default off = X only).
resource "launchdarkly_feature_flag" "configure_grid_selection_green_highlight" {
  project_key = var.project_key
  key         = "configure-grid-selection-green-highlight"
  name        = "Configure: grid selection green highlight"
  description = "When enabled, the selected grid cell shows a colored highlight (default pink) in addition to the X marker. Default is X only with no colors."
  temporary   = false

  variation_type = "boolean"

  variations {
    value       = true
    name        = "Highlight enabled"
    description = "Selected cell shows X with colored highlight (pink by default, or context color when context flag is on)"
  }

  variations {
    value       = false
    name        = "X only"
    description = "Selected cell shows X with no colors (matches 00-reference)"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "configure",
    "ui",
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

# Configure flag: context-based highlight colors derived from the logged-in username.
resource "launchdarkly_feature_flag" "configure_grid_selection_context_highlight" {
  project_key = var.project_key
  key         = "configure-grid-selection-context-highlight"
  name        = "Configure: grid selection context highlight"
  description = "When enabled with the highlight flag, selection and username colors follow cohort rules parsed from the login name (human, robot, beta). When off, highlight uses pink."
  temporary   = false

  variation_type = "boolean"

  variations {
    value       = true
    name        = "Context colors"
    description = "Apply cohort-based highlight and username colors from login name"
  }

  variations {
    value       = false
    name        = "Default pink"
    description = "Use pink highlight when highlight flag is on"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "configure",
    "ui",
    "context",
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

# Default configure flag to OFF (X only, no colors) in the target environment.
resource "launchdarkly_feature_flag_environment" "configure_grid_selection_green_highlight_env" {
  flag_id = launchdarkly_feature_flag.configure_grid_selection_green_highlight.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  off_variation = 1
}

# Default context highlight flag to OFF (pink default) in the target environment.
resource "launchdarkly_feature_flag_environment" "configure_grid_selection_context_highlight_env" {
  flag_id = launchdarkly_feature_flag.configure_grid_selection_context_highlight.id
  env_key = var.environment_key

  on = false

  fallthrough {
    variation = 1
  }

  ]
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
    launchdarkly_feature_flag.configure_grid_selection_green_highlight.key,
    launchdarkly_feature_flag.configure_grid_selection_context_highlight.key,
    launchdarkly_feature_flag.show_navigation_move_count.key,
    launchdarkly_feature_flag.show_host_os_emoji.key,
  ]
}
