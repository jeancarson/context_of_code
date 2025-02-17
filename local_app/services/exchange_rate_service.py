import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ExchangeRateService:
    def __init__(self):
        self.api_url = "https://api.exchangerate-api.com/v4/latest/GBP"
    
    def get_current_rate(self) -> float:
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
            return data['rates']['EUR']
        except Exception as e:
            logger.error(f"Error fetching exchange rate: {e}")
            return None