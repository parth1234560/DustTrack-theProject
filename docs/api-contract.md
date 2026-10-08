# DustTrack API Contract

**Status:** Proposed for team sign-off  
**Owners:** Abdul (backend), Yavar (frontend), Parth (AWS infrastructure)  
**Last updated:** 2026-10-09

This document defines the API and data format shared by the DustTrack frontend and backend. We will use it as the reference for implementation and integration. Any changes to routes or JSON fields should be agreed in a pull request before either side updates its code.

## Conventions

| Item | Agreement |
| --- | --- |
| API | Amazon API Gateway HTTP API |
| Base path | `/v1` (custom domain or API Gateway URL configured by environment) |
| Content type | `application/json` for API calls |
| Field names | `camelCase` |
| Authentication | Cognito JWT in `Authorization: Bearer <token>` |
| Date/time | ISO 8601 UTC, e.g. `2026-10-09T10:30:00Z` |
| IDs | Strings (`ROAD-001`, `INS-101`) |
| Dust rating | Integer `0`–`3` |
| Priority score | Number `0`–`1` |
| GPS | WGS84 decimal degrees: `latitude`, `longitude` |
| GeoJSON | Coordinates ordered `[longitude, latitude]` |

All six endpoints require authentication. Inspectors can create and view their permitted inspections; supervisors can access ward worklists and record cleaning. API authorization must be enforced by the backend, not just hidden in the UI. User IDs come from validated JWT claims, not request bodies.

## Routes

| Method | Route | Purpose | Main owner |
| --- | --- | --- | --- |
| `POST` | `/v1/inspections` | Create an inspection and get an S3 upload URL | Abdul |
| `GET` | `/v1/inspections/{id}` | Check inspection status and results | Abdul |
| `GET` | `/v1/worklist?ward=WARD-05` | Get roads ranked by cleaning priority | Abdul |
| `GET` | `/v1/segments/{id}` | Get a road and its current status | Abdul |
| `POST` | `/v1/segments/{id}/cleaned` | Record completed cleaning | Abdul |
| `GET` | `/v1/segments?ward=WARD-05` | Get road geometry for the map | Abdul |

### 1. Create inspection

`POST /v1/inspections`

Request:

```json
{
  "segmentId": "ROAD-001",
  "latitude": 28.61,
  "longitude": 77.20,
  "dustRating": 3,
  "fileType": "image/jpeg"
}
```

Response — `201 Created`:

```json
{
  "inspectionId": "INS-101",
  "status": "PENDING",
  "upload": {
    "url": "https://example-presigned-s3-url",
    "method": "PUT",
    "contentType": "image/jpeg"
  }
}
```

The backend creates the inspection record with `PENDING` status and generates a short-lived presigned URL for a unique S3 object key. A `201` response **does not** mean the image has been uploaded or processed. The client must upload the file separately. The API does not accept image bytes.

### 2. Get inspection

`GET /v1/inspections/INS-101`

Response — `200 OK`:

```json
{
  "inspectionId": "INS-101",
  "segmentId": "ROAD-001",
  "status": "COMPLETED",
  "inspectorDustRating": 3,
  "aiAnalysis": {
    "dustRating": 2,
    "debrisDetected": true
  },
  "imageUrl": "https://example-presigned-download-url",
  "inspectedAt": "2026-10-09T10:30:00Z"
}
```

While processing, `status` may be `PENDING` or `PROCESSING`; `aiAnalysis` and `imageUrl` may be `null` until available. `imageUrl` must be a short-lived authorized URL, never a public S3 object URL. If AI analysis fails but the inspection can still be scored, `aiAnalysis` may be `null` even when `status` is `COMPLETED`.

### 3. Get prioritized worklist

`GET /v1/worklist?ward=WARD-05`

Response — `200 OK`:

