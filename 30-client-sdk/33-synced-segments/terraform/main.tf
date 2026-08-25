# Terraform: inner-circle segment + client-side badge flag.
# https://launchdarkly.com/docs/guides/infrastructure/terraform
# https://launchdarkly.com/docs/home/flags/synced-segments

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
  sensitive   = true
  description = "LaunchDarkly API access token (set LD_ACCESS_TOKEN)"
}

variable "api_host" {
  type    = string
  default = "https://app.launchdarkly.com"
}

variable "project_key" {
  type = string
}

variable "environment_key" {
  type = string
}

variable "unbounded_segment" {
  type        = bool
  default     = true
  description = "true = big/synced-style segment. Set false if the project cannot create unbounded segments."
}

resource "launchdarkly_segment" "inner_circle" {
  project_key = var.project_key
  env_key     = var.environment_key
  key         = "marcoly-inner-circle"
  name        = "Marcoly inner circle"
  description = "Inner-circle membership. Lab injects keys via REST; production would sync from Twilio Segment Audiences."
  tags        = ["grid-navigator", "client-sdk", "synced-segments"]

  unbounded              = var.unbounded_segment
  unbounded_context_kind = "user"
}

resource "launchdarkly_feature_flag" "show_inner_circle_badge" {
  project_key    = var.project_key
  key            = "show-inner-circle-badge"
  name           = "Show: inner circle badge"
  description    = "True when the context is in marcoly-inner-circle."
  temporary      = false
  variation_type = "boolean"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = false
  }

  variations {
    value       = true
    name        = "Badge on"
    description = "Show inner-circle badge"
  }
  variations {
    value       = false
    name        = "Badge off"
    description = "No badge"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "client-sdk",
    "segments",
    "synced-segments",
    "show",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "show_inner_circle_badge_env" {
  flag_id = launchdarkly_feature_flag.show_inner_circle_badge.id
  env_key = var.environment_key

  on            = true
  off_variation = 1

  rules {
    description = "Inner circle"
    clauses {
      context_kind = "user"
      op           = "segmentMatch"
      values       = [launchdarkly_segment.inner_circle.key]
    }
    variation = 0
  }

  fallthrough {
    variation = 1
  }
}

output "flag_key" {
  value = launchdarkly_feature_flag.show_inner_circle_badge.key
}

output "segment_key" {
  value = launchdarkly_segment.inner_circle.key
}
