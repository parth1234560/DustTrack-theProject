
resource "aws_s3_bucket" "photos" {
  bucket = var.photo_bucket_name

  tags = {
    Name = "DustTrack inspection photos"
  }
}

resource "aws_s3_bucket_public_access_block" "photos" {
  bucket = aws_s3_bucket.photos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "photos" {
  bucket = aws_s3_bucket.photos.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


resource "aws_s3_bucket_cors_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id

  cors_rule {
    allowed_methods = ["PUT"]
    allowed_origins = var.allowed_origins
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
resource "aws_s3_bucket_notification" "photos" {
  bucket      = aws_s3_bucket.photos.id
  eventbridge = true
}


resource "aws_cloudwatch_event_rule" "photo_created" {
  name        = "${var.name_prefix}-photo-created"
  description = "Trigger processing when a photo is uploaded to S3"

  event_pattern = jsonencode({
    source        = ["aws.s3"]
    "detail-type" = ["Object Created"]

    detail = {
      bucket = {
        name = [aws_s3_bucket.photos.bucket]
      }
    }
  })
}

resource "aws_iam_role" "eventbridge_step_functions" {
  name = "${var.name_prefix}-eventbridge-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_start_execution" {
  name = "${var.name_prefix}-start-step-functions"
  role = aws_iam_role.eventbridge_step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["states:StartExecution"]
      Resource = var.state_machine_arn
    }]
  })
}

resource "aws_cloudwatch_event_target" "photo_processing" {
  rule     = aws_cloudwatch_event_rule.photo_created.name
  arn      = var.state_machine_arn
  role_arn = aws_iam_role.eventbridge_step_functions.arn

  depends_on = [
    aws_iam_role_policy.eventbridge_start_execution
  ]
}

