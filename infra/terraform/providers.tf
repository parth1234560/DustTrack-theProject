
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "DustTrack"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
