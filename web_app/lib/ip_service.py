import requests
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

class IPService:
    def __init__(self):
        self.api_url = "http://ip-api.com/json/{}"
        self._cache = {}  # {ip: (location_data, timestamp)}
        self._cache_lock = threading.Lock()
        self._cache_ttl = timedelta(hours=24)  # Cache for 24 hours
        
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cached data is still valid"""
        return datetime.utcnow() - timestamp < self._cache_ttl
        
    def get_location(self, ip_address: str) -> Optional[Dict[str, str]]:
        """Get location information for an IP address with caching
        
        Returns:
            Dict with location info or None if lookup fails
        """
        # Check cache first
        with self._cache_lock:
            cached_data = self._cache.get(ip_address)
            if cached_data:
                location, timestamp = cached_data
                if self._is_cache_valid(timestamp):
                    return location
                else:
                    # Remove expired cache entry
                    del self._cache[ip_address]
        
        try:
            # Skip lookup for local IPs
            if ip_address in ('127.0.0.1', 'localhost', '::1'):
                location = {
                    'city': 'Local',
                    'region': 'Development',
                    'country': 'Machine'
                }
                with self._cache_lock:
                    self._cache[ip_address] = (location, datetime.utcnow())
                return location
            
            response = requests.get(self.api_url.format(ip_address))
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    location = {
                        'city': data['city'],
                        'region': data['regionName'],
                        'country': data['country']
                    }
                    # Cache the result
                    with self._cache_lock:
                        self._cache[ip_address] = (location, datetime.utcnow())
                    return location
                else:
                    logger.warning(f"IP lookup failed for {ip_address}: {data['message']}")
                    return None
            else:
                logger.error(f"IP lookup failed with status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error looking up IP location: {e}")
            return None
