import logging
import time
import threading
import requests
from local_app.utils.calculator import open_calculator

logger = logging.getLogger(__name__)

class CalculatorMonitor(threading.Thread):
    def __init__(self, base_url, poll_interval=5):
        super().__init__()
        self.base_url = base_url
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self.daemon = True

    def stop(self):
        """Stop the monitoring thread"""
        self._stop_event.set()

    def run(self):
        """Main monitoring loop"""
        logger.info("Calculator monitor started")
        
        while not self._stop_event.is_set():
            try:
                response = requests.get(f"{self.base_url}/check-calculator")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('open_calculator'):
                        logger.info("Calculator flag is True, opening calculator...")
                        open_calculator()
                
            except Exception as e:
                logger.error(f"Error checking calculator status: {e}")
            
            time.sleep(self.poll_interval)
        
        logger.info("Calculator monitor stopped")
