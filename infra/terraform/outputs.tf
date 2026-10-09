output "environment" {
  description = "Active deployment environment"
  value       = var.environment
}

output "aws_region" {
  description = "AWS deployment region"
  value       = var.aws_region
}

output "photo_bucket_name" {
  value = module.storage.photo_bucket_name
}

output "inspections_table_name" {
  value = module.database.inspections_table_name
}

output "segments_table_name" {
  value = module.database.segments_table_name
}

output "cleaning_events_table_name" {
  value = module.database.cleaning_events_table_name
}

output "cognito_user_pool_id" {
  description = "DustTrack Cognito user pool ID"
  value       = module.identity.user_pool_id
}

output "cognito_app_client_id" {
  description = "DustTrack Cognito app client ID"
  value       = module.identity.app_client_id
}

output "cognito_issuer_url" {
  description = "DustTrack Cognito token issuer URL"
  value       = module.identity.issuer_url
}

output "api_base_url" {
  description = "DustTrack API Gateway base URL"
  value       = module.api.api_url
}

output "api_lambda_function_name" {
  description = "DustTrack shared placeholder Lambda"
  value       = module.api.lambda_function_name
}

output "state_machine_arn" {
  description = "DustTrack photo processing state machine ARN"
  value       = module.workflow.state_machine_arn
}