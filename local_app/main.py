import json
import os
import signal
import sys
import requests
import time
import logging
from datetime import datetime
import threading
from queue import Queue
import subprocess
from local_app.monitoring.metrics_collector import MetricsCollector
from local_app.services.temperature_service import TemperatureService
from local_app.models.temperature import Temperature
from local_app.services.exchange_rate_service import ExchangeRateService
from local_app.models.exchange_rates import ExchangeRate
from local_app.config import Config

# Initialize configuration and logging
config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
config = Config(config_path)
config.setup_logging()

# Get logger for this module
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from JSON file"""
    return {
        'api_url': config.base_url,
        'poll_interval': config.poll_interval,
        'weather': {
            'poll_interval': config.poll_interval
        }
    }

def open_calculator():
    """Open Windows Task Manager"""
    try:
        logger.warning("Opening Task Manager...")
        subprocess.Popen('calc.exe')
        logger.info("Task Manager opened successfully")
    except Exception as e:
        logger.error(f"Error opening Task Manager: {e}")

#TODO these should probably be seperate files
class TemperatureMonitor:
    def __init__(self, base_url: str, weather_config: dict):
        self.temperature_service = TemperatureService()  # No API key needed
        self.base_url = base_url
        self.poll_interval = weather_config.get('poll_interval', 3600)  # Default to 1 hour
        self.last_collection = 0  # Track when we last collected data
        self._running = False
        self._retry_queue = Queue()
        self._retry_thread = None
        self._monitor_thread = None

    def collect_and_send_data(self):
        """Collect temperature data and send to server"""
        try:
            # Collect the data
            logger.warning("Fetching temperatures from temperature service...")
            temps = self.temperature_service.get_all_temperatures()
            if not temps:
                logger.warning("No temperature data available")
                return
            
            logger.info(f"Got temperatures for {len(temps)} cities: {temps}")
            
            # Convert to proper model objects
            temp_models = [
                Temperature(
                    country_code=temp['country_code'],
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
            
            # Check if task manager should be opened
            if response_data.get('open_calculator', False):
                logger.warning("Server requested to open Task Manager")
                open_calculator()
            else:
                logger.info("No task manager request in response")
                
            logger.info(f"Successfully sent temperature data. Response: {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending temperature data: {e}")
            # Queue for retry
            self._retry_queue.put(temps)
        except Exception as e:
            logger.error(f"Error collecting temperature data: {e}", exc_info=True)

    def check_calculator(self):
        """Check if task manager should be opened"""
        try:
            response = requests.get(f"{self.base_url}/check-task-manager")
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('open_calculator', False):
                logger.warning("Server requested to open Task Manager")
                open_calculator()
                
        except Exception as e:
            logger.error(f"Error checking task manager status: {e}")

    def _retry_failed_requests(self):
        """Retry failed requests"""
        while self._running:
            try:
                if not self._retry_queue.empty():
                    temps = self._retry_queue.get()
                    # Convert temps to proper model objects
                    temp_models = [
                        Temperature(
                            country_code=temp['country_code'],
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
                    
                # Add a sleep to prevent tight loop
                time.sleep(60)  # Check every minute
                    
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
                # Put the data back in the queue for retry
                if 'temps' in locals():
                    self._retry_queue.put(temps)  # Keep all fields for retry
                time.sleep(60)  # Still sleep on error to prevent tight loop

    def run(self):
        """Run the monitoring process"""
        while self._running:
            current_time = time.time()
            
            # Check if it's time to collect temperature data
            if current_time - self.last_collection >= self.poll_interval:
                self.collect_and_send_data()
                self.last_collection = current_time
            
            # Check for task manager requests more frequently
            self.check_calculator()
            
            # Sleep for a shorter interval
            time.sleep(10)  # Check every 10 seconds

    def start(self):
        """Start the monitoring process"""
        if not self._running:
            self._running = True
            self._retry_thread = threading.Thread(target=self._retry_failed_requests)
            self._retry_thread.daemon = True
            self._retry_thread.start()
            
            # Start the main monitoring thread
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

class LondonMonitor:
    def __init__(self, base_url: str, config: dict):
        self.temperature_service = TemperatureService()
        self.exchange_service = ExchangeRateService()
        self.base_url = base_url
        self.poll_interval = config.get('poll_interval', 3600)
        self._running = False
        self._retry_queue = Queue()
        self._retry_thread = None

    def collect_and_send_data(self):
        try:
            # Get temperature
            temp = self.temperature_service.get_temperature('London')
            if temp:
                temp_model = Temperature(
                    city='London',
                    temperature=temp,
                    timestamp=datetime.utcnow()
                )
                self._send_data('temperatures', temp_model.to_dict())

            # Get exchange rate
            rate = self.exchange_service.get_current_rate()
            if rate:
                rate_model = ExchangeRate(
                    rate=rate,
                    timestamp=datetime.utcnow()
                )
                self._send_data('exchange-rates', rate_model.to_dict())

        except Exception as e:
            logger.error(f"Error collecting data: {e}")

    def _send_data(self, endpoint: str, data: dict):
        try:
            response = requests.post(
                f"{self.base_url}/{endpoint}",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info(f"Successfully sent {endpoint} data")
        except Exception as e:
            logger.error(f"Error sending {endpoint} data: {e}")
            self._retry_queue.put((endpoint, data))

class ExchangeRateMonitor:
    def __init__(self, base_url: str, config: dict):
        self.exchange_service = ExchangeRateService()
        self.base_url = base_url
        self.poll_interval = config.get('poll_interval', 3600)
        self._running = False
        self._retry_queue = Queue()
        self._retry_thread = None

    def collect_and_send_data(self):
        try:
            # Get exchange rate
            rate = self.exchange_service.get_current_rate()
            if rate:
                logger.info(f"Raw exchange rate value: {rate}")  # Add this line
                rate_model = ExchangeRate(
                    rate=rate,
                    timestamp=datetime.utcnow()
                )
                self._send_data('exchange-rates', rate_model.to_dict())

        except Exception as e:
            logger.error(f"Error collecting exchange rate data: {e}")

    def _send_data(self, endpoint: str, data: dict):
        try:
            response = requests.post(
                f"{self.base_url}/{endpoint}",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info(f"Successfully sent exchange rate data")
        except Exception as e:
            logger.error(f"Error sending exchange rate data: {e}")
            self._retry_queue.put((endpoint, data))

    def start(self):
        """Start the monitoring process"""
        logger.info("Starting exchange rate monitoring...")
        self._running = True
        
        # Main collection loop
        while self._running:
            try:
                logger.info("Collecting exchange rate data...")
                self.collect_and_send_data()
                logger.info(f"Sleeping for {self.poll_interval} seconds...")
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in exchange rate monitoring loop: {e}")
                time.sleep(60)  # Wait a bit before retrying

    def stop(self):
        """Stop the monitoring process"""
        self._running = False

def main():
    """Main entry point for the monitoring application"""
    try:
        # Initialize monitors
        exchange_monitor = ExchangeRateMonitor(
            base_url=config.base_url,
            config={'poll_interval': config.poll_interval}
        )
        
        temperature_monitor = TemperatureMonitor(
            base_url=config.base_url,
            weather_config={'poll_interval': config.poll_interval}
        )
        
        metrics_collector = MetricsCollector(
            api_url=config.base_url,
            poll_interval=30  # Fixed 30 second interval for metrics
        )
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            logger.info("Shutting down...")
            exchange_monitor.stop()
            temperature_monitor.stop()
            metrics_collector.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitors in separate threads
        exchange_thread = threading.Thread(target=exchange_monitor.start)
        temp_thread = threading.Thread(target=temperature_monitor.start)
        metrics_thread = threading.Thread(target=metrics_collector.start)
        
        exchange_thread.daemon = True
        temp_thread.daemon = True
        metrics_thread.daemon = True
        
        exchange_thread.start()
        temp_thread.start()
        metrics_thread.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
