from datetime import datetime

class ExchangeRate:
    def __init__(self, rate: float, timestamp: datetime):
        self.rate = rate
        self.timestamp = timestamp

    def to_dict(self):
        return {
            'rate': self.rate,
            'timestamp': self.timestamp.isoformat()
        }