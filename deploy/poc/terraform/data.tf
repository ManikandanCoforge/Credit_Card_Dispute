data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

# Default VPC and its default subnets: nothing in this pilot invents networking.
data "aws_vpc" "default" {
  count   = var.vpc_id == null ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = var.subnet_ids == null ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# Only fetched when allowed_cidrs is left null. One address, not the world.
data "http" "workstation_ip" {
  count = var.allowed_cidrs == null ? 1 : 0
  url   = "https://checkip.amazonaws.com"
}
