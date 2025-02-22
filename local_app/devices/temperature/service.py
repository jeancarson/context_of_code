import os
import requests
from typing import Optional
from ..base_device import BaseDevice

class TemperatureService(BaseDevice):
    def __init__(self, base_url: str, poll_interval: int):
        super().__init__(
            device_name="LondonTemperature",
            metric_type="LondonTemperature",
            base_url=base_url,
            poll_interval=poll_interval
        )
        
    def get_current_temperature(self) -> float:
        """Get current temperature in London using WeatherAPI"""
        url = "https://wttr.in/London?format=j1"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Extract temperature in Celsius
            temp = float(data["current_condition"][0]["temp_C"])
            return round(temp, 2)
            
        except Exception as e:
            self.logger.error(f"Error fetching temperature: {e}")
            # Return a reasonable default if API fails
            return 20.0
