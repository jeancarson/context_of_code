import logging
import threading
import time
import json
import os
from queue import Queue
from typing import Optional, Callable
import requests
from local_app.services.system_service import SystemService
from local_app.models.metrics import Metrics

logger = logging.getLogger(__name__)

class MetricsMonitor:
    """Monitor for collecting and sending system metrics"""
    
    def __init__(self, base_url: str, poll_interval: int = 30, response_callback: Optional[Callable[[dict], None]] = None):
        """Initialize the metrics monitor
        
        Args:
            base_url: URL of the metrics API
            poll_interval: How often to collect metrics (in seconds)
            response_callback: Optional callback for handling server responses
        """
        self.api_url = base_url
        self.poll_interval = poll_interval
        self.system_service = SystemService()
        self.response_callback = response_callback
        self._stop_event = threading.Event()
        self._metrics_queue = Queue()
        self._setup_storage()
        
    def _setup_storage(self):
        """Setup local storage for metrics"""
        self.storage_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _store_metrics(self, metrics: Metrics):
        """Store metrics locally"""
        filename = os.path.join(
            self.storage_dir,
            f"metrics_{metrics.timestamp.strftime('%Y%m%d')}.jsonl"
        )
        with open(filename, "a") as f:
            json.dump(metrics.to_dict(), f)
            f.write("\n")
            
    def _send_metrics(self, metrics: Metrics) -> bool:
        """Send metrics to the API"""
        try:
            metrics_dict = metrics.to_dict()
            logger.info(f"Sending metrics to API: {metrics_dict}")
            
            response = requests.post(
                f"{self.api_url}/metrics",
                json=metrics_dict,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                verify=True
            )
            
            if response.status_code == 201:  # Created
                logger.info(f"Successfully sent metrics to {self.api_url}")
                if self.response_callback:
                    self.response_callback(response.json())
                return True
            else:
                logger.error(f"Failed to send metrics. Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send metrics: {e}")
            return False
            
    def _collect_and_send(self):
        """Collect and process metrics"""
        while not self._stop_event.is_set():
            try:
                # Get metrics
                metrics = self.system_service.get_metrics()
                
                # Store locally
                self._store_metrics(metrics)
                
                # Try to send to API
                if not self._send_metrics(metrics):
                    # If failed, add to queue for retry
                    self._metrics_queue.put(metrics)
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                
            time.sleep(self.poll_interval)
            
    def _retry_failed(self):
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
            target=self._collect_and_send,
            daemon=True
        )
        self._collection_thread.start()
        
        # Start retry thread
        self._retry_thread = threading.Thread(
            target=self._retry_failed,
            daemon=True
        )
        self._retry_thread.start()
        
    def stop(self):
        """Stop collecting metrics"""
        logger.info("Stopping metrics collection")
        self._stop_event.set()
        self._collection_thread.join()
        self._retry_thread.join()
