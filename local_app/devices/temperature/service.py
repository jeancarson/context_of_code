import random
from typing import Optional
from ..base_device import BaseDevice

class TemperatureService(BaseDevice):
    def __init__(self, base_url: str, poll_interval: int):
        super().__init__(
            device_name="temperature",
            metric_type="Temperature",
            base_url=base_url,
            poll_interval=poll_interval
        )
        
    def get_current_temperature(self) -> float:
        """Simulate getting temperature reading"""
        return round(random.uniform(20.0, 25.0), 2)
