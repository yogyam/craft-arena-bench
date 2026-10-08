# A monthly spending line with alerts, and an automatic stop of the arena instance when actual spend crosses it.
# AWS has no hard cap; this is the closest thing. Budgets are evaluated a few times a day, so the stop can lag by hours.

variable "budget_usd" {
  description = "Monthly spending line for the whole account, in US dollars"
  type        = number
  default     = 30
}

variable "alert_email" {
  description = "Where the 80% and 100% alerts go"
  type        = string
}

resource "aws_budgets_budget" "monthly" {
  name         = "craft-arena-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# The role AWS Budgets assumes to stop the instance. It may stop EC2 instances and nothing else.
data "aws_iam_policy_document" "budgets_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "budget_stop" {
  name               = "craft-arena-budget-stop"
  assume_role_policy = data.aws_iam_policy_document.budgets_assume.json
}

data "aws_iam_policy_document" "budget_stop" {
  statement {
    actions   = ["ec2:StopInstances", "ec2:DescribeInstances", "ec2:DescribeInstanceStatus"]
    resources = ["*"]
  }
  statement {
    actions   = ["ssm:StartAutomationExecution", "ssm:GetAutomationExecution", "ssm:DescribeAutomationExecutions"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "budget_stop" {
  name   = "stop-ec2"
  role   = aws_iam_role.budget_stop.id
  policy = data.aws_iam_policy_document.budget_stop.json
}

resource "aws_budgets_budget_action" "stop_arena" {
  budget_name        = aws_budgets_budget.monthly.name
  action_type        = "RUN_SSM_DOCUMENTS"
  approval_model     = "AUTOMATIC"
  notification_type  = "ACTUAL"
  execution_role_arn = aws_iam_role.budget_stop.arn

  action_threshold {
    action_threshold_type  = "PERCENTAGE"
    action_threshold_value = 100
  }
  definition {
    ssm_action_definition {
      action_sub_type = "STOP_EC2_INSTANCES"
      instance_ids    = [aws_instance.arena.id]
      region          = var.region
    }
  }
  subscriber {
    address           = var.alert_email
    subscription_type = "EMAIL"
  }
}
