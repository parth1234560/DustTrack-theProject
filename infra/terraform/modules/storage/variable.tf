
variable "name_prefix" {
  description = "Prefix used for DustTrack storage resources"
  type        = string
}

variable "photo_bucket_name" {
  type = string
}

variable "allowed_origins" {
  description = "Frontend origins allowed to upload to S3"
  type        = list(string)
}

variable "state_machine_arn" {
  description = "ARN of the photo processing Step Functions state machine"
  type        = string
}
