from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExchangeRate:
    id: str
    from_currency: int
    to_currency: int
    rate: float
    timestamp: datetime

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
            id=data['id'],
            from_currency=data['from_currency'],
            to_currency=data['to_currency'],
            rate=float(data['rate']),
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        )