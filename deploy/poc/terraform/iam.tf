data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Execution role: pull the image from ECR and write to CloudWatch Logs.
resource "aws_iam_role" "execution" {
  name               = "${var.name}-exec"
  description        = "Pilot ECS task execution role: ECR pull and CloudWatch Logs"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task role: only the four SSM channel actions ECS Exec needs. No S3, no
# DynamoDB, no Secrets Manager, because the pilot has none of those.
resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  description        = "Pilot ECS task role: ECS Exec channel only"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "exec_channel" {
  statement {
    sid = "EcsExecChannel"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "exec_channel" {
  name   = "ecs-exec-channel"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.exec_channel.json
}
