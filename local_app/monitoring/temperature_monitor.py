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
    def __init__(self, base_url: str, poll_interval: int = 3600):
        self.temperature_service = TemperatureService()
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
            logger.warning("Fetching temperatures from temperature service...")
            temps = self.temperature_service.get_all_temperatures()
            if not temps:
                logger.warning("No temperature data available")
                return
            
            logger.info(f"Got temperatures for {len(temps)} cities: {temps}")
            
            # Convert to proper model objects
            temp_models = [
                CapitalTemperature(
                    id=None,  # ID will be assigned by the server
                    country_id=temp['country_code'],  # Use country_code as the country_id
                    temperature=temp['temperature'],
                    timestamp=datetime.fromisoformat(temp['timestamp'])
                ) for temp in temps
            ]
            
            # Send to server
            payload = {'temperatures': [temp.to_dict() for temp in temp_models]}
            logger.info(f"Sending temperature data to {self.base_url}/temperatures: {payload}")
            
            response = requests.post(
                f"{self.base_url}/temperatures",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Server response: {response_data}")
            
            # Check if calculator should be opened
            if response_data.get('open_calculator', False):
                logger.warning("Server requested to open calculator")
                open_calculator()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending temperature data: {e}")
            # Queue for retry
            self._retry_queue.put(temps)
        except Exception as e:
            logger.error(f"Error collecting temperature data: {e}", exc_info=True)

    def _retry_failed_requests(self):
        """Retry failed requests"""
        while self._running:
            try:
                if not self._retry_queue.empty():
                    temps = self._retry_queue.get()
                    temp_models = [
                        CapitalTemperature(
                            id=None,  # ID will be assigned by the server
                            country_id=temp['country_code'],  # Use country_code as the country_id
                            temperature=temp['temperature'],
                            timestamp=datetime.fromisoformat(temp['timestamp'])
                        ) for temp in temps
                    ]
                    
                    payload = {'temperatures': [temp.to_dict() for temp in temp_models]}
                    response = requests.post(
                        f"{self.base_url}/temperatures",
                        json=payload,
                        headers={'Content-Type': 'application/json'}
                    )
                    response.raise_for_status()
                    logger.info("Successfully resent queued temperature data")
                    
                time.sleep(60)  # Check every minute
                    
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
                if 'temps' in locals():
                    self._retry_queue.put(temps)
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
