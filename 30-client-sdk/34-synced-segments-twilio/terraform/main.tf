# Terraform: client-side badge flag targeted at a Twilio-synced segment.
# https://launchdarkly.com/docs/guides/infrastructure/terraform
# https://launchdarkly.com/docs/home/flags/twilio

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

variable "synced_segment_key" {
  type        = string
  default     = "marcoly-twilio-inner-circle"
  description = "Key of the segment Twilio created via LaunchDarkly Audiences (copy from the Segments page)."
}

resource "launchdarkly_feature_flag" "show_twilio_inner_circle_badge" {
  project_key    = var.project_key
  key            = "show-twilio-inner-circle-badge"
  name           = "Show: Twilio inner circle badge"
  description    = "True when the context is in the Twilio Segment-synced inner-circle audience."
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
    "twilio",
    "show",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "show_twilio_inner_circle_badge_env" {
  flag_id = launchdarkly_feature_flag.show_twilio_inner_circle_badge.id
  env_key = var.environment_key

  on            = true
  off_variation = 1

  rules {
    description = "Twilio inner circle"
    clauses {
      context_kind = "user"
      op           = "segmentMatch"
      values       = [var.synced_segment_key]
    }
    variation = 0
  }

  fallthrough {
    variation = 1
  }
}

output "flag_key" {
  value = launchdarkly_feature_flag.show_twilio_inner_circle_badge.key
}

output "synced_segment_key" {
  value = var.synced_segment_key
}
