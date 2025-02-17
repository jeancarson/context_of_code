import requests
import logging

logger = logging.getLogger(__name__)

class ExchangeRateService:
    def __init__(self):
        self.api_url = "https://open.er-api.com/v6/latest/GBP"
        
    def get_current_rate(self) -> float:
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
            
            # Add debug logging
            logger.debug(f"Raw API response: {data}")
            
            if 'rates' not in data:
                logger.error(f"Unexpected API response structure: {data}")
                return None
                
            rate = data['rates']['EUR']
            logger.info(f"Fetched EUR/GBP rate: {rate}")
            return rate
            
        except Exception as e:
            logger.error(f"Error fetching exchange rate: {e}")
            return None