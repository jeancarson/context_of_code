import logging
import os
import signal
import sys
import time
import json
from typing import List
from pathlib import Path
import requests

from devices.temperature.service import TemperatureService
from devices.exchange_rate.service import ExchangeRateService
from devices.local.service import LocalMetricsService
from devices.base_device import MetricDTO

logger = logging.getLogger(__name__)

class Application:
    def __init__(self):
        self._load_config()
        self._setup_devices()
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

    def _setup_devices(self):
        """Initialize device services"""
        base_url = self.config['api']['base_url']
        
        self.temperature_service = TemperatureService(
            base_url=base_url,
            poll_interval=self.config['intervals']['temperature']
        )
        
        self.exchange_rate_service = ExchangeRateService(
            base_url=base_url,
            poll_interval=self.config['intervals']['exchange_rate']
        )
        
        self.local_metrics_service = LocalMetricsService(
            base_url=base_url,
            poll_interval=self.config['intervals']['metrics']
        )

    def _handle_signal(self, signum, frame):
        """Handle termination signals"""
        logger.info("Received signal %d, shutting down...", signum)
        self._running = False

    def collect_metrics(self) -> List[MetricDTO]:
        """Collect metrics from all devices"""
        metrics = []
        
        # Temperature metric
        temp = self.temperature_service.get_current_temperature()
        metrics.append(self.temperature_service.create_metric(temp))
        
        # Exchange rate metric
        rate = self.exchange_rate_service.get_current_rate()
        metrics.append(self.exchange_rate_service.create_metric(rate))
        
        # Local system metrics
        metrics.extend(self.local_metrics_service.get_current_metrics())
        
        return metrics

    def run(self):
        """Main application loop"""
        try:
            while self._running:
                try:
                    metrics = self.collect_metrics()
                    
                    # Send metrics to server
                    try:
                        response = requests.post(
                            f"{self.config['api']['base_url']}/api/metrics",
                            json={
                                "metrics": [
                                    {
                                        "type": m.type,
                                        "value": m.value,
                                        "uuid": str(m.uuid) if m.uuid else None,
                                        "timestamp": m.timestamp
                                    } for m in metrics
                                ]
                            }
                        )
                        response.raise_for_status()
                        logger.info(f"Successfully sent {len(metrics)} metrics to server")
                    except Exception as e:
                        logger.error(f"Failed to send metrics to server: {e}")
                    
                    time.sleep(min(
                        self.config['intervals']['metrics'],
                        self.config['intervals']['temperature'],
                        self.config['intervals']['exchange_rate']
                    ))
                except Exception as e:
                    logger.error(f"Error collecting metrics: {e}")
                    time.sleep(5)  # Wait before retrying
                
        except Exception as e:
            logger.error("Error in main loop: %s", e)
            
        finally:
            self._cleanup()

    def _cleanup(self):
        """Cleanup resources"""
        logger.info("Shutting down application...")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
