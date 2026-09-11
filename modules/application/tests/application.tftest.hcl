mock_provider "aws" {
  override_during = plan

  mock_resource "aws_s3_bucket" {
    defaults = {
      id  = "harness-test-111111111111"
      arn = "arn:aws:s3:::harness-test-111111111111"
    }
  }

  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::111111111111:policy/harness-dev-read-objects" }
  }
}

variables {
  project     = "harness"
  environment = "dev"
  owner       = "platform"
  bucket_name = "harness-test-111111111111"
  extra_tags  = { ManagedBy = "untrusted-override" }
}

run "secure_bucket_and_least_privilege" {
  command = plan

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.this.block_public_acls,
      aws_s3_bucket_public_access_block.this.block_public_policy,
      aws_s3_bucket_public_access_block.this.ignore_public_acls,
      aws_s3_bucket_public_access_block.this.restrict_public_buckets,
      !aws_s3_bucket.this.force_destroy
    ])
    error_message = "Public access must be blocked and force_destroy disabled."
  }

  assert {
    condition     = one(aws_s3_bucket_versioning.this.versioning_configuration).status == "Enabled" && one(aws_s3_bucket_ownership_controls.this.rule).object_ownership == "BucketOwnerEnforced"
    error_message = "Versioning and bucket owner enforced ownership are required."
  }

  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    error_message = "SSE-S3 must be configured."
  }

  assert {
    condition     = jsondecode(aws_s3_bucket_policy.tls_only.policy).Statement[0].Effect == "Deny" && jsondecode(aws_s3_bucket_policy.tls_only.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "Non-TLS requests must be explicitly denied."
  }

  assert {
    condition = alltrue([
      for tags in [aws_s3_bucket.this.tags, aws_iam_policy.read_objects.tags] :
      tags.Project == "harness" && tags.Environment == "dev" && tags.Owner == "platform" && tags.ManagedBy == "Terraform"
    ])
    error_message = "All taggable application resources require governance tags."
  }

  assert {
    condition     = jsondecode(aws_iam_policy.read_objects.policy).Statement[1].Resource[0] == "arn:aws:s3:::harness-test-111111111111/*" && jsondecode(aws_iam_policy.read_objects.policy).Statement[1].Action[0] == "s3:GetObject"
    error_message = "Read policy must target only this bucket."
  }

  assert {
    condition     = output.bucket_name == var.bucket_name && output.bucket_arn == "arn:aws:s3:::harness-test-111111111111" && output.read_policy_arn == "arn:aws:iam::111111111111:policy/harness-dev-read-objects"
    error_message = "Output contract changed."
  }
}

run "reject_bad_bucket_name" {
  command = plan
  variables {
    bucket_name = "INVALID_BUCKET"
  }
  expect_failures = [var.bucket_name]
}

run "reject_unknown_environment" {
  command = plan
  variables {
    environment = "production-typo"
  }
  expect_failures = [var.environment]
}
