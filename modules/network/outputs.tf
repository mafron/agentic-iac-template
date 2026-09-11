output "vpc_id" {
  description = "VPC identifier for approved downstream modules."
  value       = aws_vpc.this.id
}

output "public_subnet_id" {
  description = "Public-route subnet; public IP assignment remains disabled."
  value       = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "Isolated private subnet identifier."
  value       = aws_subnet.private.id
}

output "security_group_id" {
  description = "Application security group with no allowed traffic by default."
  value       = aws_security_group.application.id
}

output "private_subnet_cidr" {
  description = "Deterministically derived private subnet CIDR."
  value       = aws_subnet.private.cidr_block
}

output "required_tags" {
  description = "Effective governance tags."
  value       = local.tags
}
