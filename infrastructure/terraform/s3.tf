data "aws_caller_identity" "current" {}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  name_prefix      = "${var.project_name}-${var.environment}"
  artifacts_bucket = "${var.project_name}-artifacts-${var.environment}-${local.account_id}"
}

resource "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket

  tags = {
    Name = local.artifacts_bucket
  }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-temp-processing"
    status = "Enabled"

    filter {
      prefix = "tmp/"
    }

    expiration {
      days = 14
    }
  }
}
