# GitHub Actions OIDC provider + CI role (pipeline upsert/start + artifact access).
# If the account already has the GitHub OIDC provider (e.g. from bedrock-lambda),
# set manage_github_oidc_provider = false and use the data source.

resource "aws_iam_openid_connect_provider" "github" {
  count = var.manage_github_oidc_provider ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.manage_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

# Least-privilege local identity: IAM user → sts:AssumeRole → github_actions role.
# (Account root cannot call AssumeRole — AWS rejects it.)
resource "aws_iam_user" "operator" {
  count = var.allow_local_sts_assume && var.create_local_operator_user ? 1 : 0
  name  = "${local.name_prefix}-operator"
  path  = "/llmops/"
  tags  = { Purpose = "local-sts-assume-role" }
}

resource "aws_iam_access_key" "operator" {
  count = var.allow_local_sts_assume && var.create_local_operator_user ? 1 : 0
  user  = aws_iam_user.operator[0].name
}

locals {
  github_oidc_provider_arn = var.manage_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
  sts_assume_principals = concat(
    var.local_assume_principals,
    var.allow_local_sts_assume && var.create_local_operator_user ? [aws_iam_user.operator[0].arn] : [],
  )
}

data "aws_iam_policy_document" "gha_assume" {
  # GitHub Actions → OIDC web identity
  statement {
    sid     = "GitHubOIDC"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_org}/${var.github_repo}:*",
      ]
    }
  }

  # Local / CLI → classic STS AssumeRole (same permissions as GHA)
  dynamic "statement" {
    for_each = var.allow_local_sts_assume && length(local.sts_assume_principals) > 0 ? [1] : []
    content {
      sid     = "LocalSTSAssumeRole"
      actions = ["sts:AssumeRole"]
      principals {
        type        = "AWS"
        identifiers = local.sts_assume_principals
      }
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.name_prefix}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.gha_assume.json
}

data "aws_iam_policy_document" "operator_assume_only" {
  count = var.allow_local_sts_assume && var.create_local_operator_user ? 1 : 0
  statement {
    sid       = "AssumePlatformRole"
    actions   = ["sts:AssumeRole"]
    resources = [aws_iam_role.github_actions.arn]
  }
}

resource "aws_iam_user_policy" "operator_assume_only" {
  count  = var.allow_local_sts_assume && var.create_local_operator_user ? 1 : 0
  name   = "${local.name_prefix}-operator-assume"
  user   = aws_iam_user.operator[0].name
  policy = data.aws_iam_policy_document.operator_assume_only[0].json
}

data "aws_iam_policy_document" "github_actions" {
  statement {
    sid = "SageMakerPipeline"
    actions = [
      "sagemaker:CreatePipeline",
      "sagemaker:UpdatePipeline",
      "sagemaker:DescribePipeline",
      "sagemaker:ListPipelines",
      "sagemaker:StartPipelineExecution",
      "sagemaker:DescribePipelineExecution",
      "sagemaker:ListPipelineExecutions",
      "sagemaker:StopPipelineExecution",
      "sagemaker:CreateModelPackageGroup",
      "sagemaker:DescribeModelPackageGroup",
      "sagemaker:ListModelPackageGroups",
      "sagemaker:DescribeModelPackage",
      "sagemaker:ListModelPackages",
      "sagemaker:AddTags",
      "sagemaker:ListTags",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "PassSageMakerRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.sagemaker_execution.arn]
  }

  statement {
    sid = "S3ReadWriteArtifacts"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]
  }

  statement {
    sid = "ECRPush"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:DescribeRepositories",
    ]
    resources = ["*"]
  }

  statement {
    sid = "AccountRead"
    actions = [
      "sts:GetCallerIdentity",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:GetRolePolicy",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "${local.name_prefix}-github-actions"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions.json
}
