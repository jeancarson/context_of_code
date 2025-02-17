from pytrends.request import TrendReq
import logging
from datetime import datetime
import time
import random

logger = logging.getLogger(__name__)

class SearchCollector:
    def __init__(self, metrics_url, search_config):
        self.pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=1)
        self.metrics_url = metrics_url
        self.celebrity_name = search_config['celebrity_name']
        self.last_request_time = 0
        self.min_request_interval = 60  # Minimum seconds between requests
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits by waiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last + random.uniform(0, 5)
            logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds before next request")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def collect_celebrity_trends(self) -> dict:
        """Get today's search trends for the configured celebrity"""
        try:
            self._wait_for_rate_limit()
            
            # Build the payload
            #TODO change this from celebrity_name to search_term or similiar
            self.pytrends.build_payload(kw_list=[self.celebrity_name], timeframe='now 1-d')
            
            # Get interest over time
            interest_df = self.pytrends.interest_over_time()
            
            if not interest_df.empty:
                # Get the most recent value
                latest_value = interest_df[self.celebrity_name].iloc[-1]
                logger.info(f"Retrieved {self.celebrity_name} search trend value: {latest_value}")
                
                # Format the data for sending to server
                return {
                    'celebrity_name': self.celebrity_name,
                    'search_count': int(latest_value),
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            logger.warning(f"No trend data available for {self.celebrity_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching trends: {e}")
            # If we hit rate limit, wait longer next time
            if "429" in str(e):
                self.min_request_interval = min(self.min_request_interval * 2, 3600)  # Max 1 hour
                logger.warning(f"Rate limit hit. Increasing wait time to {self.min_request_interval} seconds")
            return None
