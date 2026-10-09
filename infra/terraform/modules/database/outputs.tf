
output "inspections_table_name" {
  value = aws_dynamodb_table.inspections.name
}

output "segments_table_name" {
  value = aws_dynamodb_table.segments.name
}

output "cleaning_events_table_name" {
  value = aws_dynamodb_table.cleaning_events.name
}