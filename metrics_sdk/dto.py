from pydantic import BaseModel, validator, Field
from typing import List, Optional
from datetime import datetime
import uuid

def normalize_uuid(value: Optional[str]) -> Optional[str]:
    """Normalize UUID format by ensuring it has dashes"""
    if value is None:
        return None
    # If UUID has no dashes, add them back
    if '-' not in value:
        value = str(uuid.UUID(value))
    return value

class MetricValueDTO(BaseModel):
    """Data transfer object for metric values"""
    type: str = Field(..., alias='metric_type_name')  # Use type in JSON, but metric_type_name in Python
    value: float

    class Config:
        populate_by_name = True

class MetricSnapshotDTO(BaseModel):
    """Data transfer object for metric snapshots with their values"""
    device_uuid: str
    aggregator_uuid: str
    client_timestamp: str = Field(alias='client_timestamp_utc')  # Match Flask app's expected field name
    client_timezone_minutes: int
    metrics: List[MetricValueDTO]  # This will be used both internally and in JSON

    @validator('device_uuid', 'aggregator_uuid')
    def normalize_uuids(cls, v):
        return normalize_uuid(v)

    def __init__(self, **data):
        if 'client_timestamp' not in data and 'client_timestamp_utc' not in data:
            data['client_timestamp'] = datetime.utcnow().isoformat()
        super().__init__(**data)

    class Config:
        populate_by_name = True
