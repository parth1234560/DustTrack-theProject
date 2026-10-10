"""Pytest bootstrap: moto-friendly env, clock reset, AWS fixtures."""

from __future__ import annotations

import os

# Local-only SDK setup (Lambda provides real region/credentials itself;
# AWS_REGION/AWS_DEFAULT_REGION are reserved there and settable here only).
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("INSPECTIONS_TABLE", "test-inspections")
os.environ.setdefault("SEGMENTS_TABLE", "test-segments")
os.environ.setdefault("CLEANING_EVENTS_TABLE", "test-cleaning-events")
os.environ.setdefault("PHOTO_BUCKET", "test-photos")

import boto3
import pytest
from moto import mock_aws

from common import clock


@pytest.fixture(autouse=True)
def _reset_clock():
    clock.set_now(None)
    yield
    clock.set_now(None)


@pytest.fixture()
def aws_resources():
    """Moto-backed tables + photo bucket (names from env, region ap-south-1)."""
    with mock_aws():
        ddb = boto3.resource("dynamodb")
        tables = {
            os.environ["INSPECTIONS_TABLE"]: "inspectionId",
            os.environ["SEGMENTS_TABLE"]: "segmentId",
            os.environ["CLEANING_EVENTS_TABLE"]: "eventId",
        }
        for name, key in tables.items():
            ddb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        s3 = boto3.client("s3")
        s3.create_bucket(
            Bucket=os.environ["PHOTO_BUCKET"],
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        yield {"dynamodb": ddb, "s3": s3}
