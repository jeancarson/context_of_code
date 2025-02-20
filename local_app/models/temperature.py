from dataclasses import dataclass
from datetime import datetime

@dataclass
class CapitalTemperature:
    """Data class for capital city temperature data"""
    id: str
    country_id: int
    temperature: float
    timestamp: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'country_id': self.country_id,
            'temperature': self.temperature,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CapitalTemperature':
        """Create instance from dictionary data"""
        return cls(
            id=data['id'],
            country_id=data['country_id'],
            temperature=float(data['temperature']),
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        )
