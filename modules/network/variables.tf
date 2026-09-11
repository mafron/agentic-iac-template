variable "project" {
  description = "Short project identifier used in names and required tags."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.project))
    error_message = "project must be 3-20 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "owner" {
  description = "Accountable team identifier; do not put personal secrets here."
  type        = string

  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "owner must not be empty."
  }
}

variable "vpc_cidr" {
  description = "A canonical 10.x.0.0/16 CIDR; intentionally narrow sample contract."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && can(regex("^10\\.[0-9]{1,3}\\.0\\.0/16$", var.vpc_cidr))
    error_message = "Use an IPv4 CIDR in canonical 10.x.0.0/16 form."
  }
}

variable "availability_zone" {
  description = "Explicit AZ; supplied by the environment without an AWS lookup."
  type        = string
}

variable "extra_tags" {
  description = "Optional tags; required governance tags take precedence."
  type        = map(string)
  default     = {}
}
