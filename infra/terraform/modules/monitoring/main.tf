resource "aws_cloudwatch_log_group" "lambda" {
  for_each = var.lambda_names

  name              = "/aws/lambda/${each.value}"
  retention_in_days = 14
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = var.lambda_names

  alarm_name          = "${each.value}-errors"
  alarm_description   = "Lambda function has reported one or more errors."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.value
  }
}

resource "aws_cloudwatch_metric_alarm" "step_functions_failed" {
  alarm_name          = "dusttrack-dev-step-functions-failed"
  alarm_description   = "A DustTrack Step Functions execution has failed."
  namespace           = "AWS/States"
  metric_name         = "ExecutionsFailed"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }
}

resource "aws_cloudwatch_metric_alarm" "api_4xx_errors" {
  alarm_name          = "dusttrack-dev-api-4xx-errors"
  alarm_description   = "API Gateway is returning client error responses."
  namespace           = "AWS/ApiGateway"
  metric_name         = "4xx"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = var.api_id
    Stage = var.api_stage_name
  }
}

resource "aws_cloudwatch_metric_alarm" "api_5xx_errors" {
  alarm_name          = "dusttrack-dev-api-5xx-errors"
  alarm_description   = "API Gateway is returning server error responses."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = var.api_id
    Stage = var.api_stage_name
  }
}

