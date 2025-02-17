import json
import os
import signal
import sys
from local_app.monitoring.system_monitor import SystemMonitor
from local_app.monitoring.remote_metrics import RemoteMetricsStore

def load_config():
    """Load configuration from JSON file"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

def main():
    """Main entry point for the monitoring application"""
    try:
        # Load configuration
        config = load_config()
        
        # Create and start system monitor
        system_monitor = SystemMonitor(
            metrics_url=config["metrics_url"],
            poll_interval=config.get("system_poll_interval", 60)  # Default to 1 minute
        )
        system_monitor.start()

        def signal_handler(signum, frame):
            """Handle shutdown signals"""
            print("\nShutting down...")
            system_monitor.stop()
            sys.exit(0)

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep the main thread alive
        signal.pause()

    except Exception as e:
        print(f"Error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
