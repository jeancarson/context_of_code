from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExchangeRate:
    from_currency: str
    to_currency: str
    rate: float
    id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'from_currency': self.from_currency,
            'to_currency': self.to_currency,
            'rate': self.rate,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ExchangeRate':
        return cls(
            id=data.get('id'),
            from_currency=data['from_currency'],
            to_currency=data['to_currency'],
            rate=float(data['rate']),
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00')) if 'timestamp' in data else None
        )