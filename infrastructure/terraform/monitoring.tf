resource "aws_sns_topic" "budget_alerts" {
  count = var.budget_notification_email != "" ? 1 : 0
  name  = "${local.name_prefix}-budget-alerts"
}

resource "aws_sns_topic_subscription" "budget_email" {
  count     = var.budget_notification_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.budget_alerts[0].arn
  protocol  = "email"
  endpoint  = var.budget_notification_email
}

# Budgets API requires at least one subscriber — only create when email is set.
resource "aws_budgets_budget" "monthly" {
  count = var.budget_notification_email != "" ? 1 : 0

  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_notification_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts[0].arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_notification_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts[0].arn]
  }
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/aws/sagemaker/pipelines/${local.name_prefix}"
  retention_in_days = 30
}
