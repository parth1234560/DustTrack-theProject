
variable "name_prefix" {
  description = "Prefix used for DustTrack API resources"
  type        = string
}

variable "cognito_issuer" {
  description = "Cognito User Pool issuer URL used to validate JWTs"
  type        = string
}

variable "cognito_audience" {
  description = "Cognito App Client ID accepted as the JWT audience"
  type        = string
}

variable "allowed_origins" {
  description = "Frontend origins allowed by API Gateway"
  type        = list(string)
}

variable "inspections_table_name" {
  type = string
}

variable "segments_table_name" {
  type = string
}

variable "cleaning_events_table_name" {
  type = string
}

variable "photo_bucket_name" {
  description = "Private S3 bucket used for inspection photo uploads"
  type        = string
}

variable "upload_url_expiry_seconds" {
  description = "Presigned S3 PUT URL expiry in seconds"
  type        = number
  default     = 900
}
