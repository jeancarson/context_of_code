import requests
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ExchangeRateService:
    def __init__(self, config_path: str = '../config.json'):
        # Load config
        with open(config_path) as f:
            config = json.load(f)
        
        self.country_config = config['country']
        self.base_url = "https://open.er-api.com/v6/latest"
        
    def get_all_rates(self) -> list:
        """Get exchange rates for configured currency against EUR"""
        current_time = datetime.utcnow()
        rates = []
        
        # Only get rate for configured country's currency
        if self.country_config['currency'] != 'EUR':
            try:
                response = requests.get(f"{self.base_url}/{self.country_config['currency']}")
                response.raise_for_status()
                data = response.json()
                
                if 'rates' not in data:
                    logger.error(f"Unexpected API response structure: {data}")
                    return rates
                    
                rate = data['rates']['EUR']
                logger.info(f"Fetched {self.country_config['currency']}/EUR rate: {rate}")
                
                # Add to rates list
                rates.append({
                    'from_currency': self.country_config['currency'],
                    'to_currency': 'EUR',
                    'rate': rate,
                    'timestamp': current_time
                })
                
            except Exception as e:
                logger.error(f"Error fetching {self.country_config['currency']}/EUR rate: {e}")
                
        return rates