resource "aws_lb" "api" {
  name               = "${var.name}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = local.subnet_ids
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = 60

  enable_deletion_protection = false

  lifecycle {
    precondition {
      condition     = length(local.subnet_ids) >= 2
      error_message = "The load balancer needs at least two subnets. Pass subnet_ids, or create a default VPC in this region."
    }
  }
}

resource "aws_lb_target_group" "api" {
  name                 = "${var.name}-tg"
  port                 = var.container_port
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = local.vpc_id
  deregistration_delay = 15

  health_check {
    enabled             = true
    path                = var.health_check_path
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
