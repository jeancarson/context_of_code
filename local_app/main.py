import json
import logging
import os
import signal
import sys
import time
from typing import Dict, Any
from local_app.monitoring.metrics_monitor import MetricsMonitor
from local_app.monitoring.temperature_monitor import TemperatureMonitor
from local_app.monitoring.exchange_rate_monitor import ExchangeRateMonitor
from local_app.utils.calculator import open_calculator

logger = logging.getLogger(__name__)

class Application:
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/config.json relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "config", "config.json")
        self.load_config(config_path)
        self._setup_monitors()
        self._stop = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def load_config(self, config_path: str):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def _handle_server_response(self, response: Dict[str, Any]):
        """Central handler for all server responses"""
        try:
            if response.get("open_calculator", False):
                open_calculator()
        except Exception as e:
            logger.error(f"Error handling server response: {e}")

    def _setup_monitors(self):
        """Initialize all monitors"""
        base_url = self.config["api"]["base_url"]
        
        self.metrics_monitor = MetricsMonitor(
            base_url=base_url,
            poll_interval=self.config["intervals"]["metrics"],
            response_callback=self._handle_server_response
        )
        
        self.temperature_monitor = TemperatureMonitor(
            base_url=base_url,
            poll_interval=self.config["intervals"]["temperature"]
        )
        
        self.exchange_rate_monitor = ExchangeRateMonitor(
            base_url=base_url,
            poll_interval=self.config["intervals"]["exchange_rate"]
        )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self._stop = True

    def start(self):
        """Start all monitors"""
        logger.info("Starting application")
        self.metrics_monitor.start()
        self.temperature_monitor.start()
        self.exchange_rate_monitor.start()

    def stop(self):
        """Stop all monitors"""
        logger.info("Stopping application")
        self.metrics_monitor.stop()
        self.temperature_monitor.stop()
        self.exchange_rate_monitor.stop()

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        app = Application()
        app.start()
        
        # Keep the main thread running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        app.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
