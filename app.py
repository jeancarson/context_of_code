import os
from flask import Flask, jsonify, send_from_directory, render_template, request
from lib.config import Config
from lib.system_monitor import SystemMonitor
import logging
from lib.models.device_metrics import DeviceMetrics
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from lib.block_timer import BlockTimer
from lib.metrics_cache import MetricsCache
from lib.constants import HTTPMethod
from lib.person_handler import PersonHandler

# Compute root directory once and use it throughout the file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize logging first
logger = logging.getLogger(__name__)
config = Config(os.path.join(ROOT_DIR, 'config.json'))
config.setup_logging()

# Initialize Flask app with configuration
app = Flask(__name__)
app.config['DEBUG'] = config.debug
app.config['SECRET_KEY'] = config.server.secret_key

# Initialize system monitor
system_monitor = SystemMonitor()

# Define function to fetch fresh metrics
def fetch_device_metrics():
    metrics = system_monitor.get_metrics()
    return DeviceMetrics.create_from_metrics(metrics)

# Initialize metrics cache with our specific metrics fetcher
metrics_cache = MetricsCache(
    fetch_func=fetch_device_metrics,
    cache_duration_seconds=config.cache.duration_seconds
)

# Initialize the person handler
person_handler = PersonHandler()

logger.info("Configured server is: %s:%d", config.server.host, config.server.port)

logger.debug("This is a sample debug message")
logger.info("This is a sample info message")
logger.warning("This is a sample warning message")
logger.error("This is a sample error message")
logger.critical("This is a sample critical message")

@app.route("/")
def hello():
    return render_template('my.html')

@app.route("/local_stats")
def local_stats():
    with BlockTimer("Get Local Stats Request", logger):
        logger.info("Fetching local stats")
        
        metrics = metrics_cache.get_metrics()
        
        return render_template('metrics.html', metrics=metrics)

# Add this route to serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(os.path.join(ROOT_DIR, 'static'), path)

@app.route('/people', methods=[HTTPMethod.GET.value])
def get_all_persons():
    return person_handler.get_all_persons()

@app.route('/people/<int:person_id>', methods=[HTTPMethod.GET.value])
def get_person(person_id):
    return person_handler.get_person(person_id)

@app.route('/people', methods=[HTTPMethod.POST.value])
def create_person():
    return person_handler.create_person()

@app.route('/people/<int:person_id>', methods=[HTTPMethod.PUT.value])
def update_person(person_id):
    return person_handler.update_person(person_id)

@app.route('/people/<int:person_id>', methods=[HTTPMethod.DELETE.value])
def delete_person(person_id):
    return person_handler.delete_person(person_id)

if __name__ == "__main__":
    try:
        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
else:
    # For WSGI servers
    application = app
