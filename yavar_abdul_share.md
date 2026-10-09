Yavar's cognito info-->
aws_region = "ap-south-1"
cognito_app_client_id = "5ppg0e92dkbp6bbblsos3g312f"
cognito_issuer_url = "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_e7NPcfGE0"
cognito_user_pool_id = "ap-south-1_e7NPcfGE0"
environment = "dev"


api_base_url = "https://4e7bzdbb6g.execute-api.ap-south-1.amazonaws.com"

//Note-->
Method  Endpoint
POST /v1/inspections
GET /v1/inspections/{id}
GET /v1/worklist
GET  /v1/segments/{id}
POST /v1/segments/{id}/cleaned
GET   /v1/segments
api_lambda_function_name = "dusttrack-dev-api"

POST /v1/inspections upload contract-->
request:
{
  "segmentId": "SEG-001",
  "latitude": 28.61,
  "longitude": 77.20,
  "dustRating": 2,
  "fileType": "image/jpeg"
}

response:
{
  "inspectionId": "...",
  "status": "PENDING",
  "upload": {
    "url": "presigned-s3-put-url",
    "method": "PUT",
    "contentType": "image/jpeg",
    "expiresIn": 900
  }
}

After PUT upload to response.upload.url, S3 triggers Step Functions. Current workflow is MVP placeholder logic and marks the inspection COMPLETED.







Abdul's output required-->
aws_region = "ap-south-1"
cleaning_events_table_name = "dusttrack-dev-cleaning-events"
inspections_table_name = "dusttrack-dev-inspections"
photo_bucket_name = "dusttrack-dev-photos-parth-2026"
segments_table_name = "dusttrack-dev-segments"
