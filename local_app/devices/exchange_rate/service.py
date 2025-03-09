import os
import requests
from typing import Optional, List
from ..base_device import BaseDevice, MetricDTO

class ExchangeRateService(BaseDevice):
    def __init__(self, base_url: str, poll_interval: int):
        super().__init__(
            device_name="exchange_rate",
            metric_type="GPBtoEURexchangeRate",
            base_url=base_url,
            poll_interval=poll_interval
        )
        
    def get_current_rate(self) -> Optional[float]:
        """
        Get current GBP to EUR exchange rate using Frankfurter API
        
        Returns:
            Optional[float]: The current exchange rate, or None if the API call fails
        """
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
            return None
            
    def get_current_metrics(self) -> List[MetricDTO]:
        """
        Get current metrics
        
        Returns:
            List[MetricDTO]: List containing the exchange rate metric, or an empty list if data is unavailable
        """
        rate = self.get_current_rate()
        
        # Only create and return a metric if we have valid data
        if rate is not None:
            metric = self.create_metric(rate)
            return [metric]
        else:
            self.logger.warning("No exchange rate data available to report")
            return []
