import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import List
import aiohttp

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
        self._event_loop = None
        self._metrics_queue = []  # Queue to store metrics before sending
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _load_config(self):
        """Load configuration from file"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            # Add a send interval if not present
            if 'send_interval' not in self.config['intervals']:
                self.config['intervals']['send'] = 30  # Default 30 seconds
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            sys.exit(1)

    def _setup_devices(self):
        """Initialize device services"""
        try:
            logger.info("Initializing temperature service...")
            self.temperature_service = TemperatureService(
                base_url=self.config['api']['base_url'],
                poll_interval=self.config['intervals']['temperature']
            )
            
            logger.info("Initializing exchange rate service...")
            self.exchange_rate_service = ExchangeRateService(
                base_url=self.config['api']['base_url'],
                poll_interval=self.config['intervals']['exchange_rate']
            )
            
            logger.info("Initializing local metrics service...")
            self.local_metrics_service = LocalMetricsService(
                base_url=self.config['api']['base_url'],
                poll_interval=self.config['intervals']['local']
            )
            
            logger.info("All devices initialized successfully")
        except Exception as e:
            logger.error(f"Error setting up devices: {e}")
            sys.exit(1)

    async def collect_service_metrics(self, service, interval):
        """Collect metrics from a specific service on its own interval"""
        while self._running:
            try:
                metrics = service.get_current_metrics()
                if metrics:
                    self._metrics_queue.extend(metrics)
                    logger.info(f"Added {len(metrics)} metrics from {service.__class__.__name__} to queue")
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error collecting metrics from {service.__class__.__name__}: {str(e)}")
                if hasattr(e, '__traceback__'):
                    import traceback
                    logger.error(f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}")
                await asyncio.sleep(1)

    async def send_metrics_task(self):
        """Task to send queued metrics on a fixed interval"""
        while self._running:
            try:
                if self._metrics_queue:
                    logger.info(f"Sending {len(self._metrics_queue)} metrics from queue")
                    await self.send_metrics(self._metrics_queue)
                    self._metrics_queue = []  # Clear the queue after sending
                else:
                    logger.info("No metrics in queue to send")
                await asyncio.sleep(self.config['intervals']['send'])
            except Exception as e:
                logger.error(f"Error in send_metrics_task: {str(e)}")
                if hasattr(e, '__traceback__'):
                    import traceback
                    logger.error(f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}")
                await asyncio.sleep(1)

    async def send_metrics(self, metrics: List[MetricDTO]):
        """Send metrics to server"""
        try:
            metrics_to_send = []
            for metric in metrics:
                device_id = await self.get_device_id(metric.type)
                if not device_id:
                    logger.error(f"No device ID for metric type {metric.type}")
                    continue
                
                # Remove dashes from UUID to match database format
                device_id = device_id.replace('-', '')
                
                metrics_to_send.append({
                    "type": metric.type,
                    "value": metric.value,
                    "device_id": device_id,
                    "created_at": str(datetime.now())
                })
            
            if not metrics_to_send:
                logger.error("No metrics to send - all device IDs missing")
                return
            
            # Send metrics to server
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.config['api']['base_url']}/api/metrics",
                        json={"metrics": metrics_to_send}
                    ) as response:
                        data = await response.json()
                        if response.status != 200:
                            logger.error(f"Error sending metrics: {response.status}")
                            logger.error(f"Server response: {data}")
                            if response.status == 500:
                                logger.error(f"Request data that caused error: {metrics_to_send}")
                        elif data.get('errors'):
                            logger.warning(f"Some metrics failed: {data['errors']}")
                        else:
                            logger.debug(f"Successfully sent {len(metrics_to_send)} metrics")
            except Exception as e:
                logger.error(f"Error sending metrics to server: {str(e)}")
                if hasattr(e, '__traceback__'):
                    import traceback
                    logger.error(f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}")
        except Exception as e:
            logger.error(f"Error preparing metrics to send: {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}")

    async def get_device_id(self, metric_type: str) -> str:
        """Get device ID for metric type, using the appropriate device's UUID"""
        # Map metric types to their devices
        device_map = {
            'Temperature': self.temperature_service,
            'GPBtoEURexchangeRate': self.exchange_rate_service,
            'CPUPercent': self.local_metrics_service,
            'RAMPercent': self.local_metrics_service,
            'DiskPercent': self.local_metrics_service,
            'local': self.local_metrics_service  # Add mapping for local device type
        }
        
        device = device_map.get(metric_type)
        if not device:
            logger.error(f"No device found for metric type: {metric_type}")
            return None
            
        # Use the device's UUID directly
        if device.uuid:
            return str(device.uuid)
            
        logger.error(f"Device {device.device_name} has no UUID")
        return None

    async def run_async(self):
        """Async main loop"""
        logger.info("Starting async loop...")
        try:
            # Create tasks for each service
            tasks = [
                self.collect_service_metrics(
                    self.temperature_service,
                    self.config['intervals']['temperature']
                ),
                self.collect_service_metrics(
                    self.exchange_rate_service,
                    self.config['intervals']['exchange_rate']
                ),
                self.collect_service_metrics(
                    self.local_metrics_service,
                    self.config['intervals']['local']
                ),
                self.send_metrics_task()
            ]
            
            # Run all tasks concurrently
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in run_async: {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}")

    def _cleanup(self):
        """Cleanup resources"""
        logger.info("Shutting down application...")
        if self._event_loop:
            self._event_loop.close()

    def _handle_signal(self, signum, frame):
        """Handle termination signals"""
        logger.info("Received signal %d, shutting down...", signum)
        self._running = False

    def run(self):
        """Main application loop"""
        logger.info("Starting application...")
        try:
            # Create a new event loop
            if self._event_loop is None:
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)
            
            # Run the async loop
            self._event_loop.run_until_complete(self.run_async())
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}")
        finally:
            self._cleanup()

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
