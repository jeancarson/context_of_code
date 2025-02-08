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
    metrics = system_monitor.get_metrics()
    return DeviceMetrics.create_from_metrics(metrics)

# Initialize metrics cache with our specific metrics fetcher
metrics_cache = MetricsCache(
    fetch_func=fetch_device_metrics,
    cache_duration_seconds=30
)

logger.info("Configured server is: %s", config.database.host)

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
        logger.info("Fetching local stats")
        
        # When on PythonAnywhere, fetch metrics from local server
        # if os.getenv('PYTHONANYWHERE_SITE'):
        #     try:
        #         # Replace with your actual local machine's public IP or domain
        #         response = requests.get('localhost:5001/metrics')
        #         response.raise_for_status()
        #         metrics_data = response.json()
        #         metrics = DeviceMetrics(**metrics_data)
        #     except Exception as e:
        #         logger.error(f"Failed to fetch metrics from local server: {e}")
        #         return jsonify({"error": "Failed to fetch metrics from local server"}), 500
        # else:
        #     # When running locally, get metrics from cache
        metrics = metrics_cache.get_metrics()
        
        # For API calls that expect JSON
        if request.headers.get('Accept') == 'application/json':
            return metrics.to_json(indent=2)
        
        # For browser views, render the HTML template
        return render_template('metrics.html', metrics=metrics)

# Add this route to serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(os.path.join(ROOT_DIR, 'static'), path)

@app.route('/people', methods=['GET'])
def people_get():
    try:
        return render_template('people.html')
    except Exception as e:
        logger.error(f"Failed to render people.html: {e}")
        return "Failed to render people.html", 500

@app.route('/people', methods=['POST'])
def people_post():
    try:
        name = request.form.get('name')
        if not name:
            logger.error("Name is required")
            return "Name is required", 400
        return f"Hello {name}!", 200
    except Exception as e:
        logger.error(f"Failed to handle people POST request: {e}")
        return "Failed to handle people POST request", 500

if __name__ == "__main__":
    # Only run the Flask development server if we're not on PythonAnywhere
    if not os.getenv('PYTHONANYWHERE_SITE'):
        try:
            logger.info("Starting Flask web server on %s:%s", config.flask.host, config.flask.port)
            app.run(
                host=config.flask.host,
                port=config.flask.port
            )
        except Exception as e:
            logger.error(f"Failed to run Flask server: {e}")
            sys.exit(-1)
    else:
        logger.info("Running on PythonAnywhere, not starting Flask server")