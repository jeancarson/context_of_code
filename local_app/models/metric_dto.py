from dataclasses import dataclass
from typing import Optional
from uuid import UUID

@dataclass
class MetricDTO:
    type: str  # e.g., "GPBtoEURexchangeRate", "RAMPercent", "Temperature"
    value: float
    uuid: Optional[UUID] = None  # Will be None if not yet assigned
    timestamp: Optional[float] = None  # Will be set by the service before sending
