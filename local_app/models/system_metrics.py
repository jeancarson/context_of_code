from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SystemMetrics(BaseModel):
    """Model for system metrics data"""
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    memory_total_gb: float
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)
    
    class Config:
        json_schema_extra = {
            "example": {
                "cpu_percent": 45.2,
                "memory_percent": 65.8,
                "memory_available_gb": 8.5,
                "memory_total_gb": 16.0,
                "timestamp": "2025-02-15T18:54:14Z"
            }
        }
