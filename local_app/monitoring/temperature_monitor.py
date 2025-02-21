import logging
import threading
import time
from datetime import datetime
from queue import Queue
import requests

from local_app.services.temperature_service import TemperatureService
from local_app.models.temperature import CapitalTemperature
from local_app.utils.calculator import open_calculator

logger = logging.getLogger(__name__)

class TemperatureMonitor:
    def __init__(self, base_url: str, config_path: str, poll_interval: int = 3600):
        self.temperature_service = TemperatureService(config_path)
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.last_collection = 0
        self._running = False
        self._retry_queue = Queue()
        self._retry_thread = None
        self._monitor_thread = None

    def collect_and_send_data(self):
        """Collect temperature data and send to server"""
        try:
            temp_data = self.temperature_service.get_current_temperature()
            if temp_data is None:
                logger.warning("No temperature data available")
                return

            # Format data for server
            payload = {
                'temperatures': [{
                    'country_id': 1,  # Assuming GB is ID 1
                    'temperature': temp_data['temperature'],
                    'timestamp': temp_data['timestamp']
                }]
            }
            
            logger.info(f"Sending temperature data to {self.base_url}/temperatures: {payload}")
            
            response = requests.post(
                f"{self.base_url}/temperatures",
                json=payload
            )
            
            if response.status_code != 201:
                logger.error(f"Server returned error: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            logger.info("Successfully sent temperature data")
            
        except Exception as e:
            logger.error(f"Error collecting temperature data: {e}")
            if 'temp_data' in locals():
                self._retry_queue.put(temp_data)

    def _retry_failed_requests(self):
        """Retry failed requests"""
        while self._running:
            try:
                if not self._retry_queue.empty():
                    temp_data = self._retry_queue.get()
                    response = requests.post(
                        f"{self.base_url}/temperatures",
                        json=temp_data
                    )
                    response.raise_for_status()
                    logger.info("Successfully resent queued temperature data")
                    
                time.sleep(60)  # Check every minute
                    
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
                if 'temp_data' in locals():
                    self._retry_queue.put(temp_data)
                time.sleep(60)

    def run(self):
        """Run the monitoring process"""
        while self._running:
            current_time = time.time()
            
            if current_time - self.last_collection >= self.poll_interval:
                self.collect_and_send_data()
                self.last_collection = current_time
            
            time.sleep(10)

    def start(self):
        """Start the monitoring process"""
        if not self._running:
            self._running = True
            self._retry_thread = threading.Thread(target=self._retry_failed_requests)
            self._retry_thread.daemon = True
            self._retry_thread.start()
            
            self._monitor_thread = threading.Thread(target=self.run)
            self._monitor_thread.daemon = True
            self._monitor_thread.start()

    def stop(self):
        """Stop the monitoring process"""
        self._running = False
        if self._retry_thread:
            self._retry_thread.join()
        if self._monitor_thread:
            self._monitor_thread.join()