```json
{
  "wardId": "WARD-05",
  "items": [
    {
      "segmentId": "ROAD-001",
      "roadName": "MG Road",
      "priorityScore": 0.92,
      "priorityLevel": "HIGH",
      "dustRating": 3,
      "lastCleanedAt": "2026-10-04T08:00:00Z"
    }
  ],
  "nextCursor": null
}
```

Results are ordered by `priorityScore` descending. `nextCursor` is `null` when there are no more results; a non-null cursor can be passed as `?cursor=...` for the next page. The backend defines and documents the priority-level thresholds.

### 4. Get road segment

`GET /v1/segments/ROAD-001`

Response — `200 OK`:

```json
{
  "segmentId": "ROAD-001",
  "roadName": "MG Road",
  "wardId": "WARD-05",
  "geometry": {
    "type": "LineString",
    "coordinates": [[77.20, 28.61], [77.21, 28.62]]
  },
  "cleaningCadenceDays": 5,
  "priorityScore": 0.92,
  "lastCleanedAt": "2026-10-04T08:00:00Z"
}
```

The road geometry is GeoJSON. Note the `[longitude, latitude]` coordinate order.

### 5. Record cleaning

`POST /v1/segments/ROAD-001/cleaned`

Request:

```json
{
  "cleanedAt": "2026-10-09T12:00:00Z",
  "squadId": "TEAM-02",
  "method": "MECHANICAL",
  "remarks": "Road cleaning completed"
}
```

Response — `201 Created`:

```json
{
  "cleaningEventId": "CLEAN-101",
  "segmentId": "ROAD-001",
  "status": "RECORDED"
}
```

The backend writes a CleaningEvents record and updates the segment's last-cleaned time. This endpoint is restricted to authorized supervisors. `method` is one of `MANUAL` or `MECHANICAL` for the MVP. The caller's identity is taken from the JWT.

### 6. List road segments

`GET /v1/segments?ward=WARD-05`

Response — `200 OK`:

```json
{
  "wardId": "WARD-05",
  "items": [
    {
      "segmentId": "ROAD-001",
      "roadName": "MG Road",
      "geometry": {
        "type": "LineString",
        "coordinates": [[77.20, 28.61], [77.21, 28.62]]
      },
      "priorityScore": 0.92,
      "priorityLevel": "HIGH"
    }
  ],
  "nextCursor": null
}
```

Yavar uses the geometry with Leaflet/OpenStreetMap to draw and color roads. Pagination follows the same `nextCursor` convention as the worklist.

## Photo upload: frontend to S3

We upload photos directly from the browser to S3. The photo is **not** sent as part of the `POST /inspections` JSON request.

1. Inspector selects or takes a photo in the Next.js app. The browser requests GPS permission and captures coordinates.
2. Yavar calls `POST /v1/inspections` with road ID, GPS, inspector dust rating and MIME type.
3. Abdul's API Lambda creates the `PENDING` record in DynamoDB and returns `upload.url`.
4. Yavar sends the actual file with HTTP `PUT` to that URL, using the exact signed content type and headers.
5. S3 object creation is routed through EventBridge to Step Functions.
6. The workflow validates the uploaded object, calls Bedrock and weather services, calculates the road score, and updates DynamoDB.
7. The frontend calls `GET /v1/inspections/{id}` until the status is final.

Frontend example:

```typescript
const response = await fetch(`${apiBaseUrl}/v1/inspections`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`
  },
  body: JSON.stringify({
    segmentId,
    latitude,
    longitude,
    dustRating,
    fileType: selectedImageFile.type
  })
});

if (!response.ok) throw new Error("Could not create inspection");
const { inspectionId, upload } = await response.json();

