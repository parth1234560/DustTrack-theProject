import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

inspections = dynamodb.Table(os.environ["INSPECTIONS_TABLE"])
segments = dynamodb.Table(os.environ["SEGMENTS_TABLE"])
cleaning_events = dynamodb.Table(os.environ["CLEANING_EVENTS_TABLE"])
photo_bucket = os.environ["PHOTO_BUCKET"]
upload_url_expires = int(os.environ.get("UPLOAD_URL_EXPIRES", "900"))


def decimal_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Unsupported type: {type(value).__name__}")


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=decimal_default),
    }


def scan_all(table):
    items = []
    args = {}

    while True:
        result = table.scan(**args)
        items.extend(result.get("Items", []))

        if "LastEvaluatedKey" not in result:
            break

        args["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    return items


def lambda_handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "UNKNOWN")
    path = event.get("rawPath", "/")
    params = event.get("pathParameters") or {}

    try:
        # GET /v1/segments
        if method == "GET" and path == "/v1/segments":
            return response(200, {"items": scan_all(segments)})

        # GET /v1/segments/{id}
        if (
            method == "GET"
            and path.startswith("/v1/segments/")
            and params.get("id")
        ):
            result = segments.get_item(
                Key={"segmentId": params["id"]}
            )
            item = result.get("Item")

            if not item:
                return response(404, {"message": "Segment not found"})

            return response(200, item)

        # POST /v1/inspections
        if method == "POST" and path == "/v1/inspections":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return response(400, {"message": "Invalid JSON body"})

            segment_id = body.get("segmentId")
            file_type = body.get("fileType")
            latitude = body.get("latitude")
            longitude = body.get("longitude")
            dust_rating = body.get("dustRating")

            if not isinstance(segment_id, str) or not segment_id.strip():
                return response(400, {"message": "segmentId is required"})

            if file_type not in ["image/jpeg", "image/png", "image/webp"]:
                return response(400, {"message": "fileType must be image/jpeg, image/png or image/webp"})

            if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
                return response(400, {"message": "latitude and longitude are required numbers"})

            if not isinstance(dust_rating, int) or dust_rating < 0 or dust_rating > 3:
                return response(400, {"message": "dustRating must be an integer from 0 to 3"})

            inspection_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            extension = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
            }[file_type]
            photo_key = f"inspections/{inspection_id}/photo.{extension}"

            item = {
                "inspectionId": inspection_id,
                "segmentId": segment_id.strip(),
                "photoKey": photo_key,
                "status": "PENDING",
                "createdAt": created_at,
                "latitude": Decimal(str(latitude)),
                "longitude": Decimal(str(longitude)),
                "inspectorDustRating": dust_rating,
                "fileType": file_type,
            }

            inspections.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(inspectionId)",
            )

            upload_url = s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": photo_bucket,
                    "Key": photo_key,
                    "ContentType": file_type,
                },
                ExpiresIn=upload_url_expires,
            )

            return response(201, {
                "inspectionId": inspection_id,
                "status": "PENDING",
                "upload": {
                    "url": upload_url,
                    "method": "PUT",
                    "contentType": file_type,
                    "expiresIn": upload_url_expires,
                },
            })

        # GET /v1/inspections/{id}
        if (
            method == "GET"
            and path.startswith("/v1/inspections/")
            and params.get("id")
        ):
            result = inspections.get_item(
                Key={"inspectionId": params["id"]}
            )
            item = result.get("Item")

            if not item:
                return response(404, {"message": "Inspection not found"})

            return response(200, item)

        # GET /v1/worklist
        if method == "GET" and path == "/v1/worklist":
            all_segments = scan_all(segments)

            worklist = [
                item
                for item in all_segments
                if item.get("cleaningStatus", "NEEDS_CLEANING") != "CLEAN"
            ]

            return response(200, {"items": worklist})

        # POST /v1/segments/{id}/cleaned
        if (
            method == "POST"
            and path.startswith("/v1/segments/")
            and path.endswith("/cleaned")
            and params.get("id")
        ):
            segment_id = params["id"]

            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return response(400, {"message": "Invalid JSON body"})

            cleaned_at = datetime.now(timezone.utc).isoformat()
            event_id = str(uuid.uuid4())

            segments.update_item(
                Key={"segmentId": segment_id},
                UpdateExpression=(
                    "SET cleaningStatus = :status, lastCleanedAt = :time"
                ),
                ExpressionAttributeValues={
                    ":status": "CLEAN",
                    ":time": cleaned_at,
                },
                ConditionExpression="attribute_exists(segmentId)",
            )

            event_item = {
                "eventId": event_id,
                "segmentId": segment_id,
                "cleanedAt": cleaned_at,
                "notes": str(body.get("notes", "")),
            }

            cleaning_events.put_item(Item=event_item)

            return response(
                200,
                {
                    "message": "Segment marked as cleaned",
                    **event_item,
                },
            )

        return response(404, {"message": "Route not found"})

    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code", "Unknown")

        if error_code == "ConditionalCheckFailedException":
            return response(404, {"message": "Segment not found"})

        print(f"DynamoDB error: {error_code}")
        return response(500, {"message": "Database operation failed"})

    except Exception:
        print("Unhandled API error")
        return response(500, {"message": "Internal server error"})

