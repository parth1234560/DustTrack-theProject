output "lambda_log_group_names" {
  value = {
    for name, group in aws_cloudwatch_log_group.lambda :
    name => group.name
  }
}

output "lambda_error_alarm_names" {
  value = {
    for name, alarm in aws_cloudwatch_metric_alarm.lambda_errors :
    name => alarm.alarm_name
  }
}

output "step_functions_alarm_name" {
  value = aws_cloudwatch_metric_alarm.step_functions_failed.alarm_name
}
