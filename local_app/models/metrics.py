from datetime import datetime
from typing import Optional
from dataclasses import dataclass

@dataclass
class Metrics:
    """Model for system metrics data"""
    id: Optional[int]
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    memory_total_gb: float
    device_id: str

    def __init__(self, **data):
        self.id = data.get('id')
        self.timestamp = data.get('timestamp', datetime.utcnow())
        self.cpu_percent = data['cpu_percent']
        self.memory_percent = data['memory_percent']
        self.memory_available_gb = data['memory_available_gb']
        self.memory_total_gb = data['memory_total_gb']
        self.device_id = data.get('device_id', 'unknown')

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_available_gb': self.memory_available_gb,
            'memory_total_gb': self.memory_total_gb,
            'device_id': self.device_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Metrics':
        """Create Metrics instance from dictionary"""
        if 'timestamp' in data:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        return cls(**data)
