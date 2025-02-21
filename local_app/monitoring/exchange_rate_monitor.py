import logging
import threading
import time
from queue import Queue
import requests

from local_app.services.exchange_rate_service import ExchangeRateService
from local_app.models.exchange_rates import ExchangeRate

logger = logging.getLogger(__name__)

class ExchangeRateMonitor:
    def __init__(self, base_url: str, config_path: str = 'local_app/config/config.json', poll_interval: int = 3600):
        self.exchange_service = ExchangeRateService(config_path)
        self.base_url = base_url
        self.poll_interval = poll_interval
        self._running = False
        self._retry_queue = Queue()
        self._retry_thread = None
        self._monitor_thread = None

    def collect_and_send_data(self):
        """Collect exchange rate data and send to server"""
        try:
            rates = self.exchange_service.get_all_rates()
            if not rates:
                logger.warning("No exchange rate data available")
                return

            # Send each rate to server
            for rate_data in rates:
                # Create model object
                rate_model = ExchangeRate(
                    from_currency=rate_data['from_currency'],
                    to_currency=rate_data['to_currency'],
                    rate=rate_data['rate'],
                    timestamp=rate_data['timestamp']
                )
                
                # Send to server
                payload = {'exchange_rate': rate_model.to_dict()}
                logger.info(f"Sending exchange rate data to {self.base_url}/exchange_rates: {payload}")
                
                try:
                    response = requests.post(
                        f"{self.base_url}/exchange_rates",
                        json=payload
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully sent exchange rate data for {rate_data['from_currency']}")
                except Exception as e:
                    logger.error(f"Error sending exchange rate data: {e}")
                    self._retry_queue.put(rate_model)
            
        except Exception as e:
            logger.error(f"Error collecting exchange rate data: {e}")

    def _send_data(self, endpoint: str, data: dict):
        """Send data to specified endpoint"""
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info(f"Successfully sent data to {endpoint}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending data to {endpoint}: {e}")
            raise

    def _retry_failed_requests(self):
        """Retry failed requests"""
        while self._running:
            try:
                if not self._retry_queue.empty():
                    rate_model = self._retry_queue.get()
                    payload = {'exchange_rate': rate_model.to_dict()}
                    self._send_data('/exchange_rates', payload)
                    logger.info("Successfully resent queued exchange rate data")
                time.sleep(60)
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
                self._retry_queue.put(rate_model)
                time.sleep(60)

    def run(self):
        """Run the monitoring process"""
        while self._running:
            self.collect_and_send_data()
            time.sleep(self.poll_interval)

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
