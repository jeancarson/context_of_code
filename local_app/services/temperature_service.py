import requests
import logging
from datetime import datetime
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)

class TemperatureService:
    def __init__(self, config_path: str = '../config.json'):
        # Load config
        with open(config_path) as f:
            config = json.load(f)
        
        self.country_config = config['country']
    
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
            logger.error(f"Error fetching temperature for {city_info['name']}: {e}")
            return None
    
    def get_current_temperature(self) -> Optional[dict]:
        """Get temperature for configured capital city"""
        current_time = datetime.utcnow()
        
        temp = self.get_temperature({
            'name': self.country_config['capital']['name'],
            'lat': self.country_config['capital']['lat'],
            'lon': self.country_config['capital']['lon']
        })
        
        if temp is not None:
            return {
                'country_code': self.country_config['code'],
                'country_name': self.country_config['name'],
                'capital': self.country_config['capital']['name'],
                'temperature': temp,
                'timestamp': current_time.isoformat()
            }
        return None
