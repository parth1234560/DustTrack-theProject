# DustTrack — Infrastructure Handoff

**Environment:** dev
**AWS Region:** `ap-south-1`
**Purpose:** Shared infrastructure and integration contract for backend and frontend development.

## 1. Existing Infrastructure

| Resource                     | Identifier                                                |
| ---------------------------- | --------------------------------------------------------- |
| Photo bucket                 | `dusttrack-dev-photos-parth-2026`                         |
| Inspections table            | `dusttrack-dev-inspections`                               |
| Segments table               | `dusttrack-dev-segments`                                  |
| Cleaning events table        | `dusttrack-dev-cleaning-events`                           |
| API Lambda                   | `dusttrack-dev-api`                                       |
| Step Functions state machine | `dusttrack-dev-photo-processing`                          |
| API base URL                 | `https://4e7bzdbb6g.execute-api.ap-south-1.amazonaws.com` |
| Cognito user pool ID         | `ap-south-1_e7NPcfGE0`                                    |
| Cognito app client ID        | `5ppg0e92dkbp6bbblsos3g312f`                              |

## 2. Current API Routes

All configured application routes use Cognito JWT authorization.

* `GET /v1/segments` — list road segments.
* `GET /v1/segments/{id}` — retrieve a segment.
* `POST /v1/segments/{id}/cleaned` — mark a segment as cleaned and record a cleaning event.
* `GET /v1/worklist` — retrieve segments requiring cleaning.
* `POST /v1/inspections` — create an inspection.
* `GET /v1/inspections/{id}` — retrieve an inspection.

## 3. Abdul — Backend Integration

Please update this document or the linked GitHub issue with:

* Actual workflow Lambda function names.
* Environment variable **names** required by each handler.
* Expected S3 object key and input event structure.
* Step Functions input/output contract.
* Validation, AI/weather/scoring integration status.
* The logic that updates inspection status to `COMPLETED` or an appropriate failure state.
* How segment priority and cleaning events are updated.
* Any IAM permissions required by the handlers.

**Current known behavior:** Creating an inspection stores a `PENDING` record and returns a presigned S3 `PUT` upload URL. Uploading to that object key triggers EventBridge and Step Functions. The current workflow is still MVP placeholder logic, but it updates the inspection to `PROCESSING` and then `COMPLETED` so the upload pipeline can be tested before Abdul replaces the processing handlers.

## 4. Yavar — Frontend Integration

* API base URL: `https://4e7bzdbb6g.execute-api.ap-south-1.amazonaws.com`
* Region: `ap-south-1`
* Cognito user pool ID: `ap-south-1_e7NPcfGE0`
* Cognito app client ID: `5ppg0e92dkbp6bbblsos3g312f`
* JWT authorization: `Authorization: Bearer <IdToken>`
* Routes: see Section 2.
* Frontend origin: **TODO — agree on the exact development origin and configure CORS accordingly.**
* Upload method: call `POST /v1/inspections`, then upload the selected image bytes with HTTP `PUT` to `response.upload.url` using the exact `response.upload.contentType`.

Please document the frontend environment variable names in a `.env.example` file. Use placeholders only; never commit real credentials or tokens.

## 5. Upload and Processing Contract — To Be Confirmed

The intended flow is:

1. Frontend authenticates with Cognito.
2. Frontend selects a road segment and obtains GPS coordinates with user permission.
3. Frontend requests permission to upload a photo.
4. Photo is uploaded to the private S3 bucket.
5. An inspection record is created with status `PENDING`.
6. Step Functions processes the photo.
7. Validation and scoring results are stored.
8. Inspection status and segment priority are updated.
9. Supervisor reviews the ranked worklist.
10. Cleaning completion creates a record in the cleaning events table.

Do not treat this full flow as complete until it has been demonstrated end to end.

## 6. Verification Checklist

* [x] Cognito JWT authentication works.
* [x] Segment listing works.
* [x] Inspection creation works.
* [x] Inspection retrieval works.
* [x] Marking a segment as cleaned works.
* [x] Cleaned segment disappears from the worklist.
* [x] Presigned upload flow implemented and tested.
* [x] S3 upload triggers the MVP workflow.
* [ ] Real workflow handlers integrated.
* [x] Inspection reaches a final status.
* [ ] Segment priority updates from processing results.
* [ ] Frontend-to-dashboard demo verified.
* [ ] Monitoring and failure handling verified.

Latest MVP upload test: inspection `c9c33bba-e1be-400a-b0e2-d271407cbec4` uploaded object `inspections/c9c33bba-e1be-400a-b0e2-d271407cbec4/photo.jpg`; Step Functions execution succeeded; DynamoDB inspection status became `COMPLETED`.

## 7. Security

Never commit passwords, JWTs, AWS credentials, private keys, or secret values. Keep actual secrets in approved secret storage and share only the identifiers and configuration names teammates need.
