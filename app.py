import datetime
from flask import Flask, jsonify
from lib_config.config import Config
from system_monitor import SystemMonitor
import sys
import logging

# Load configuration
config = Config('config.json')

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
    return "Hello World!"

@app.route("/local_stats")
def local_stats():
    logger.info("Fetching local stats")
    metrics = system_monitor.get_metrics()
    
    stats = {
        "cpu": {
            "usage_percent": metrics.cpu_percent,
            "temperature_c": metrics.cpu_temp
        },
        "memory": {
            "usage_percent": metrics.memory_percent,
            "available_gb": metrics.memory_available_gb,
            "total_gb": metrics.memory_total_gb
        },
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    stats_json = jsonify(stats) 
    logger.debug("Local temperature: %s", stats["cpu"]["temperature_c"])  # Changed from stats.cpu.temperature_c
    return stats_json

if __name__ == "__main__":
    app.run(
        host=config.flask.host,
        port=config.flask.port
    ) 
    sys.exit(0)