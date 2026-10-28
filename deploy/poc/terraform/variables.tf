variable "region" {
  description = "AWS region. us-east-1 keeps the prices quoted in the executive brief."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Resource name prefix. Keep it short: the ALB and target group names must stay under 32 characters."
  type        = string
  default     = "ccd-poc"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,21}$", var.name))
    error_message = "name must be 3 to 22 characters, lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "owner" {
  description = "Owner tag used for cost attribution and the teardown sweep."
  type        = string
  default     = "Coforge FDE Pod"
}

variable "cpu_architecture" {
  description = "Fargate CPU architecture. Must match the platform used by push-image.sh (X86_64 means linux/amd64)."
  type        = string
  default     = "X86_64"

  validation {
    condition     = contains(["X86_64", "ARM64"], var.cpu_architecture)
    error_message = "cpu_architecture must be X86_64 or ARM64."
  }
}

variable "task_cpu" {
  description = "Fargate task CPU units. 512 is 0.5 vCPU, the value the cost model assumes."
  type        = string
  default     = "512"
}

variable "task_memory" {
  description = "Fargate task memory in MiB. 1024 pairs with 512 CPU."
  type        = string
  default     = "1024"
}

variable "container_port" {
  description = "Port the container listens on. serve.py defaults to 8000."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "Target group health check path. GET /health returns 200 with the dataset name."
  type        = string
  default     = "/health"
}

variable "image_tag" {
  description = "Image tag deployed from ECR. push-image.sh reads the same value."
  type        = string
  default     = "poc"
}

variable "desired_count" {
  description = "Task count. One is enough for the pilot and it is what the cost model assumes."
  type        = number
  default     = 1
}

variable "exec_session_logging" {
  description = "Read by phases.sh, not Terraform: log every ECS Exec operator session to CloudWatch with one update-cluster call. Set TF_VAR_exec_session_logging=false to skip it."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch retention for API logs and ECS Exec session logs."
  type        = number
  default     = 7
}

variable "allowed_cidrs" {
  description = "CIDRs allowed to reach the load balancer on port 80. Leave null to detect this workstation's public IP and allow only that /32."
  type        = list(string)
  default     = null
}

variable "vpc_id" {
  description = "VPC to deploy into. Null uses the account's default VPC."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "At least two subnets for the load balancer. Null uses the default VPC's default subnets."
  type        = list(string)
  default     = null
}

variable "create_vpc" {
  description = "Create a dedicated VPC for the pilot instead of using the account's default VPC. Adds no billable resources, and stops the pilot sharing subnets with other teams."
  type        = bool
  default     = false
}

variable "vpc_cidr" {
  description = "CIDR for the dedicated VPC, only used when create_vpc is true. Must be a /24 or larger, for example 10.42.0.0/16."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 24
    error_message = "vpc_cidr must be a valid CIDR with a prefix of /24 or larger, for example 10.42.0.0/16."
  }
}
