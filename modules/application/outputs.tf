output "bucket_name" {
  description = "Application bucket name."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_arn" {
  description = "Application bucket ARN."
  value       = aws_s3_bucket.this.arn
}

output "read_policy_arn" {
  description = "Unattached, bucket-scoped read policy ARN."
  value       = aws_iam_policy.read_objects.arn
}

output "required_tags" {
  description = "Effective governance tags."
  value       = local.tags
}
