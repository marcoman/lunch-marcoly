# LaunchDarkly capability: Terraform — segments and segment-targeted highlight flag
# See: https://launchdarkly.com/docs/home/flags/segments

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

locals {
  color_names = ["yellow", "red", "blue", "green", "purple"]
}

resource "launchdarkly_segment" "generic" {
  project_key = var.project_key
  env_key     = var.environment_key
  key         = "seg-by-name-generic"
  name        = "By name: generic"
  description = "Username is exactly generic"
  tags        = ["grid-navigator", "use-case", "segments-by-name"]

  rules {
    clauses {
      attribute = "segmentType"
      op        = "in"
      values    = ["generic"]
    }
  }
}

resource "launchdarkly_segment" "named_color" {
  for_each = toset(local.color_names)

  project_key = var.project_key
  env_key     = var.environment_key
  key         = "seg-by-name-color-${each.key}"
  name        = "By name: color ${each.key}"
  description = "Username is exactly the color name ${each.key}"
  tags        = ["grid-navigator", "use-case", "segments-by-name"]

  rules {
    clauses {
      attribute = "namedColor"
      op        = "in"
      values    = [each.key]
    }
  }
}

resource "launchdarkly_segment" "human" {
  project_key = var.project_key
  env_key     = var.environment_key
  key         = "seg-by-name-human"
  name        = "By name: human"
  description = "Even letter count, not generic or color name"
  tags        = ["grid-navigator", "use-case", "segments-by-name"]

  rules {
    clauses {
      attribute = "segmentType"
      op        = "in"
      values    = ["human"]
    }
  }
}

resource "launchdarkly_segment" "robot" {
  project_key = var.project_key
  env_key     = var.environment_key
  key         = "seg-by-name-robot"
  name        = "By name: robot"
  description = "Odd letter count, not generic or color name"
  tags        = ["grid-navigator", "use-case", "segments-by-name"]

  rules {
    clauses {
      attribute = "segmentType"
      op        = "in"
      values    = ["robot"]
    }
  }
}

resource "launchdarkly_segment" "human_beta" {
  project_key = var.project_key
  env_key     = var.environment_key
  key         = "seg-by-name-human-beta"
  name        = "By name: human + beta"
  description = "Even letter count with beta in username"
  tags        = ["grid-navigator", "use-case", "segments-by-name"]

  rules {
    clauses {
      attribute = "segmentType"
      op        = "in"
      values    = ["human-beta"]
    }
  }
}

resource "launchdarkly_segment" "robot_beta" {
  project_key = var.project_key
  env_key     = var.environment_key
  key         = "seg-by-name-robot-beta"
  name        = "By name: robot + beta"
  description = "Odd letter count with beta in username"
  tags        = ["grid-navigator", "use-case", "segments-by-name"]

  rules {
    clauses {
      attribute = "segmentType"
      op        = "in"
      values    = ["robot-beta"]
    }
  }
}

resource "launchdarkly_feature_flag" "configure_grid_selection_green_highlight" {
  project_key = var.project_key
  key         = "configure-grid-selection-green-highlight"
  name        = "Configure: grid selection green highlight"
  description = "Segments-by-name: string highlight color from segment targeting (none, yellow, red, blue, green, purple)."
  temporary   = false

  variation_type = "string"

  variations {
    value       = "none"
    name        = "No highlight"
    description = "X only — matches 00-reference"
  }

  variations {
    value       = "yellow"
    name        = "Yellow"
    description = "Yellow selection highlight"
  }

  variations {
    value       = "red"
    name        = "Red"
    description = "Red selection highlight"
  }

  variations {
    value       = "blue"
    name        = "Blue"
    description = "Blue selection highlight"
  }

  variations {
    value       = "green"
    name        = "Green"
    description = "Green selection highlight"
  }

  variations {
    value       = "purple"
    name        = "Purple"
    description = "Purple selection highlight"
  }

  defaults {
    on_variation  = 0
    off_variation = 0
  }

  tags = [
    "grid-navigator",
    "use-case",
    "segments-by-name",
    "configure",
    "string",
    "managed-by-terraform",
  ]
}

resource "launchdarkly_feature_flag_environment" "highlight_env" {
  flag_id = launchdarkly_feature_flag.configure_grid_selection_green_highlight.id
  env_key = var.environment_key

  on            = true
  off_variation = 0

  rules {
    description = "Generic — no highlight"
    clauses {
      attribute = "segmentMatch"
      op        = "segmentMatch"
      values    = [launchdarkly_segment.generic.key]
    }
    variation = 0
  }

  dynamic "rules" {
    for_each = {
      yellow = { segment = launchdarkly_segment.named_color["yellow"].key, variation = 1 }
      red    = { segment = launchdarkly_segment.named_color["red"].key, variation = 2 }
      blue   = { segment = launchdarkly_segment.named_color["blue"].key, variation = 3 }
      green  = { segment = launchdarkly_segment.named_color["green"].key, variation = 4 }
      purple = { segment = launchdarkly_segment.named_color["purple"].key, variation = 5 }
    }
    content {
      description = "Named color ${rules.key}"
      clauses {
        attribute = "segmentMatch"
        op        = "segmentMatch"
        values    = [rules.value.segment]
      }
      variation = rules.value.variation
    }
  }

  rules {
    description = "Human + beta"
    clauses {
      attribute = "segmentMatch"
      op        = "segmentMatch"
      values    = [launchdarkly_segment.human_beta.key]
    }
    variation = 4
  }

  rules {
    description = "Robot + beta"
    clauses {
      attribute = "segmentMatch"
      op        = "segmentMatch"
      values    = [launchdarkly_segment.robot_beta.key]
    }
    variation = 5
  }

  rules {
    description = "Human"
    clauses {
      attribute = "segmentMatch"
      op        = "segmentMatch"
      values    = [launchdarkly_segment.human.key]
    }
    variation = 1
  }

  rules {
    description = "Robot"
    clauses {
      attribute = "segmentMatch"
      op        = "segmentMatch"
      values    = [launchdarkly_segment.robot.key]
    }
    variation = 2
  }

  fallthrough {
    variation = 0
  }
}

output "flag_key" {
  value = launchdarkly_feature_flag.configure_grid_selection_green_highlight.key
}

output "segment_keys" {
  value = concat(
    [launchdarkly_segment.generic.key],
    [for c in local.color_names : launchdarkly_segment.named_color[c].key],
    [
      launchdarkly_segment.human.key,
      launchdarkly_segment.robot.key,
      launchdarkly_segment.human_beta.key,
      launchdarkly_segment.robot_beta.key,
    ],
  )
}
