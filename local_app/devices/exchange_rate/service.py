import os
import requests
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
        """Get current GBP to EUR exchange rate using Frankfurter API"""
        url = "https://api.frankfurter.app/latest?from=GBP&to=EUR"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Extract the conversion rate
            rate = data["rates"]["EUR"]
            return round(rate, 4)
            
        except Exception as e:
            self.logger.error(f"Error fetching exchange rate: {e}")
            # Return a reasonable default if API fails
            return 1.15
