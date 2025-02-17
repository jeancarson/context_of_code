import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class IPService:
    def __init__(self):
        self.api_url = "http://ip-api.com/json/{}"  # Free API, no key needed
        
    def get_location(self, ip_address: str) -> Optional[Dict[str, str]]:
        """Get location information for an IP address
        
        Returns:
            Dict with location info or None if lookup fails
            Example: {
                'city': 'Mountain View',
                'region': 'California',
                'country': 'United States'
            }
        """
        try:
            # Skip lookup for local IPs
            if ip_address in ('127.0.0.1', 'localhost', '::1'):
                return {
                    'city': 'Local',
                    'region': 'Development',
                    'country': 'Machine'
                }
            
            response = requests.get(self.api_url.format(ip_address))
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return {
                        'city': data['city'],
                        'region': data['regionName'],
                        'country': data['country']
                    }
                else:
                    logger.warning(f"IP lookup failed for {ip_address}: {data['message']}")
                    return None
            else:
                logger.error(f"IP lookup failed with status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error looking up IP location: {e}")
            return None
