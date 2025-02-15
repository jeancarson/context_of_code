import os
import json
import logging
from local_app.monitoring.metrics_collector import MetricsCollector

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    with open(config_path) as f:
        return json.load(f)

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main entry point for the metrics collector"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        
        # Create and start metrics collector
        collector = MetricsCollector(
            api_url=config["api_url"],
            poll_interval=config.get("poll_interval", 30)
        )
        collector.start()
        
        # Keep the main thread alive
        try:
            while True:
                input()  # Wait for Ctrl+C
        except KeyboardInterrupt:
            logger.info("Stopping metrics collection...")
            collector.stop()
            
    except Exception as e:
        logger.error(f"Failed to start metrics collection: {e}")
        
if __name__ == "__main__":
    main()
