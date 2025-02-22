from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class MetricDTO(BaseModel):
    """Data transfer object for metrics"""
    type: str
    value: float
    device_id: Optional[str] = None  # UUID as hex string
    created_at: Optional[str] = None

class MetricsRequest(BaseModel):
    """Request containing a list of metrics"""
    metrics: List[MetricDTO]

def convert_to_orm(metric: MetricDTO, device_id: int, type_id: int) -> 'Metrics':
    """Convert a MetricDTO to an ORM Metrics object"""
    from .generated_models import Metrics
    
    return Metrics(
        device=device_id,
        type=type_id,
        value=Decimal(str(metric.value)),  # Convert float to Decimal for precision
        created_at=metric.created_at if metric.created_at else str(datetime.now())
    )
