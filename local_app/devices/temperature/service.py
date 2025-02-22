import os
import requests
from typing import Optional, List
from ..base_device import BaseDevice, MetricDTO
import time

class TemperatureService(BaseDevice):
    def __init__(self, base_url: str, poll_interval: int):
        super().__init__(
            device_name="Temperature",
            metric_type="Temperature",
            base_url=base_url,
            poll_interval=poll_interval
        )
        self.city = "London"
        
    def get_current_temperature(self) -> float:
        """Get current temperature in London using WeatherAPI"""
        url = f"https://wttr.in/{self.city}?format=j1"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Extract temperature in Celsius
            temp = float(data["current_condition"][0]["temp_C"])
            return round(temp, 2)
            
        except Exception as e:
            self.logger.error(f"Error fetching temperature for {self.city}: {e}")
            # Return a reasonable default if API fails
            return 20.0
            
    def get_current_metrics(self) -> List[MetricDTO]:
        """Get current metrics"""
        temperature = self.get_current_temperature()
        metric = self.create_metric(temperature)
        return [metric]
        
    def run(self):
        """Run the temperature service"""
        while self._running:
            try:
                temperature = self.get_current_temperature()
                metric = self.create_metric(temperature)
                metric.type = "Temperature"  # Use the same type as the device
                
                self.publish_metrics([metric])
                
            except Exception as e:
                self.logger.error(f"Error in temperature service: {e}")
                
            time.sleep(self.poll_interval)
