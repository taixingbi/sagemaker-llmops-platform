terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0"
    }
  }

  # Configure via: terraform init -backend-config=...
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sagemaker-finetuning-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
