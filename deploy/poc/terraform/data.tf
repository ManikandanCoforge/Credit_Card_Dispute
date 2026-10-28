data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

# Default VPC and its default subnets. Both are skipped when the pilot creates
# its own VPC (create_vpc = true) or is handed explicit IDs.
data "aws_vpc" "default" {
  count   = var.create_vpc || var.vpc_id != null ? 0 : 1
  default = true
}

data "aws_subnets" "default" {
  count = var.create_vpc || var.subnet_ids != null ? 0 : 1

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
