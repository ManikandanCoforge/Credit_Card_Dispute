# Optional: a VPC of this pilot's own, so nothing shares the account's
# default VPC with another team. Off by default: `create_vpc = true` adds one
# VPC, two public subnets across two availability zones, an internet gateway and
# a route table. No NAT gateway, so the cost stays at the pilot's $0.056 an hour.
#
# Why this exists: the default VPC is a shared resource. Other people's load
# balancers and tasks sit in the same subnets, and someone else deleting the
# default VPC deletes your demo with it. A dedicated VPC removes that coupling
# without adding a single billable line item.

data "aws_availability_zones" "available" {
  count = var.create_vpc ? 1 : 0
  state = "available"
}

resource "aws_vpc" "poc" {
  count = var.create_vpc ? 1 : 0

  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name}-vpc"
  }
}

resource "aws_subnet" "public" {
  count = var.create_vpc ? 2 : 0

  vpc_id                  = aws_vpc.poc[0].id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available[0].names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.name}-public-${count.index + 1}"
    Tier = "public"
  }
}

resource "aws_internet_gateway" "poc" {
  count = var.create_vpc ? 1 : 0

  vpc_id = aws_vpc.poc[0].id

  tags = {
    Name = "${var.name}-igw"
  }
}

resource "aws_route_table" "public" {
  count = var.create_vpc ? 1 : 0

  vpc_id = aws_vpc.poc[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.poc[0].id
  }

  tags = {
    Name = "${var.name}-public"
  }
}

resource "aws_route_table_association" "public" {
  count = var.create_vpc ? 2 : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}
