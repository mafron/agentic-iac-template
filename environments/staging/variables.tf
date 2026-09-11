variable "environment" {
  description = "Fixed environment identity; cannot be relabeled by tfvars."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "This root must remain staging."
  }
}

variable "project" {
  description = "Project identifier validated by the Golden Path modules."
  type        = string
  default     = "harness"
}

variable "owner" {
  description = "Responsible team."
  type        = string
  default     = "platform"
}

variable "aws_region" {
  description = "AWS region; this sample uses its a availability zone."
  type        = string
  default     = "ap-northeast-1"
}

variable "aws_account_id" {
  description = "Expected 12-digit account ID; guards against planning in the wrong account."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must contain exactly 12 digits."
  }
}

variable "vpc_cidr" {
  description = "Environment VPC CIDR; changing this is HIGH RISK."
  type        = string
  default     = "10.43.0.0/16"
}

variable "bucket_name" {
  description = "Globally unique application bucket name."
  type        = string
}
