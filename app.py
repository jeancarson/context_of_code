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

# Compute root directory once and use it throughout the file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load configuration
config = Config(os.path.join(ROOT_DIR, 'config.json'))

# Initialize Flask app with configuration
app = Flask(__name__)
app.config['DEBUG'] = config.debug
app.config['SECRET_KEY'] = config.flask.secret_key

logger = logging.getLogger(__name__)
config.setup_logging()

# Initialize system monitor
system_monitor = SystemMonitor()

# Define function to fetch fresh metrics
def fetch_device_metrics():
    if not os.getenv('PYTHONANYWHERE_SITE'):
        # When running locally, get metrics directly
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
    else:
        # When on PythonAnywhere, fetch from ngrok tunnel
        logger.info("Running on PythonAnywhere, fetching from ngrok tunnel")
        response = requests.get('https://1eff-80-233-75-158.ngrok-free.app/metrics')
        response.raise_for_status()
        metrics_data = response.json()
        return DeviceMetrics(**metrics_data)

# Initialize metrics cache with our specific metrics fetcher
metrics_cache = MetricsCache[DeviceMetrics](
    fetch_func=fetch_device_metrics,
    cache_duration_seconds=30
)

logger.info("Configured server is: %s", config.database.host)  # "localhost"

logger.debug("This is a sample debug message")
logger.info("This is a sample info message")
logger.warning("This is a sample warning message")
logger.error("This is a sample error message")
logger.critical("This is a sample critical message")

@app.route("/")
def hello():
    with BlockTimer("Hello World Request", logger):
        logger.info("Hello World!")
        my_html_path = os.path.join(ROOT_DIR, 'my.html')
        return open(my_html_path).read()

@app.route("/local_stats")
def local_stats():
    with BlockTimer("Get Local Stats Request", logger):
        try:
            # When running locally, get metrics directly
            if not os.getenv('PYTHONANYWHERE_SITE'):
                logger.info("Running locally, getting direct system metrics")
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
                device_metrics = DeviceMetrics(**metrics)
            else:
                # When on PythonAnywhere, fetch from local publisher
                logger.info("Running on PythonAnywhere, fetching from local metrics publisher")
                # Replace with your actual local machine's public IP or domain
                response = requests.get('http://80.233.42.56:5001/metrics')
                response.raise_for_status()
                metrics_data = response.json()
                device_metrics = DeviceMetrics(**metrics_data)
            
            # For API calls that expect JSON
            if request.headers.get('Accept') == 'application/json':
                return device_metrics.to_json(indent=2)
            
            # For browser views, render the HTML template
            return render_template('metrics.html', metrics=device_metrics)
            
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to fetch metrics: {str(e)}"}), 500

# Add this route to serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(os.path.join(ROOT_DIR, 'static'), path)

if __name__ == "__main__":
    # Only run the Flask development server if we're not on PythonAnywhere
    if not os.getenv('PYTHONANYWHERE_SITE'):
        try:
            app.run(
                host=config.flask.host,
                port=config.flask.port
            )
        except Exception as e:
            logger.error(f"Failed to run Flask server: {e}")
            sys.exit(-1)