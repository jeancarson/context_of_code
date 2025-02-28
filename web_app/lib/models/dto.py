from pydantic import BaseModel, validator
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal
import uuid

def normalize_uuid(value: Optional[str]) -> Optional[str]:
    """Normalize UUID format by ensuring it has dashes"""
    if value is None:
        return None
    # If UUID has no dashes, add them back
    if '-' not in value:
        value = str(uuid.UUID(value))
    return value

class AggregatorDTO(BaseModel):
    """Data transfer object for aggregators"""
    name: str
    aggregator_uuid: Optional[str] = None

    @validator('aggregator_uuid')
    def normalize_aggregator_uuid(cls, v):
        return normalize_uuid(v)

class DeviceDTO(BaseModel):
    """Data transfer object for devices"""
    device_name: str
    device_uuid: Optional[str] = None
    aggregator_uuid: str

    @validator('device_uuid', 'aggregator_uuid')
    def normalize_device_uuids(cls, v):
        return normalize_uuid(v)

class MetricTypeDTO(BaseModel):
    """Data transfer object for metric types"""
    metric_type_name: str
    device_uuid: str

    @validator('device_uuid')
    def normalize_device_uuid(cls, v):
        return normalize_uuid(v)

class MetricValueDTO(BaseModel):
    """Data transfer object for metric values"""
    metric_type_name: str
    value: float

class MetricSnapshotDTO(BaseModel):
    """Data transfer object for metric snapshots with their values"""
    device_uuid: str
    client_timestamp_utc: Optional[str] = None
    client_timezone_minutes: int
    metric_values: List[MetricValueDTO]

    @validator('device_uuid')
    def normalize_device_uuid(cls, v):
        return normalize_uuid(v)

def convert_to_snapshot_orm(snapshot: MetricSnapshotDTO, device_id: int) -> 'MetricSnapshots':
    """Convert a MetricSnapshotDTO to an ORM MetricSnapshots object"""
    from .generated_models import MetricSnapshots
    
    return MetricSnapshots(
        device_id=device_id,
        client_timestamp_utc=snapshot.client_timestamp_utc or str(datetime.utcnow()),
        client_timezone_minutes=snapshot.client_timezone_minutes,
        server_timestamp_utc=str(datetime.utcnow()),
        server_timezone_minutes=0  # Use system timezone offset here
    )

def convert_to_metric_value_orm(value: MetricValueDTO, snapshot_id: int, type_id: int) -> 'MetricValues':
    """Convert a MetricValueDTO to an ORM MetricValues object"""
    from .generated_models import MetricValues
    
    return MetricValues(
        metric_snapshot_id=snapshot_id,
        metric_type_id=type_id,
        value=Decimal(str(value.value))
    )
