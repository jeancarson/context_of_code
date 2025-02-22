from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

@dataclass
class MetricDTO:
    type: str  # e.g., "GPBtoEURexchangeRate", "RAMPercent", "Temperature"
    value: float
    uuid: Optional[UUID] = None  # Device UUID
    timestamp: Optional[float] = None  # Unix timestamp

@dataclass
class MetricsRequest:
    metrics: list[MetricDTO]  # List of metrics to store

def convert_to_orm(metric: MetricDTO, device_id: int, type_id: int) -> 'Metrics':
    """Convert a MetricDTO to an ORM Metrics object"""
    from .generated_models import Metrics
    
    return Metrics(
        device=device_id,
        type=type_id,
        value=Decimal(str(metric.value)),  # Convert float to Decimal for precision
        timestamp=str(datetime.fromtimestamp(metric.timestamp)) if metric.timestamp else str(datetime.now())
    )
