# LaunchDarkly: string flag with targeting rules on a public context attribute.
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
  description = "LaunchDarkly API access token"
  sensitive   = true
}

variable "api_host" {
  type        = string
  default     = "https://app.launchdarkly.com"
  description = "LaunchDarkly API host"
}

variable "project_key" {
  type        = string
  description = "LaunchDarkly project key"
}

variable "environment_key" {
  type        = string
  description = "Environment receiving the targeting rules"
}

resource "launchdarkly_feature_flag" "team_label_style" {
  project_key = var.project_key
  key         = "configure-team-label-style"
  name        = "Configure: team label style"
  description = "String style selected by targeting rules on the public team context attribute."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "plain"
    name        = "Plain"
    description = "No explicit team-label color"
  }
  variations {
    value       = "colored-red"
    name        = "Colored red"
    description = "Red team-label text"
  }
  variations {
    value       = "colored-blue"
    name        = "Colored blue"
    description = "Blue team-label text"
  }
  variations {
    value       = "colored-yellow"
    name        = "Colored yellow"
    description = "Yellow team-label text"
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
    "targeting-rules",
    "context-attributes",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "team_label_style" {
  flag_id = launchdarkly_feature_flag.team_label_style.id
  env_key = var.environment_key

  on            = true
  off_variation = 0

  rules {
    description = "Team Red"
    clauses {
      context_kind = "user"
      attribute    = "team"
      op           = "in"
      values       = ["red"]
    }
    variation = 1
  }

  rules {
    description = "Team Blue"
    clauses {
      context_kind = "user"
      attribute    = "team"
      op           = "in"
      values       = ["blue"]
    }
    variation = 2
  }

  rules {
    description = "Team Yellow"
    clauses {
      context_kind = "user"
      attribute    = "team"
      op           = "in"
      values       = ["yellow"]
    }
    variation = 3
  }

  fallthrough {
    variation = 0
  }
}

output "flag_key" {
  value = launchdarkly_feature_flag.team_label_style.key
}
