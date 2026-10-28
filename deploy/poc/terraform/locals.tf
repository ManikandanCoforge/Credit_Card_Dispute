locals {
  # Precedence: a VPC created here beats explicit IDs, which beat the default
  # VPC. Only the selected branch is evaluated, so count = 0 blocks stay inert.
  vpc_id = var.create_vpc ? aws_vpc.poc[0].id : (
    var.vpc_id != null ? var.vpc_id : data.aws_vpc.default[0].id
  )

  subnet_ids = var.create_vpc ? aws_subnet.public[*].id : (
    var.subnet_ids != null ? var.subnet_ids : data.aws_subnets.default[0].ids
  )

  allowed_cidrs = var.allowed_cidrs != null ? var.allowed_cidrs : [
    "${chomp(data.http.workstation_ip[0].response_body)}/32",
  ]

  image_uri = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

  # Valid Fargate CPU and memory pairs. Anything else fails at plan time with a
  # message that names the valid options, instead of a 20 minute service stall.
  fargate_sizes = {
    "256"  = ["512", "1024", "2048"]
    "512"  = ["1024", "2048", "3072", "4096"]
    "1024" = ["2048", "3072", "4096", "5120", "6144", "7168", "8192"]
    "2048" = ["4096", "5120", "6144", "7168", "8192", "9216", "10240", "11264", "12288", "13312", "14336", "15360", "16384"]
  }
}
