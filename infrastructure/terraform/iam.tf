# SageMaker execution role — used by Pipeline / Training / Processing / Model
data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker_execution" {
  name               = "${local.name_prefix}-sagemaker-execution"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
}

data "aws_iam_policy_document" "sagemaker_execution" {
  statement {
    sid = "S3Artifacts"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]
  }

  statement {
    sid = "ECRPull"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = ["*"]
  }

  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/sagemaker/*"]
  }

  statement {
    sid = "SageMakerJobs"
    actions = [
      "sagemaker:CreateTrainingJob",
      "sagemaker:DescribeTrainingJob",
      "sagemaker:StopTrainingJob",
      "sagemaker:CreateProcessingJob",
      "sagemaker:DescribeProcessingJob",
      "sagemaker:StopProcessingJob",
      "sagemaker:CreateModel",
      "sagemaker:CreateModelPackage",
      "sagemaker:DescribeModelPackage",
      "sagemaker:CreateModelPackageGroup",
      "sagemaker:DescribeModelPackageGroup",
      "sagemaker:UpdateModelPackage",
      "sagemaker:ListModelPackages",
      "sagemaker:AddTags",
      "sagemaker:ListTags",
      "sagemaker:CreateExperiment",
      "sagemaker:CreateTrial",
      "sagemaker:CreateTrialComponent",
      "sagemaker:AssociateTrialComponent",
      "sagemaker:DescribeExperiment",
      "sagemaker:DescribeTrial",
      "sagemaker:DescribeTrialComponent",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "PassOwnRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.sagemaker_execution.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["sagemaker.amazonaws.com"]
    }
  }

  # Hugging Face / PyTorch DLC images live in public SageMaker account repos
  statement {
    sid = "Marketplace"
    actions = [
      "aws-marketplace:ViewSubscriptions",
      "aws-marketplace:Subscribe",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sagemaker_execution" {
  name   = "${local.name_prefix}-sagemaker-execution"
  role   = aws_iam_role.sagemaker_execution.id
  policy = data.aws_iam_policy_document.sagemaker_execution.json
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_managed" {
  # Broad managed policy for Pipeline orchestration edge cases; tighten later.
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}
