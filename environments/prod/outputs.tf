output "vpc_id" {
  description = "Network VPC identifier."
  value       = module.network.vpc_id
}

output "private_subnet_id" {
  description = "Isolated subnet for future approved application modules."
  value       = module.network.private_subnet_id
}

output "bucket_name" {
  description = "Application bucket name."
  value       = module.application.bucket_name
}

output "environment" {
  description = "Fixed environment identity used for review."
  value       = var.environment
}
