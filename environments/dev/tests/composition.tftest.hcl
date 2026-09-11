mock_provider "aws" {
  override_during = plan

  mock_resource "aws_vpc" {
    defaults = { id = "vpc-0123456789abcdef0" }
  }

  mock_resource "aws_s3_bucket" {
    defaults = {
      id  = "harness-dev-111111111111"
      arn = "arn:aws:s3:::harness-dev-111111111111"
    }
  }
}

variables {
  aws_account_id = "111111111111"
  bucket_name    = "harness-dev-111111111111"
}

run "composition_contract" {
  command = plan

  assert {
    condition     = output.environment == "dev" && module.network.required_tags.Environment == "dev" && module.application.required_tags.Environment == "dev"
    error_message = "Environment identity must be consistent across modules."
  }

  assert {
    condition     = output.vpc_id == "vpc-0123456789abcdef0" && output.bucket_name == var.bucket_name
    error_message = "Root outputs must expose the Golden Path outputs."
  }
}

run "reject_environment_relabel" {
  command = plan
  variables {
    environment = "prod"
  }
  expect_failures = [var.environment]
}
