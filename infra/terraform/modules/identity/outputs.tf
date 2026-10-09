
output "user_pool_id" {
  description = "Cognito user pool ID"
  value       = aws_cognito_user_pool.this.id
}

output "app_client_id" {
  description = "Cognito app client ID"
  value       = aws_cognito_user_pool_client.this.id
}

output "issuer_url" {
  description = "Cognito token issuer URL"
  value       = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}