const uploadResponse = await fetch(upload.url, {
  method: upload.method,
  headers: { "Content-Type": upload.contentType },
  body: selectedImageFile
});
if (!uploadResponse.ok) throw new Error("Photo upload failed");
```

Parth configures private S3 access, upload permissions, event routing and S3 CORS for the frontend origin. The upload URL should expire quickly and allow upload only to the generated object key. Validation after upload must check the real object size/type; the `fileType` supplied by the browser is not trusted. Uploaded images remain private.

## Processing and data storage

| DynamoDB table | Primary key | Stores |
| --- | --- | --- |
| `Inspections` | `inspectionId` | Inspector observations, GPS, S3 key, image hash, AI result, status, timestamps |
| `Segments` | `segmentId` | Road geometry, ward, cleaning cadence, last-cleaned date, latest priority |
| `CleaningEvents` | `cleaningEventId` | Cleaning date, road, squad, method, recorder |

Indexes are needed for inspections by segment/date, cleaning events by segment/date, segments by ward/priority, and exact-image duplicate lookup. For reliable duplicate prevention under concurrent uploads, a conditional-write uniqueness record is required; a hash query alone is not sufficient.

The Step Functions workflow is:

`ValidateInput → [AnalyseImage + FetchWeather in parallel] → UpdateCadence → ScoreSegment → PublishWorkList`

- **ValidateInput:** Check the uploaded S3 object, GPS proximity to the selected road geometry and exact duplicate hash.
- **AnalyseImage:** Ask Bedrock for dust/debris assessment; inspector rating remains authoritative.
- **FetchWeather:** Get relevant weather information from Open-Meteo.
- **UpdateCadence:** Adjust the road's estimated cleaning interval using its history.
- **ScoreSegment:** Calculate the priority score.
- **PublishWorkList:** Save inspection outcome and segment priority to DynamoDB.

Statuses: `PENDING` → `PROCESSING` → `COMPLETED`, `REJECTED` or `FAILED`. Invalid submissions become `REJECTED`; unexpected processing failures become `FAILED`. A Bedrock outage should not block scoring from the inspector's rating. GPS is a plausibility check, not proof of physical presence.

## Error responses

Use the same shape for errors from every API:

```json
{
  "error": {
    "code": "INVALID_GPS",
    "message": "Inspection location is too far from the selected road"
  }
}
```

| HTTP status | Meaning |
| --- | --- |
| `200` | Successful read |
| `201` | Record created |
| `400` | Invalid input |
| `401` | Missing or invalid token |
| `403` | User not allowed to perform action |
| `404` | Inspection or segment not found |
| `409` | Duplicate or conflicting operation |
| `500` | Unexpected server error |

The frontend must handle network failures, expired upload URLs, pending inspections, and failed processing. Never display a `PENDING` inspection as completed.

## Ownership and integration

| Person | Responsibility |
| --- | --- |
| **Parth** | Terraform, API Gateway routes and JWT authorizer, IAM, private S3/CORS, DynamoDB resources, EventBridge, Step Functions, CI/CD, logs and deployment |
| **Abdul** | API request/response validation, Python Lambda handlers, presigned URLs, DynamoDB reads/writes, scoring and workflow logic |
| **Yavar** | Next.js inspector/supervisor UI, Cognito login, JWT on API calls, direct S3 upload, polling, Leaflet map and API error handling |
| **Swastik** | Bedrock prompt/evaluation, sample photos, weather/AI testing and QA; confirm ownership with the team |

**Integration order:** (1) agree on contracts, (2) Parth deploys Terraform foundation while Abdul builds handlers and Yavar builds UI with mock JSON, (3) connect the create-inspection/upload flow, (4) connect Step Functions and scoring, (5) connect supervisor worklist and cleaning updates, (6) run end-to-end tests.

## Sign-off before implementation

- [ ] Abdul confirms all six routes and JSON fields.
- [ ] Yavar confirms all six routes support the inspector and supervisor screens.
- [ ] Parth confirms IAM, Cognito roles, S3 upload, CORS and API Gateway configuration.
- [ ] Team confirms DynamoDB keys/indexes, pagination and processing statuses.
- [ ] Team agrees on priority-level thresholds, GPS tolerance, photo limits and upload URL expiry.
- [ ] Team confirms delivery dates and updates this document if anything changes.

**Approvals:** Abdul — pending · Yavar — pending · Parth — pending
