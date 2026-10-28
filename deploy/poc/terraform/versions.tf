terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}

provider "aws" {
  region = var.region

  # Every taggable resource inherits these, so cost and ownership survive a
  # forgotten resource. "Lifetime = ephemeral" is the teardown reminder.
  default_tags {
    tags = {
      Project     = "credit-card-dispute"
      Component   = "${var.name}-pilot"
      Environment = "poc"
      ManagedBy   = "terraform"
      Owner       = var.owner
      Lifetime    = "ephemeral"
    }
  }
}
