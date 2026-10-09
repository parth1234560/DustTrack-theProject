
# DustTrack

DustTrack helps inspectors upload road dust observations and helps supervisors see which road segments need cleaning first.

This repo currently contains the AWS infrastructure, API contract, backend placeholder handlers, and integration handoff notes for the hackathon MVP.

## Current Dev Environment

```text
AWS region: ap-south-1
API base URL: https://4e7bzdbb6g.execute-api.ap-south-1.amazonaws.com
Cognito user pool ID: ap-south-1_e7NPcfGE0
Cognito app client ID: 5ppg0e92dkbp6bbblsos3g312f
Photo bucket: dusttrack-dev-photos-parth-2026
Inspections table: dusttrack-dev-inspections
Segments table: dusttrack-dev-segments
Cleaning events table: dusttrack-dev-cleaning-events
Step Functions: dusttrack-dev-photo-processing
```

All application routes require:

```text
Authorization: Bearer <Cognito IdToken>
Content-Type: application/json
```

## Routes

```text
GET  /v1/segments
GET  /v1/segments/{id}
GET  /v1/worklist
POST /v1/inspections
GET  /v1/inspections/{id}
POST /v1/segments/{id}/cleaned
```

## Photo Upload Flow

The frontend does not send image bytes to the API.

1. Call `POST /v1/inspections`.
2. API creates a `PENDING` inspection.
3. API returns a presigned S3 upload URL.
4. Frontend uploads the image with `PUT`.
5. S3 triggers EventBridge.
6. EventBridge starts Step Functions.
7. MVP workflow marks the inspection `PROCESSING`, then `COMPLETED`.

Example request:

```json
{
  "segmentId": "SEG-001",
  "latitude": 28.61,
  "longitude": 77.2,
  "dustRating": 2,
  "fileType": "image/jpeg"
}
```

Example response:

```json
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
```

Then upload:

```ts
await fetch(upload.url, {
  method: upload.method,
  headers: { "Content-Type": upload.contentType },
  body: selectedImageFile
});
```

## For Yavar

Use these frontend env values:

```text
NEXT_PUBLIC_AWS_REGION=ap-south-1
NEXT_PUBLIC_API_BASE_URL=https://4e7bzdbb6g.execute-api.ap-south-1.amazonaws.com
NEXT_PUBLIC_COGNITO_USER_POOL_ID=ap-south-1_e7NPcfGE0
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=5ppg0e92dkbp6bbblsos3g312f
```

Useful test data:

```text
segmentId: SEG-001
```

Important frontend behavior:

- Use the Cognito IdToken in `Authorization`.
- Upload photos directly to the returned S3 URL.
- Poll `GET /v1/inspections/{id}` until status is final.
- Treat `PENDING` and `PROCESSING` as not done yet.

## For Abdul

Current API Lambda:

```text
dusttrack-dev-api
```

Current workflow Lambda names:

```text
dusttrack-dev-validate-input
dusttrack-dev-analyse-image
dusttrack-dev-fetch-weather
dusttrack-dev-update-cadence
dusttrack-dev-score-segment
dusttrack-dev-publish-work-list
```

Current workflow is intentionally MVP placeholder logic. It proves the upload pipeline works, but real validation, Bedrock/weather, scoring, duplicate detection, GPS checks, and segment priority updates still need your handlers.

Expected S3 object key format:

```text
inspections/{inspectionId}/photo.{jpg|png|webp}
```

## Verified

Parth verified the MVP pipeline end to end:

```text
API create inspection -> presigned upload -> S3 object -> EventBridge -> Step Functions -> DynamoDB COMPLETED
```

Latest test inspection:

```text
c9c33bba-e1be-400a-b0e2-d271407cbec4
```

Terraform drift check:

```text
No changes. Infrastructure matches configuration.
```

## Still To Do

- Replace workflow placeholder logic with Abdul's real processing handlers.
- Add real segment priority scoring updates.
- Confirm final frontend origin and CORS.
- Run Yavar's full frontend-to-dashboard demo.
- Keep real passwords, JWTs, AWS keys, and test credentials out of git.

## More Detail

- API contract: `docs/api-contract.md`
- Infra handoff: `docs/integration/infrastructure_handoff.md`
- Terraform root: `infra/terraform`
