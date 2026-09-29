# Policy fixture — do not terraform apply.
# Omitting sunset is valid LaunchDarkly config. Sentinel is what rejects it.
# Custom properties — https://launchdarkly.com/docs/home/infrastructure/custom-properties

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
  description = "LaunchDarkly API host"
  default     = "https://app.launchdarkly.com"
}

variable "project_key" {
  type        = string
  description = "LaunchDarkly project key"
}

resource "launchdarkly_feature_flag" "enable_sentinel_sunset" {
  project_key    = var.project_key
  key            = "enable-sentinel-sunset"
  name           = "Enable: sentinel sunset demo"
  description    = "19-terraform-sentinel fail fixture. Boolean flag with no sunset custom property."
  variation_type = "boolean"
  temporary      = true

  variations {
    value = true
    name  = "On"
  }

  variations {
    value = false
    name  = "Off"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = ["managed-by-terraform", "sentinel-demo"]
}
