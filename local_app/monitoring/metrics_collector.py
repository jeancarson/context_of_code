import time
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime
import json
import threading
from queue import Queue
import os
from local_app.monitoring.system_monitor import SystemMonitor
from local_app.models.system_metrics import SystemMetrics
from lib.constants import StatusCode

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self, api_url: str, poll_interval: int = 30):
        """Initialize the metrics collector
        
        Args:
            api_url: URL of the metrics API
            poll_interval: How often to collect metrics (in seconds)
        """
        self.api_url = api_url
        self.poll_interval = poll_interval
        self.system_monitor = SystemMonitor()
        self._stop_event = threading.Event()
        self._metrics_queue: Queue = Queue()
        self._setup_storage()
        
    def _setup_storage(self):
        """Setup local storage for metrics"""
        self.storage_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _store_metrics(self, metrics: SystemMetrics):
        """Store metrics locally"""
        filename = os.path.join(
            self.storage_dir,
            f"metrics_{metrics.timestamp.strftime('%Y%m%d')}.jsonl"
        )
        with open(filename, "a") as f:
            f.write(metrics.json() + "\n")
            
    def _send_metrics(self, metrics: SystemMetrics) -> bool:
        """Send metrics to the API
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Convert to dict and ensure datetime is serialized
            metrics_dict = json.loads(metrics.json())
            logger.info(f"Sending metrics to API: {metrics_dict}")
            
            response = requests.post(
                f"{self.api_url}/metrics",
                json=metrics_dict,
                headers=headers,
                verify=True
            )
            
            logger.info(f"API Response: {response.status_code} - {response.text}")
            
            if response.status_code == StatusCode.CREATED:
                logger.info(f"Successfully sent metrics to {self.api_url}")
                response_data = response.json()
                
                # Handle any server commands or config updates
                if "command" in response_data:
                    logger.info(f"Received command: {response_data['command']}")
                    # Handle command here if needed
                    
                if "config" in response_data:
                    logger.info(f"Received config update: {response_data['config']}")
                    # Update config here if needed
                    
                return True
            else:
                logger.error(f"Failed to send metrics. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error when sending metrics: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error when sending metrics: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send metrics: {e}")
            return False
            
    def _collect_metrics(self):
        """Collect and process metrics"""
        while not self._stop_event.is_set():
            try:
                # Get metrics
                metrics = self.system_monitor.get_metrics()
                
                # Store locally
                self._store_metrics(metrics)
                
                # Try to send to API
                if not self._send_metrics(metrics):
                    # If failed, add to queue for retry
                    self._metrics_queue.put(metrics)
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                
            time.sleep(self.poll_interval)
            
    def _retry_failed_metrics(self):
        """Retry sending failed metrics"""
        while not self._stop_event.is_set():
            try:
                if not self._metrics_queue.empty():
                    metrics = self._metrics_queue.get()
                    if self._send_metrics(metrics):
                        logger.info("Successfully resent queued metrics")
                    else:
                        # Put back in queue if failed
                        self._metrics_queue.put(metrics)
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
            
            time.sleep(5)  # Check every 5 seconds
            
    def start(self):
        """Start collecting metrics"""
        logger.info("Starting metrics collection")
        
        # Start collection thread
        self._collection_thread = threading.Thread(
            target=self._collect_metrics,
            daemon=True
        )
        self._collection_thread.start()
        
        # Start retry thread
        self._retry_thread = threading.Thread(
            target=self._retry_failed_metrics,
            daemon=True
        )
        self._retry_thread.start()
        
    def stop(self):
        """Stop collecting metrics"""
        logger.info("Stopping metrics collection")
        self._stop_event.set()
        self._collection_thread.join()
        self._retry_thread.join()
