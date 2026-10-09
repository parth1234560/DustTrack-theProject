
output "api_url" {
  description = "Base URL for the DustTrack HTTP API"
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "lambda_function_name" {
  description = "Shared placeholder Lambda function name"
  value       = aws_lambda_function.placeholder.function_name
}

output "api_id" {
  description = "API Gateway HTTP API ID"
  value       = aws_apigatewayv2_api.this.id
}

output "stage_name" {
  description = "API Gateway stage name"
  value       = aws_apigatewayv2_stage.default.name
}
