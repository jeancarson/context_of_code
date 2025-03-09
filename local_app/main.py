import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import asyncio
import json
import logging
import signal
import time
from datetime import datetime
from typing import List, Dict
import aiohttp

from devices.temperature.service import TemperatureService
from devices.exchange_rate.service import ExchangeRateService
from devices.local.service import LocalMetricsService
from services.calculator import CalculatorService
from devices.base_device import MetricDTO
from utils.calculator import open_calculator
from metrics_sdk import MetricsAPI, MetricSnapshotDTO, MetricValueDTO
from lib_utils.logger import Logger
from local_app.config.config import Config

logger = logging.getLogger(__name__)

class Application:
    def __init__(self):
        self._load_config()
        self._setup_devices()
        self._running = True
        self._event_loop = None
        self._metrics_queue = []  # Queue to store metrics before sending
        self._last_calculator_state = None  # Track last calculator state
        # Use a persistent storage directory in the application directory
        metrics_storage = os.path.join(os.path.dirname(__file__), 'metrics_storage')
        self._metrics_api = MetricsAPI(self.config['api']['base_url'], storage_dir=metrics_storage)
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
        """Task to periodically send queued metrics"""
        while self._running:
            try:
                if self._metrics_queue:
                    metrics = self._metrics_queue.copy()
                    self._metrics_queue.clear()
                    await self.send_metrics(metrics)
            except Exception as e:
                logger.error(f"Error in send_metrics_task: {e}")
            finally:
                await asyncio.sleep(self.config['intervals']['send'])

    async def send_metrics(self, metrics: List[MetricDTO]) -> None:
        """Send metrics to API using the SDK"""
        if not metrics:
            return

        # Create a snapshot for each individual metric
        for metric in metrics:
            device = self._get_device_for_metric(metric.type)
            if not device or not device.uuid:
                logger.error(f"No valid device found for metric type: {metric.type}")
                continue

            # Create individual snapshot for this metric
            snapshot = MetricSnapshotDTO(
                device_uuid=str(device.uuid),
                aggregator_uuid=str(device.aggregator_uuid),
                client_timestamp=datetime.fromtimestamp(metric.created_at or time.time()).isoformat(),
                client_timezone_minutes=-time.timezone // 60,
                metrics=[MetricValueDTO(
                    type=metric.type,
                    value=metric.value
                )]
            )

            await self._metrics_api.send_metrics(snapshot)  # Queue the snapshot

        # After queueing all snapshots, try to flush the queue
        await self._metrics_api.flush_queue()

    def _get_device_for_metric(self, metric_type: str):
        """Get device instance for metric type"""
        device_map = {
            'Temperature': self.temperature_service,
            'GPBtoEURexchangeRate': self.exchange_rate_service,
            'CPUPercent': self.local_metrics_service,
            'RAMPercent': self.local_metrics_service,
            'DiskPercent': self.local_metrics_service,
            'local': self.local_metrics_service
        }
        device = device_map.get(metric_type)
        if device:
            logger.debug(f"Found device for metric type {metric_type}: uuid={device.uuid}, aggregator={device.aggregator_uuid}")
        return device

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
        """Check if calculator needs to be opened"""
        connection_error_logged = False  # Track if we've already logged a connection error
        
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.config['api']['base_url']}/check-calculator") as response:
                        if response.status == 200:
                            data = await response.json()
                            current_state = data.get('calculator_state')
                            
                            # Only open calculator when state changes
                            if current_state != self._last_calculator_state and self._last_calculator_state is not None:
                                open_calculator()
                                logger.info("Opening calculator due to state change")
                            
                            self._last_calculator_state = current_state
                            connection_error_logged = False  # Reset error flag on successful connection
                        else:
                            if not connection_error_logged:
                                logger.info(f"Calculator check returned unexpected status {response.status}")
                                connection_error_logged = True
                                
            except aiohttp.ClientError as e:
                if not connection_error_logged:
                    logger.info("Calculator service unavailable - web app appears to be offline")
                    connection_error_logged = True
            except Exception as e:
                if not connection_error_logged:
                    logger.warning(f"Unexpected error in calculator check: {str(e)}")
                    connection_error_logged = True
                    
            await asyncio.sleep(1)  # Poll every second

    async def initialize(self):
        """Initialize async components"""
        await self._metrics_api.connect()  # This will also load the persisted queue

    async def run_async(self):
        """Async main loop"""
        logger.info("Starting async loop...")
        try:
            # First initialize async components
            await self.initialize()
            
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
                self.check_calculator()  # Add calculator check task
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
    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    config = Config(config_path)
    
    # Initialize logging using the shared logger
    global logger
    logger = Logger.setup_from_config("Local App", config)
    
    # Set specific loggers to appropriate levels
    logging.getLogger('metrics_sdk.api').setLevel(logging.INFO)  # Keep SDK at INFO to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)  # Reduce HTTP client noise
    logging.getLogger('asyncio').setLevel(logging.WARNING)  # Reduce async noise
    
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
