output "region" {
  description = "Region everything was created in."
  value       = var.region
}

output "alb_dns_name" {
  description = "Load balancer DNS name. This is the host a demo URL resolves to."
  value       = aws_lb.api.dns_name
}

output "api_base_url" {
  description = "Base URL for the pilot API."
  value       = "http://${aws_lb.api.dns_name}"
}

output "health_url" {
  description = "First verification check."
  value       = "http://${aws_lb.api.dns_name}/health"
}

output "cluster_name" {
  description = "ECS cluster name, used by demo.sh and the verification commands."
  value       = aws_ecs_cluster.poc.name
}

output "service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.api.name
}

output "log_group_name" {
  description = "CloudWatch log group for API logs and ECS Exec sessions."
  value       = aws_cloudwatch_log_group.api.name
}

output "target_group_arn" {
  description = "Target group behind the listener, used by the target health check."
  value       = aws_lb_target_group.api.arn
}

output "ecr_repository_url" {
  description = "Repository to push the image to."
  value       = aws_ecr_repository.api.repository_url
}

output "image_uri" {
  description = "Exact image reference the task definition runs."
  value       = local.image_uri
}

output "image_tag" {
  description = "Tag deployed. push-image.sh reads this value."
  value       = var.image_tag
}

output "cpu_architecture" {
  description = "Fargate architecture, so push-image.sh builds the matching platform."
  value       = var.cpu_architecture
}

output "container_port" {
  description = "Port the container listens on."
  value       = var.container_port
}

output "allowed_cidrs" {
  description = "Sources allowed to reach the load balancer on port 80."
  value       = local.allowed_cidrs
}

output "exec_agent_check" {
  description = "Verification check 3: the managed agent must print RUNNING."
  value       = "aws ecs describe-tasks --cluster ${aws_ecs_cluster.poc.name} --tasks $(aws ecs list-tasks --cluster ${aws_ecs_cluster.poc.name} --service-name ${aws_ecs_service.api.name} --query 'taskArns[0]' --output text) --query 'tasks[0].containers[0].managedAgents[0].lastStatus' --output text"
}
