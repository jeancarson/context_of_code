from datetime import datetime
from typing import Optional
from dataclasses import dataclass

@dataclass
class Metrics:
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    memory_total_gb: float
    device_id: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
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
        # Convert ISO format string to datetime
        timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        
        return cls(
            timestamp=timestamp,
            cpu_percent=float(data['cpu_percent']),
            memory_percent=float(data['memory_percent']),
            memory_available_gb=float(data['memory_available_gb']),
            memory_total_gb=float(data['memory_total_gb']),
            device_id=str(data.get('device_id', 'unknown'))
        )
