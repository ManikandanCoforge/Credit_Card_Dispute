resource "aws_ecs_cluster" "poc" {
  name = var.name

  # Container Insights is off on purpose: the pilot needs logs, not metrics at
  # 0.5 vCPU. CloudWatch alarms in the runbook cover the failure modes that matter.
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = "main"
      image     = local.image_uri
      essential = true

      portMappings = [
        {
          name          = "http"
          containerPort = var.container_port
          protocol      = "tcp"
          appProtocol   = "http"
        },
      ]

      environment = [
        { name = "BANK_DATA_DIR", value = "/app/data/dev" },
        { name = "BANK_STATE", value = "/app/.state/mock.sqlite" },
        { name = "BANK_PORT", value = tostring(var.container_port) },
      ]

      # Required by ECS Exec: without an init process the SSM agent is not
      # reaped and the channel never opens.
      linuxParameters = { initProcessEnabled = true }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
          "mode"                  = "non-blocking"
        }
      }
    },
  ])

  lifecycle {
    precondition {
      condition     = contains(lookup(local.fargate_sizes, var.task_cpu, []), var.task_memory)
      error_message = "task_memory ${var.task_memory} is not valid for task_cpu ${var.task_cpu}. Valid memory values: ${join(", ", lookup(local.fargate_sizes, var.task_cpu, ["unknown CPU"]))}."
    }
  }
}

resource "aws_ecs_service" "api" {
  name            = "${var.name}-api"
  cluster         = aws_ecs_cluster.poc.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 90

  # The operator gate: this is what lets "demo.sh exec" run the approval inside
  # the same process tree as the API.
  enable_execute_command = true

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = local.subnet_ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true # no NAT gateway in the pilot
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "main"
    container_port   = var.container_port
  }

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy.exec_channel,
    aws_iam_role_policy_attachment.execution_managed,
  ]
}

# Session logging for ECS Exec is not exposed by the AWS provider 6.70 in any
# resource: aws_ecs_service has no execute_command_configuration block, and
# aws_ecs_cluster does not model configuration either. The setting lives on the
# cluster and is applied by the one AWS CLI call in phases.sh (service phase).
# Terraform owns enable_execute_command above; that call owns the logging
# destination, so a rejected apply never leaves a half-written resource behind.
