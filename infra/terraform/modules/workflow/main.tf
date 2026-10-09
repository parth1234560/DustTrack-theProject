
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    filename = "lambda_function.py"
    content  = <<-PYTHON
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
inspections = dynamodb.Table(os.environ["INSPECTIONS_TABLE"])

def handler(event, context):
    step = os.environ.get("STEP_NAME", "Unknown")
    now = datetime.now(timezone.utc).isoformat()

    detail = event.get("detail", {})
    encoded_key = detail.get("object", {}).get("key", "")
    photo_key = urllib.parse.unquote_plus(encoded_key)
    inspection_id = None

    parts = photo_key.split("/")
    if len(parts) >= 3 and parts[0] == "inspections":
        inspection_id = parts[1]

    if step == "validate_input":
        if not inspection_id:
            raise ValueError("Could not derive inspection ID from S3 object key")

        inspections.update_item(
            Key={"inspectionId": inspection_id},
            UpdateExpression="SET #status = :status, processingStartedAt = :now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "PROCESSING",
                ":now": now,
            },
        )

        return {
            "step": step,
            "status": "ok",
            "inspectionId": inspection_id,
            "photoKey": photo_key,
        }

    inspection_id = event.get("validation", {}).get("inspectionId", inspection_id)

    if step == "publish_work_list":
        if not inspection_id:
            raise ValueError("Missing inspection ID for publish step")

        inspections.update_item(
            Key={"inspectionId": inspection_id},
            UpdateExpression="SET #status = :status, completedAt = :now, workflowResult = :result",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "COMPLETED",
                ":now": now,
                ":result": "MVP workflow completed. Replace placeholder AI/weather/scoring handlers with Abdul's final logic.",
            },
        )

        return {
            "step": step,
            "status": "ok",
            "inspectionId": inspection_id,
            "message": "Inspection marked COMPLETED",
        }

    return {
        "step": step,
        "status": "ok",
        "inspectionId": inspection_id,
        "message": f"{step} completed with MVP placeholder logic"
    }
PYTHON
  }
}

resource "aws_iam_role" "step_functions" {
  name = "${var.name_prefix}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role" "lambda" {
  name = "${var.name_prefix}-workflow-lambda-role"

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

locals {
  workflow_steps = toset([
    "validate_input",
    "analyse_image",
    "fetch_weather",
    "update_cadence",
    "score_segment",
    "publish_work_list"
  ])

  transient_lambda_errors = [
    "Lambda.ServiceException",
    "Lambda.AWSLambdaException",
    "Lambda.SdkClientException",
    "Lambda.TooManyRequestsException"
  ]

  task_error_handling = {
    Retry = [{
      ErrorEquals     = local.transient_lambda_errors
      IntervalSeconds = 2
      MaxAttempts     = 3
      BackoffRate     = 2
    }]

    Catch = [{
      ErrorEquals = ["States.ALL"]
      ResultPath  = "$.workflow_error"
      Next        = "WorkflowFailed"
    }]
  }
}

resource "aws_lambda_function" "placeholder" {
  for_each = local.workflow_steps

  function_name = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.12"

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  environment {
    variables = {
      STEP_NAME         = each.key
      INSPECTIONS_TABLE = var.inspections_table_name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_iam_role_policy.lambda_dynamodb_access
  ]
}

resource "aws_iam_role_policy" "lambda_dynamodb_access" {
  name = "${var.name_prefix}-workflow-dynamodb-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = "arn:aws:dynamodb:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/${var.inspections_table_name}"
      }
    ]
  })
}

resource "aws_iam_role_policy" "step_functions_invoke_lambdas" {
  name = "${var.name_prefix}-sfn-invoke-lambdas"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["lambda:InvokeFunction"]
      Resource = [
        for fn in values(aws_lambda_function.placeholder) : fn.arn
      ]
    }]
  })
}

resource "aws_sfn_state_machine" "photo_processing" {
  name     = "${var.name_prefix}-photo-processing"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "DustTrack photo processing workflow"
    StartAt = "ValidateInput"

    States = {
      ValidateInput = merge({
        Type       = "Task"
        Resource   = aws_lambda_function.placeholder["validate_input"].arn
        ResultPath = "$.validation"
        Next       = "AnalyseImageAndFetchWeather"
      }, local.task_error_handling)




      AnalyseImageAndFetchWeather = merge({
        Type = "Parallel"

        Branches = [
          {
            StartAt = "AnalyseImage"
            States = {
              AnalyseImage = {
                Type       = "Task"
                Resource   = aws_lambda_function.placeholder["analyse_image"].arn
                ResultPath = "$"

                Retry = [{
                  ErrorEquals     = local.transient_lambda_errors
                  IntervalSeconds = 2
                  MaxAttempts     = 3
                  BackoffRate     = 2
                }]

                Catch = [{
                  ErrorEquals = ["States.ALL"]
                  ResultPath  = "$.branch_error"
                  Next        = "ImageBranchFailed"
                }]

                Next = "ImageBranchSucceeded"
              }

              ImageBranchSucceeded = {
                Type = "Pass"
                End  = true
              }

              ImageBranchFailed = {
                Type  = "Fail"
                Error = "ImageAnalysisFailed"
                Cause = "The image analysis branch failed."
              }
            }
          },
          {
            StartAt = "FetchWeather"
            States = {
              FetchWeather = {
                Type       = "Task"
                Resource   = aws_lambda_function.placeholder["fetch_weather"].arn
                ResultPath = "$"

                Retry = [{
                  ErrorEquals     = local.transient_lambda_errors
                  IntervalSeconds = 2
                  MaxAttempts     = 3
                  BackoffRate     = 2
                }]

                Catch = [{
                  ErrorEquals = ["States.ALL"]
                  ResultPath  = "$.branch_error"
                  Next        = "WeatherBranchFailed"
                }]

                Next = "WeatherBranchSucceeded"
              }

              WeatherBranchSucceeded = {
                Type = "Pass"
                End  = true
              }

              WeatherBranchFailed = {
                Type  = "Fail"
                Error = "WeatherFetchFailed"
                Cause = "The weather fetch branch failed."
              }
            }
          }
        ]

        ResultPath = "$.parallel_results"
        Next       = "UpdateCadence"
      }, local.task_error_handling)

      UpdateCadence = merge({
        Type       = "Task"
        Resource   = aws_lambda_function.placeholder["update_cadence"].arn
        ResultPath = "$.cadence"
        Next       = "ScoreSegment"
      }, local.task_error_handling)

      ScoreSegment = merge({
        Type       = "Task"
        Resource   = aws_lambda_function.placeholder["score_segment"].arn
        ResultPath = "$.segment_score"
        Next       = "PublishWorkList"
      }, local.task_error_handling)

      PublishWorkList = merge({
        Type       = "Task"
        Resource   = aws_lambda_function.placeholder["publish_work_list"].arn
        ResultPath = "$.work_list"
        End        = true
      }, local.task_error_handling)

      WorkflowFailed = {
        Type  = "Fail"
        Error = "DustTrackWorkflowFailed"
        Cause = "A workflow task failed after retries"
      }
    }
  })

  depends_on = [
    aws_iam_role_policy.step_functions_invoke_lambdas
  ]
}
