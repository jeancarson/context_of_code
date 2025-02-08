import time
import logging
import requests
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from .system_monitor import SystemMonitor
from .config import Config
import threading
from queue import Queue
import json

logger = logging.getLogger(__name__)

@dataclass
class PollConfig:
    """Configuration for the metrics poller"""
    server_url: str
    poll_interval_seconds: int = 30
    retry_interval_seconds: int = 5
    max_retries: int = 3

class MetricsPoller:
    def __init__(self, config: PollConfig):
        """Initialize the metrics poller with configuration"""
        self.config = config
        self.system_monitor = SystemMonitor()
        self._stop_event = threading.Event()
        self._command_queue: Queue = Queue()
        self._registered_commands: Dict[str, Callable] = {}
        
    def register_command(self, command_name: str, handler: Callable):
        """Register a command that can be triggered by the server"""
        self._registered_commands[command_name] = handler
        logger.info(f"Registered command handler for: {command_name}")

    def _send_metrics(self) -> Optional[Dict[str, Any]]:
        """Send metrics to the server and return the response"""
        try:
            metrics = self.system_monitor.get_metrics()
            response = requests.post(
                f"{self.config.server_url}/metrics",
                json=metrics.dict(),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to send metrics. Status: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending metrics: {e}")
            return None

    def _handle_server_response(self, response: Dict[str, Any]):
        """Handle any commands or configurations sent by the server"""
        if not response:
            return
            
        # Check for commands
        if "command" in response:
            command = response["command"]
            if command in self._registered_commands:
                try:
                    # Add command to queue for async execution
                    self._command_queue.put(command)
                    logger.info(f"Queued command: {command}")
                except Exception as e:
                    logger.error(f"Error queueing command {command}: {e}")
            else:
                logger.warning(f"Received unknown command: {command}")

        # Check for configuration updates
        if "config" in response:
            try:
                new_config = response["config"]
                # Update polling interval if provided
                if "poll_interval_seconds" in new_config:
                    self.config.poll_interval_seconds = new_config["poll_interval_seconds"]
                    logger.info(f"Updated polling interval to {self.config.poll_interval_seconds}s")
            except Exception as e:
                logger.error(f"Error processing config update: {e}")

    def _process_command_queue(self):
        """Process any pending commands"""
        while not self._command_queue.empty():
            command = self._command_queue.get()
            try:
                handler = self._registered_commands[command]
                handler()
                logger.info(f"Executed command: {command}")
            except Exception as e:
                logger.error(f"Error executing command {command}: {e}")
            finally:
                self._command_queue.task_done()

    def start(self):
        """Start the polling loop"""
        logger.info("Starting metrics poller...")
        
        while not self._stop_event.is_set():
            retry_count = 0
            while retry_count < self.config.max_retries:
                response = self._send_metrics()
                if response:
                    self._handle_server_response(response)
                    break
                retry_count += 1
                if retry_count < self.config.max_retries:
                    logger.info(f"Retrying in {self.config.retry_interval_seconds} seconds...")
                    time.sleep(self.config.retry_interval_seconds)
            
            # Process any pending commands
            self._process_command_queue()
            
            # Wait for next polling interval
            self._stop_event.wait(self.config.poll_interval_seconds)
        
        logger.info("Metrics poller stopped")

    def stop(self):
        """Stop the polling loop"""
        logger.info("Stopping metrics poller...")
        self._stop_event.set()

# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create configuration
    config = PollConfig(
        server_url="https://jeancarson.pythonanywhere.com",
        poll_interval_seconds=30
    )
    
    # Create and start poller
    poller = MetricsPoller(config)
    
    # Register example command
    def example_command():
        logger.info("Executing example command!")
    
    poller.register_command("example_command", example_command)
    
    try:
        poller.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        poller.stop()
