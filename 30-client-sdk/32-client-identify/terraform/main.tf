# LaunchDarkly capability: Terraform — identify demo flags + key targeting
# https://launchdarkly.com/docs/guides/infrastructure/terraform
# https://launchdarkly.com/docs/home/flags/target-rules

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

resource "launchdarkly_feature_flag" "enable_identify_grid_highlight" {
  project_key = var.project_key
  key         = "enable-identify-grid-highlight"
  name        = "Enable: identify grid highlight"
  description = "Browser string flag. Targeting on context key: alice→green, bob→blue, else none."
  temporary   = false

  variation_type = "string"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = false
  }

  variations {
    value       = "none"
    name        = "No highlight"
    description = "Fallthrough / off"
  }
  variations {
    value       = "green"
    name        = "Green"
    description = "Alice"
  }
  variations {
    value       = "yellow"
    name        = "Yellow"
    description = "Yellow"
  }
  variations {
    value       = "red"
    name        = "Red"
    description = "Red"
  }
  variations {
    value       = "blue"
    name        = "Blue"
    description = "Bob"
  }
  variations {
    value       = "purple"
    name        = "Purple"
    description = "Purple"
  }

  defaults {
    on_variation  = 0
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "client-sdk",
    "identify",
    "enable",
    "ui",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag" "show_identify_move_count" {
  project_key = var.project_key
  key         = "show-identify-move-count"
  name        = "Show: identify move count"
  description = "Browser boolean flag. Targeting on context key: alice→true, bob and fallthrough→false."
  temporary   = true

  variation_type = "boolean"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = false
  }

  variations {
    value       = true
    name        = "Visible"
    description = "Alice"
  }
  variations {
    value       = false
    name        = "Hidden"
    description = "Bob / fallthrough"
  }

  defaults {
    on_variation  = 1
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "client-sdk",
    "identify",
    "show",
    "header",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "enable_identify_grid_highlight_env" {
  flag_id = launchdarkly_feature_flag.enable_identify_grid_highlight.id
  env_key = var.environment_key

  on            = true
  off_variation = 0

  rules {
    description = "Alice"
    clauses {
      context_kind = "user"
      attribute    = "key"
      op           = "in"
      values       = ["alice"]
    }
    variation = 1
  }

  rules {
    description = "Bob"
    clauses {
      context_kind = "user"
      attribute    = "key"
      op           = "in"
      values       = ["bob"]
    }
    variation = 4
  }

  fallthrough {
    variation = 0
  }
}

resource "launchdarkly_feature_flag_environment" "show_identify_move_count_env" {
  flag_id = launchdarkly_feature_flag.show_identify_move_count.id
  env_key = var.environment_key

  on            = true
  off_variation = 1

  rules {
    description = "Alice"
    clauses {
      context_kind = "user"
      attribute    = "key"
      op           = "in"
      values       = ["alice"]
    }
    variation = 0
  }

  rules {
    description = "Bob"
    clauses {
      context_kind = "user"
      attribute    = "key"
      op           = "in"
      values       = ["bob"]
    }
    variation = 1
  }

  fallthrough {
    variation = 1
  }
}

output "flag_keys" {
  value = [
    launchdarkly_feature_flag.enable_identify_grid_highlight.key,
    launchdarkly_feature_flag.show_identify_move_count.key,
  ]
}
