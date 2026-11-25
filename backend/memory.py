"""Persistent LangGraph checkpoint memory backed by DynamoDB and S3."""

from langgraph_checkpoint_aws import DynamoDBSaver

from .config import (
    AWS_REGION,
    CHECKPOINT_BUCKET,
    CHECKPOINT_TABLE,
    MEMORY_REQUIRED_ENV,
    require_env,
)
from .schemas import FlightDetails, TravelDetails


def build_checkpointer() -> DynamoDBSaver:
    """Create the persistent TripCraft checkpointer.

    DynamoDB is the primary checkpoint store. The AWS saver can offload
    larger serialized payloads to the configured S3 bucket.
    """
    require_env(MEMORY_REQUIRED_ENV)

    checkpointer = DynamoDBSaver(
        table_name=CHECKPOINT_TABLE,
        region_name=AWS_REGION,
        s3_offload_config={
            "bucket_name": CHECKPOINT_BUCKET,
        },
    )

    # Keep strict/safe MsgPack deserialization while allowing our own
    # Pydantic models to round-trip through checkpoints.
    return checkpointer.with_allowlist(
        [
            (
                TravelDetails.__module__,
                TravelDetails.__name__,
            ),
            (
                FlightDetails.__module__,
                FlightDetails.__name__,
            ),
        ]
    )
