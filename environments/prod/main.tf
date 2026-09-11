provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
}

module "network" {
  source = "../../modules/network"

  project           = var.project
  environment       = var.environment
  owner             = var.owner
  vpc_cidr          = var.vpc_cidr
  availability_zone = "${var.aws_region}a"
}

module "application" {
  source = "../../modules/application"

  project     = var.project
  environment = var.environment
  owner       = var.owner
  bucket_name = var.bucket_name
}
