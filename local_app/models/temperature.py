from dataclasses import dataclass
from datetime import datetime

@dataclass
class Temperature:
    """Simple data class for temperature data before sending to server"""
    country_code: str
    country_name: str
    capital: str
    temperature: float
    timestamp: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'country_code': self.country_code,
            'country_name': self.country_name,
            'capital': self.capital,
            'temperature': self.temperature,
            'timestamp': self.timestamp.isoformat()
        }
