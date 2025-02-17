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
from local_app.monitoring.metrics_collector import MetricsCollector
from local_app.collectors.github_collector import GitHubCollector
from local_app.services.github_stats_service import GitHubStatsService
from local_app.models.github_stats import GitHubStats

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from JSON file"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)

class GitHubMonitor:
    def __init__(self, base_url: str, github_config: dict):
        self.github_service = GitHubStatsService(github_config.get('token'))
        self.base_url = base_url
        self.poll_interval = github_config.get('poll_interval', 3600)  # Default to 1 hour
        self._running = False
        self._retry_queue = Queue()
        self._retry_thread = None
    
    def collect_and_send_data(self):
        """Collect GitHub stats and send to server"""
        try:
            # Collect the data using GitHub service
            stats = self.github_service.get_country_stats()
            if not stats:
                logger.warning("No GitHub stats available")
                return
            
            # Convert stats to proper model objects
            stats_models = [
                GitHubStats(
                    country_code=stat['country_code'],
                    country_name=stat['country_name'],
                    population=stat['population'],
                    commit_count=stat['commit_count'],
                    commits_per_capita=stat['commits_per_capita'],
                    timestamp=datetime.fromisoformat(stat['timestamp'])
                ) for stat in stats
            ]
            
            # Send to server
            response = requests.post(
                f"{self.base_url}/github_stats",
                json={'stats': [stat.to_dict() for stat in stats_models]},
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info("Successfully sent GitHub stats")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending GitHub stats: {e}")
            # Queue for retry
            self._retry_queue.put(stats)
        except Exception as e:
            logger.error(f"Error collecting GitHub stats: {e}")
    
    def _retry_failed_requests(self):
        """Retry failed requests"""
        while self._running:
            try:
                if not self._retry_queue.empty():
                    stats = self._retry_queue.get()
                    response = requests.post(
                        f"{self.base_url}/github_stats",
                        json={'stats': [stat.to_dict() for stat in stats]},
                        headers={'Content-Type': 'application/json'}
                    )
                    response.raise_for_status()
                    logger.info("Successfully resent queued stats")
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
                self._retry_queue.put(stats)  # Put back in queue
    
    def start(self):
        """Start the monitoring process"""
        self._running = True
        
        # Start retry thread
        self._retry_thread = threading.Thread(target=self._retry_failed_requests)
        self._retry_thread.daemon = True
        self._retry_thread.start()
        
        # Main collection loop
        while self._running:
            try:
                self.collect_and_send_data()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait a bit before retrying
    
    def stop(self):
        """Stop the monitoring process"""
        self._running = False
        if self._retry_thread:
            self._retry_thread.join()

def main():
    """Main entry point for the monitoring application"""
    try:
        # Load configuration
        config = load_config()
        
        # Initialize GitHub monitor
        github_monitor = GitHubMonitor(
            base_url=config['api_url'],
            github_config=config['github']
        )
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            logger.info("Shutting down...")
            github_monitor.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring
        github_monitor.start()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
