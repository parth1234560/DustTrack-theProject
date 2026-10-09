
data "aws_region" "current" {}

data "archive_file" "placeholder" {
  type        = "zip"
  source_file = "${path.module}/lambda/handler.py"
  output_path = "${path.module}/placeholder.zip"
}

resource "aws_iam_role" "lambda" {
  name = "${var.name_prefix}-api-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "placeholder" {
  function_name    = "${var.name_prefix}-api"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      INSPECTIONS_TABLE     = var.inspections_table_name
      SEGMENTS_TABLE        = var.segments_table_name
      CLEANING_EVENTS_TABLE = var.cleaning_events_table_name
      PHOTO_BUCKET          = var.photo_bucket_name
      UPLOAD_URL_EXPIRES    = tostring(var.upload_url_expiry_seconds)
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_iam_role_policy.dynamodb_access,
    aws_iam_role_policy.photo_upload_access
  ]

  tags = {
    Name = "${var.name_prefix}-api"
  }
}

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-http-api"
  protocol_type = "HTTP"


  cors_configuration {
    allow_origins = var.allowed_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
  }

  tags = {
    Name = "${var.name_prefix}-http-api"
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.placeholder.invoke_arn
  payload_format_version = "2.0"
}

locals {
  routes = toset([
    "POST /v1/inspections",
    "GET /v1/inspections/{id}",
    "GET /v1/worklist",
    "GET /v1/segments/{id}",
    "POST /v1/segments/{id}/cleaned",
    "GET /v1/segments"
  ])
}


resource "aws_apigatewayv2_route" "this" {
  for_each = local.routes

  api_id             = aws_apigatewayv2_api.this.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.placeholder.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}



resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.this.id
  name             = "${var.name_prefix}-cognito-jwt"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = var.cognito_issuer
    audience = [var.cognito_audience]
  }
}

resource "aws_iam_role_policy" "dynamodb_access" {
  name = "${var.name_prefix}-api-dynamodb-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Scan"
        ]
        Resource = [
          "arn:aws:dynamodb:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/${var.inspections_table_name}",
          "arn:aws:dynamodb:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/${var.segments_table_name}",
          "arn:aws:dynamodb:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/${var.cleaning_events_table_name}"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "photo_upload_access" {
  name = "${var.name_prefix}-api-photo-upload-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::${var.photo_bucket_name}/inspections/*"
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

