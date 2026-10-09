output "state_machine_arn" {
  description = "ARN of the photo processing state machine"
  value       = aws_sfn_state_machine.photo_processing.arn
}

output "lambda_function_names" {
  description = "Workflow Lambda function names"
  value       = toset([for fn in values(aws_lambda_function.placeholder) : fn.function_name])
}
