# Two security groups, two rules. The task accepts port 8000 from the load
# balancer only, and the load balancer accepts port 80 from one address.
resource "aws_security_group" "alb" {
  name        = "${var.name}-alb-sg"
  description = "Pilot ALB ingress"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.name}-alb-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  for_each = toset(local.allowed_cidrs)

  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the allowlist"
  cidr_ipv4         = each.value
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_all" {
  security_group_id = aws_security_group.alb.id
  description       = "ALB to task"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "task" {
  name        = "${var.name}-task-sg"
  description = "Pilot task ingress from the ALB only"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.name}-task-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "task_from_alb" {
  security_group_id            = aws_security_group.task.id
  description                  = "Container port from the ALB security group"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = var.container_port
  to_port                      = var.container_port
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "task_all" {
  security_group_id = aws_security_group.task.id
  description       = "ECR pull and CloudWatch, no inbound requirement"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
