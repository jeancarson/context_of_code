import os
import datetime
from flask import Flask, jsonify, send_from_directory, render_template, request
from lib_config.config import Config
from system_monitor import SystemMonitor
import sys
import logging
from models.device_metrics import DeviceMetrics

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

# Access configuration values naturally with typeahead and strongly typed.
logger.info("Configured server is: %s", config.database.host)  # "localhost"

logger.debug("This is a sample debug message")
logger.info("This is a sample info message")
logger.warning("This is a sample warning message")
logger.error("This is a sample error message")
logger.critical("This is a sample critical message")

@app.route("/")
def hello():
    logger.info("Hello World!")
    my_html_path = os.path.join(ROOT_DIR, 'my.html')
    return open(my_html_path).read()

@app.route("/local_stats")
def local_stats():
    logger.info("Fetching local stats")
    metrics = system_monitor.get_metrics()
    
    device_metrics = DeviceMetrics.create_from_metrics(metrics)
    
    # For API calls that expect JSON
    if request.headers.get('Accept') == 'application/json':
        return device_metrics.to_json(indent=2)
    
    # For browser views, render the HTML template
    return render_template('metrics.html', metrics=device_metrics)

# Add this route to serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(os.path.join(ROOT_DIR, 'static'), path)

if __name__ == "__main__":
    # Only run the Flask development server if we're not on PythonAnywhere
    if not os.getenv('PYTHONANYWHERE_SITE'):
        app.run(
            host=config.flask.host,
            port=config.flask.port
        )
        sys.exit(0)
