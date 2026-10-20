output "artifacts_bucket" {
  description = "S3 bucket for data, models, and evaluation artifacts"
  value       = aws_s3_bucket.artifacts.bucket
}

output "sagemaker_execution_role_arn" {
  description = "IAM role ARN passed to SageMaker jobs and pipeline"
  value       = aws_iam_role.sagemaker_execution.arn
}

output "github_actions_role_arn" {
  description = "Set this as GitHub Actions variable AWS_ROLE_ARN; also used by local sts:AssumeRole"
  value       = aws_iam_role.github_actions.arn
}

output "operator_user_name" {
  description = "IAM user for local STS AssumeRole (not root)"
  value       = try(aws_iam_user.operator[0].name, null)
}

output "operator_access_key_id" {
  description = "Access key for operator user — configure AWS profile llmops-base"
  value       = try(aws_iam_access_key.operator[0].id, null)
}

output "operator_secret_access_key" {
  description = "Secret for operator user (sensitive — store in ~/.aws/credentials, never commit)"
  value       = try(aws_iam_access_key.operator[0].secret, null)
  sensitive   = true
}

output "ecr_training_repository_url" {
  description = "ECR repo for custom training images (optional; DLC used by default)"
  value       = aws_ecr_repository.training.repository_url
}

output "pipeline_name" {
  description = "Conventional SageMaker pipeline name for this environment"
  value       = "${var.project_name}-${var.environment}"
}

output "model_package_group" {
  description = "Model Registry package group name"
  value       = "${var.project_name}-${var.environment}"
}

output "aws_region" {
  value = var.aws_region
}

output "environment" {
  value = var.environment
}
