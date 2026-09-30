# LaunchDarkly capability: Terraform — one boolean flag, Android-only targeting rule
# https://launchdarkly.com/docs/guides/infrastructure/terraform
# Keywords: targeting rules, platform, using_mobile_key
#
# This file encodes state 1 (platform in [android] serves true).
# rest/advance-rollout.sh adds ios. A later terraform apply puts the rule
# back to android only.

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

resource "launchdarkly_feature_flag" "enable_mobile_platform_rollout" {
  project_key = var.project_key
  key         = "enable-mobile-platform-rollout"
  name        = "Enable: mobile platform rollout"
  description = "Boolean release flag. True is the new experience. Targeting starts with platform android."
  temporary   = true

  variation_type = "boolean"

  client_side_availability {
    using_environment_id = true
    using_mobile_key     = true
  }

  variations {
    value       = true
    name        = "New release"
    description = "Green cell and Release: on"
  }

  variations {
    value       = false
    name        = "Previous"
    description = "Plain X and Release: waiting"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = [
    "grid-navigator",
    "mobile-sdk",
    "platform-rollout",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "enable_mobile_platform_rollout_env" {
  flag_id = launchdarkly_feature_flag.enable_mobile_platform_rollout.id
  env_key = var.environment_key

  on            = true
  off_variation = 1

  rules {
    description = "Android first"
    clauses {
      context_kind = "user"
      attribute    = "platform"
      op           = "in"
      values       = ["android"]
    }
    variation = 0
  }

  fallthrough {
    variation = 1
  }
}

output "flag_key" {
  value = launchdarkly_feature_flag.enable_mobile_platform_rollout.key
}
