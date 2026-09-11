mock_provider "aws" {
  override_during = plan

  mock_resource "aws_vpc" {
    defaults = { id = "vpc-0123456789abcdef0" }
  }

  mock_resource "aws_subnet" {
    defaults = { id = "subnet-0123456789abcdef0" }
  }

  mock_resource "aws_internet_gateway" {
    defaults = { id = "igw-0123456789abcdef0" }
  }

  mock_resource "aws_security_group" {
    defaults = { id = "sg-0123456789abcdef0" }
  }
}

variables {
  project           = "harness"
  environment       = "dev"
  owner             = "platform"
  availability_zone = "ap-northeast-1a"
  extra_tags        = { Owner = "untrusted-override" }
}

run "safe_defaults_and_contract" {
  command = plan

  assert {
    condition     = aws_vpc.this.cidr_block == "10.42.0.0/16" && output.private_subnet_cidr == "10.42.10.0/24"
    error_message = "The CIDR derivation contract changed."
  }

  assert {
    condition     = !aws_subnet.public.map_public_ip_on_launch && !aws_subnet.private.map_public_ip_on_launch
    error_message = "Public IP assignment must default to false."
  }

  assert {
    condition     = length(aws_security_group.application.ingress) == 0 && length(aws_security_group.application.egress) == 0
    error_message = "Default security group must deny ingress and egress."
  }

  assert {
    condition     = length(aws_route_table.private.route) == 0 && one(aws_route_table.public.route).cidr_block == "0.0.0.0/0"
    error_message = "Only the public route table may have an internet route."
  }

  assert {
    condition = alltrue([
      for tags in [aws_vpc.this.tags, aws_subnet.public.tags, aws_subnet.private.tags, aws_security_group.application.tags, aws_internet_gateway.this.tags, aws_route_table.public.tags, aws_route_table.private.tags] :
      tags.Project == "harness" && tags.Environment == "dev" && tags.Owner == "platform" && tags.ManagedBy == "Terraform"
    ])
    error_message = "Required tags must exist and cannot be replaced by extra_tags."
  }

  assert {
    condition     = output.vpc_id == "vpc-0123456789abcdef0" && output.security_group_id == "sg-0123456789abcdef0" && output.private_subnet_id == aws_subnet.private.id
    error_message = "Module outputs must reference the intended resources."
  }
}

run "reject_public_vpc_cidr" {
  command = plan
  variables {
    vpc_cidr = "8.8.0.0/16"
  }
  expect_failures = [var.vpc_cidr]
}

run "reject_empty_owner" {
  command = plan
  variables {
    owner = " "
  }
  expect_failures = [var.owner]
}
