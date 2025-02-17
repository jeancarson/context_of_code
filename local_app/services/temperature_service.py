import requests
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TemperatureService:
    def __init__(self):
        # Map of country codes to their capitals and coordinates
        self.capitals = {
            'IE': {'city': 'Dublin', 'name': 'Ireland', 'lat': 53.3498, 'lon': -6.2603},
            'GB': {'city': 'London', 'name': 'United Kingdom', 'lat': 51.5074, 'lon': -0.1278},
            'FR': {'city': 'Paris', 'name': 'France', 'lat': 48.8566, 'lon': 2.3522}
        }
    
    def get_temperature(self, city_info: Dict) -> Optional[float]:
        """Get current temperature for a city using Open-Meteo API"""
        try:
            response = requests.get(
                'https://api.open-meteo.com/v1/forecast',
                params={
                    'latitude': city_info['lat'],
                    'longitude': city_info['lon'],
                    'current_weather': True,
                    'timezone': 'auto'
                }
            )
            response.raise_for_status()
            data = response.json()
            return data['current_weather']['temperature']
            
        except Exception as e:
            logger.error(f"Error fetching temperature for {city_info['city']}: {e}")
            return None
    
    def get_all_temperatures(self) -> list:
        """Get temperatures for all capital cities"""
        current_time = datetime.utcnow()
        temperatures = []
        
        for country_code, info in self.capitals.items():
            temp = self.get_temperature(info)
            if temp is not None:
                temperatures.append({
                    'country_code': country_code,
                    'country_name': info['name'],
                    'capital': info['city'],
                    'temperature': temp,
                    'timestamp': current_time.isoformat()
                })
        
        return temperatures
