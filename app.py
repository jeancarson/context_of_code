import os
import datetime
from flask import Flask, jsonify, send_from_directory, render_template, request
from lib_config.config import Config
from system_monitor import SystemMonitor
import sys
import logging
from models.device_metrics import DeviceMetrics
import requests
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import threading
import time
import psutil
from block_timer import BlockTimer
from metrics_cache import MetricsCache

class App:
    def __init__(self):
        # Compute root directory once and use it throughout the file
        self.root_dir = os.path.dirname(os.path.abspath(__file__))

        # Load configuration
        self.config = Config(os.path.join(self.root_dir, 'config.json'))

        # Initialize Flask app with configuration
        app = Flask(__name__)
        app.config['DEBUG'] = self.config.debug
        app.config['SECRET_KEY'] = self.config.flask.secret_key

        self.logger = logging.getLogger(__name__)
        self.config.setup_logging()

        # Initialize system monitor
        self.system_monitor = SystemMonitor()

        self.logger.info("Application initialized with configuration: %s", self.config)

        # Define function to fetch fresh metrics
        def fetch_device_metrics(self):
            # Get metrics directly from the system
            battery = psutil.sensors_battery()
            battery_percent = battery.percent if battery else 0.0
            memory = psutil.virtual_memory()
            
            metrics = {
                'battery_percent': battery_percent,
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'memory_total_mb': memory.total / (1024 * 1024),
                'timestamp': datetime.datetime.now().isoformat()
            }
            return DeviceMetrics(**metrics)

        # Initialize metrics cache with our specific metrics fetcher
        self.metrics_cache = MetricsCache[DeviceMetrics](
            fetch_func=fetch_device_metrics,
            cache_duration_seconds=30
        )

        self.logger.info("Configured server is: %s", self.config.database.host)  # "localhost"

        self.logger.debug("This is a sample debug message")
        self.logger.info("This is a sample info message")
        self.logger.warning("This is a sample warning message")
        self.logger.error("This is a sample error message")
        self.logger.critical("This is a sample critical message")

    @app.route("/")
    def hello(self):
        with BlockTimer("Hello World Request", self.logger):
            self.logger.info("Hello World!")
            my_html_path = os.path.join(self.root_dir, 'my.html')
            return open(my_html_path).read()

    @app.route("/local_stats")
    def local_stats(self):
        with BlockTimer("Get Local Stats Request", self.logger):
            try:
                metrics = self.fetch_device_metrics()
                return jsonify(metrics.dict())
            except Exception as e:
                self.logger.error(f"Error getting system metrics: {e}")
                return jsonify({"error": str(e)}), 500


    def run():
        # Only run the Flask development server if we're not on PythonAnywhere
        if not os.getenv('PYTHONANYWHERE_SITE'):
            try:
                self.logger.info("Starting Flask web server on port %s", self.config.flask.port)
                app.run(
                    host=self.config.flask.host,
                    port=self.config.flask.port
                )
            except Exception as e:
                self.logger.exception("Application failed with error: %s", str(e))
                sys.exit(-1)
        else:
            self.logger.info("Running on PythonAnywhere, not starting Flask server")

if __name__ == "__main__":
    app = App()
    app.run()
    app.logger.info("Application completed successfully")