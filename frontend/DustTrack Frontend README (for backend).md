# DustTrack frontend: README for the backend team

By Yavar (frontend). Last updated 10 Oct 2026.

This explains what the frontend sends to the API, what it expects back, and what must be configured on the AWS side before it works end to end.

## What it is

A single file, `dusttrack-live.html`, with no build step and no dependencies. It has two views:

- **Inspector** (mobile first): pick a road, take a photo, capture GPS, rate dust 0 to 3, submit, then watch the status.
- **Supervisor**: worklist, mark cleaned, map and road detail.

The frontend never computes a score, level, rank or explanation. It only displays what the API returns.

## Run it locally

Serve the file from an origin the API allows. Opening it as `file://` will fail CORS.

```
python3 -m http.server 3000
# open http://localhost:3000/dusttrack-live.html
```

## Config (top of the script, `CFG`)

| Key | Value |
| --- | --- |
| region | `ap-south-1` |
| clientId | `5ppg0e92dkbp6bbblsos3g312f` |
| api | `https://4e7bzdbb6g.execute-api.ap-south-1.amazonaws.com` |
| ward | empty = no `ward` param (API returns all wards). Set to `WARD-05` to filter. |
| demo | `true` shows a "Use road start (testing)" GPS button. Set `false` for the real demo. |

User pool: `ap-south-1_e7NPcfGE0`.

## What backend and infra must do first

1. **CORS on the API:** add `http://localhost:3000` and the Amplify URL to `allowed_origins`. Allowed methods `GET`, `POST`, `OPTIONS`; headers `content-type`, `authorization`.
2. **CORS on the photo bucket** (`dusttrack-dev-photos-parth-2026`): allow `PUT` from the same origins, with header `Content-Type`.
3. **Cognito groups:** every test user must be in `inspectors` or `supervisors`. A user in neither is signed out with an error.
4. **Test users:** create at least one of each. First login forces a new password (`NEW_PASSWORD_REQUIRED`), which the app handles.

## Authentication

- The app calls Cognito directly (`InitiateAuth` with `USER_PASSWORD_AUTH`, `RespondToAuthChallenge`, `REFRESH_TOKEN_AUTH`). No SDK.
- Every API call sends `Authorization: Bearer <ID token>`. The authorizer audience is the app client ID, so the **ID token** (not the access token) is used.
- Role is read from the `cognito:groups` claim in the ID token for UI routing only. **The backend must still enforce roles.**
- A 401 signs the user out. The session lives in `sessionStorage` and refreshes automatically.

## API calls the frontend makes

| Call | When | Fields the frontend reads |
| --- | --- | --- |
| `GET /v1/segments` (follows `nextCursor`) | After login, for the road list and map | `segmentId`, `roadName`, `geometry.coordinates` as `[lon, lat]`, `priorityScore`, `priorityLevel`, `isDemo` (optional) |
| `GET /v1/worklist` | Supervisor view, refetched on focus and every 60 s | `items[]` with `segmentId`, `roadName`, `priorityScore`, `priorityLevel`, `dustRating`, `lastCleanedAt`, plus optional `explanation`; `nextCursor` |
| `GET /v1/segments/{id}` | Detail drawer | `cleaningCadenceDays`, `lastCleanedAt`; optional `explanation`, `priorityBreakdown`, `recentInspections`, `cleaningEvents` |
| `POST /v1/inspections` | Inspector submit | Sends `segmentId`, `latitude`, `longitude`, `dustRating`, `fileType`. Reads `inspectionId`, `upload.url`, `upload.method`, `upload.contentType` |
| `PUT <upload.url>` | Right after the POST | Body is the image. Header is exactly `upload.contentType`. **No Authorization header.** |
| `GET /v1/inspections/{id}` | Polled after upload | `status`, plus on completion `priorityScore` (or `score`), `priorityLevel`, `explanation`, `aiAnalysis`, `disagreement` |
| `POST /v1/segments/{id}/cleaned` | Mark cleaned | Sends `cleanedAt` (UTC, no milliseconds), `squadId`, `method` (`MANUAL` or `MECHANICAL`), `remarks`. Expects 201 |

The frontend displays `priorityScore` as a whole number: values up to 1 are shown as a percentage (0.92 shows as 92); larger values are rounded as is.

## Inspection status handling

- **Polling:** every 2 s, growing to 5 s, for up to 60 s.
- **PENDING / PROCESSING:** shown as in progress, never as done.
- **COMPLETED:** shows score, level and explanation. If `aiAnalysis` is null it shows "AI check skipped". If `disagreement` is true it shows "Model differs. Your rating was kept."
- **REJECTED:** shows `message`, `rejectionReason` or `error.message` from the inspection. **Please include a human-readable reason on rejected inspections** (bad GPS, duplicate photo). Otherwise users see a generic text.
- **FAILED:** generic error with a retry button, which creates a new inspection.
- **Timeout after 60 s:** "still processing". Nothing is marked done.
- **Photo upload:** the presigned URL lasts 900 s. If S3 returns 403 on the PUT, the app tells the user to start a new inspection.

## Error format

The app accepts both `{ "error": { "code", "message" } }` and the current placeholder `{ "message" }`. Network failures and CORS blocks show a readable message.

## Things I assumed. Please confirm or correct

- Level names are `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Any other value still displays, using its own text.
- Map colour and pattern come from `priorityLevel` only, never from score thresholds.
- The optional fields in the table above are only shown if present. The names `priorityBreakdown`, `recentInspections`, `cleaningEvents`, `explanation` and `disagreement` are my guesses and should match whatever Part 1 returns.
- Inspectors can call `GET /v1/segments`. If that returns 403 for them, the app falls back to typing a segment ID.
- `REJECTED` is returned by `GET /v1/inspections/{id}`, not as an error on the `POST`.
- Segment IDs follow the seed (`SEG-001`), not the contract examples (`ROAD-001`).
- Default ward: `WARD-05` or all wards? The API returns `wardId: null` with no ward.

## Known limits

- The map is a plain line drawing with no street tiles. Leaflet and OpenStreetMap can replace it once the origin is hosted.
- No offline mode and no HEIC support. Photos must be JPEG, PNG or WebP, and images over 10 MiB are shrunk in the browser.

## Quick test checklist

1. Sign in as an inspector (new-password step works).
2. Create an inspection, upload, and see it reach COMPLETED.
3. Submit a far-away GPS point and see REJECTED with a reason.
4. Submit the same photo twice and see REJECTED.
5. Sign in as a supervisor, see the worklist, mark a road cleaned, and see it leave the list.
6. Check the browser console for CORS errors if anything fails to load.
