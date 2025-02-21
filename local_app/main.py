import logging
import os
import signal
import sys
import time
from pathlib import Path

from local_app.monitoring.metrics_monitor import MetricsMonitor
from local_app.monitoring.temperature_monitor import TemperatureMonitor
from local_app.monitoring.exchange_rate_monitor import ExchangeRateMonitor
from local_app.monitoring.calculator_monitor import CalculatorMonitor
from local_app.services.system_service import SystemService
import json

logger = logging.getLogger(__name__)

class Application:
    def __init__(self):
        self.system_service = SystemService()
        self._load_config()
        self._setup_monitors()
        self._running = True
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _load_config(self):
        """Load configuration from file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path) as f:
                self.config = json.load(f)
                logger.info("Loaded configuration from %s", config_path)
        except Exception as e:
            logger.error("Error loading config: %s", e)
            sys.exit(1)

    def _setup_monitors(self):
        """Initialize and start monitoring threads"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        base_url = self.config['api']['base_url']
        
        self.metrics_monitor = MetricsMonitor(
            base_url=base_url,
            poll_interval=self.config['intervals']['metrics']
        )
        
        self.temperature_monitor = TemperatureMonitor(
            base_url=base_url,
            config_path=config_path,
            poll_interval=self.config['intervals']['temperature']
        )
        
        self.exchange_rate_monitor = ExchangeRateMonitor(
            base_url=base_url,
            config_path=config_path,
            poll_interval=self.config['intervals']['exchange_rate']
        )

        self.calculator_monitor = CalculatorMonitor(
            base_url=base_url,
            poll_interval=5  # Check every 5 seconds
        )

    def _handle_signal(self, signum, frame):
        """Handle termination signals"""
        logger.info("Received signal %d, shutting down...", signum)
        self._running = False

    def run(self):
        """Start all monitoring threads"""
        try:
            self.metrics_monitor.start()
            self.temperature_monitor.start()
            self.exchange_rate_monitor.start()
            self.calculator_monitor.start()
            
            # Keep main thread alive
            while self._running:
                time.sleep(1)
                
        except Exception as e:
            logger.error("Error in main loop: %s", e)
            
        finally:
            self._cleanup()

    def _cleanup(self):
        """Stop all monitoring threads"""
        logger.info("Stopping monitors...")
        self.metrics_monitor.stop()
        self.temperature_monitor.stop()
        self.exchange_rate_monitor.stop()
        self.calculator_monitor.stop()
        logger.info("All monitors stopped")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
