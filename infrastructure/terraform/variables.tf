variable "aws_region" {
  type        = string
  description = "AWS region for all resources"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment name (dev|prod)"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "project_name" {
  type        = string
  description = "Short project prefix for resource names"
  default     = "llm-finetune"
}

variable "github_org" {
  type        = string
  description = "GitHub org or user for OIDC trust"
  default     = "taixingbi"
}

variable "github_repo" {
  type        = string
  description = "GitHub repository name (without org)"
  default     = "sagemaker-finetuning-platform"
}

variable "budget_limit_usd" {
  type        = number
  description = "Monthly AWS Budget alert threshold (notification only)"
  default     = 150
}

variable "budget_notification_email" {
  type        = string
  description = "Email for Budget alerts (empty skips Budget resource; required for alerts)"
  default     = ""
}

variable "manage_github_oidc_provider" {
  type        = bool
  description = "Create the GitHub OIDC provider. Set false if the account already has token.actions.githubusercontent.com"
  default     = true
}
