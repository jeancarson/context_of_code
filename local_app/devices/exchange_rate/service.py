import random
from typing import Optional
from ..base_device import BaseDevice

class ExchangeRateService(BaseDevice):
    def __init__(self, base_url: str, poll_interval: int):
        super().__init__(
            device_name="exchange_rate",
            metric_type="GPBtoEURexchangeRate",
            base_url=base_url,
            poll_interval=poll_interval
        )
        
    def get_current_rate(self) -> float:
        """Simulate getting exchange rate"""
        return round(random.uniform(1.15, 1.20), 4)
