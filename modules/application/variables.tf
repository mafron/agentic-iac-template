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
  description = "Accountable team identifier."
  type        = string

  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "owner must not be empty."
  }
}

variable "bucket_name" {
  description = "Globally unique S3 name; a deliberately restricted naming subset."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "Use 3-63 lowercase alphanumeric/hyphen characters, starting with a letter and ending alphanumeric."
  }
}

variable "extra_tags" {
  description = "Optional tags; required governance tags take precedence."
  type        = map(string)
  default     = {}
}
