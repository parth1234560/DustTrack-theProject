
variable "name_prefix" {
  description = "Prefix for workflow resources"
  type        = string
}

variable "inspections_table_name" {
  description = "DynamoDB table storing inspection records"
  type        = string
}
