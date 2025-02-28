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
from services.calculator import CalculatorService
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

            logger.info("Initializing calculator service...")
            self.calculator_service = CalculatorService()
            
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"Error setting up services: {e}")
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
        """Send metrics to the server"""
        if not metrics:
            return

        async with aiohttp.ClientSession() as session:
            try:
                metrics_data = {
                    "metrics": [{
                        "type": m.type,
                        "value": m.value,
                        "device_id": str(m.uuid) if m.uuid else None,
                        "created_at": str(datetime.now()) if m.created_at is None else str(m.created_at)
                    } for m in metrics]
                }
                
                url = f"{self.config['api']['base_url']}/api/metrics"
                logger.info(f"Sending metrics to URL: {url}")
                async with session.post(url, json=metrics_data) as response:
                    response_data = await response.json()
                    logger.info(f"Server response: {response_data}")
                    
                    # Check for calculator flag
                    logger.info("Checking calculator flag...")
                    if self.calculator_service.check_calculator_flag(response_data):
                        logger.info("Calculator flag is True, opening calculator...")
                        self.calculator_service.open_calculator()
                    else:
                        logger.info("Calculator flag is False, not opening calculator")
                        
                    return response_data
            except Exception as e:
                logger.error(f"Error sending metrics: {str(e)}")
                return None

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

    async def check_calculator(self):
        """Check if calculator should be opened"""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.config['api']['base_url']}/toggle-calculator"
                logger.info(f"Checking calculator at URL: {url}")
                async with session.post(url) as response:
                    response_data = await response.json()
                    logger.info(f"Calculator response: {response_data}")
                    
                    if self.calculator_service.check_calculator_flag(response_data):
                        logger.info("Opening calculator...")
                        self.calculator_service.open_calculator()
            except Exception as e:
                logger.error(f"Error checking calculator: {str(e)}")

    async def check_calculator_task(self):
        """Task to check calculator flag periodically"""
        while self._running:
            try:
                url = f"{self.config['api']['base_url']}/check-calculator"
                async with aiohttp.ClientSession() as session:
                    async with session.post(url) as response:
                        response_data = await response.json()
                        logger.info(f"Calculator check response: {response_data}")
                        
                        if self.calculator_service.check_calculator_flag(response_data):
                            logger.info("Opening calculator...")
                            self.calculator_service.open_calculator()
                
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error checking calculator: {str(e)}")
                await asyncio.sleep(1)

    async def run_async(self):
        """Async main loop"""
        logger.info("Starting async loop...")
        try:
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
                self.send_metrics_task(),
                self.check_calculator_task()
            ]
            
            # Run all tasks concurrently
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in async loop: {e}")
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
