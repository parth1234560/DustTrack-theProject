
variable "aws_region" {
  description = "AWS region for DustTrack"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}
variable "photo_bucket_name" {
  type        = string
  description = "Globally unique name for private inspection photos"
}

variable "allowed_origins" {
  type        = list(string)
  description = "Frontend origins allowed by API Gateway and S3 CORS"
  default     = ["http://localhost:3000"]
}
