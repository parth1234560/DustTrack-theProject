variable "lambda_names" {
  description = "Lambda function names monitored by CloudWatch"
  type        = set(string)
}

variable "state_machine_arn" {
  description = "DustTrack Step Functions state machine ARN"
  type        = string
}

variable "api_id" {
  description = "API Gateway HTTP API ID"
  type        = string
}

variable "api_stage_name" {
  description = "API Gateway stage name"
  type        = string
}
