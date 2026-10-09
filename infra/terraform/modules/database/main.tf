
resource "aws_dynamodb_table" "inspections" {
  name         = "${var.name_prefix}-inspections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "inspectionId"

  attribute {
    name = "inspectionId"
    type = "S"
  }
}

resource "aws_dynamodb_table" "segments" {
  name         = "${var.name_prefix}-segments"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "segmentId"

  attribute {
    name = "segmentId"
    type = "S"
  }
}

resource "aws_dynamodb_table" "cleaning_events" {
  name         = "${var.name_prefix}-cleaning-events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "eventId"

  attribute {
    name = "eventId"
    type = "S"
  }
}