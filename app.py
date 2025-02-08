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

# Person data model
@dataclass_json
@dataclass
class Person:
    name: str
    dob: str
    id: int = None

# In-memory database
persons = {}
next_id = 1

@app.route('/people', methods=['GET'])
def get_all_persons():
    return jsonify(list(persons.values())), 200

@app.route('/people/<int:person_id>', methods=['GET'])
def get_person(person_id):
    person = persons.get(person_id)
    if person is None:
        return jsonify({"error": "Person not found"}), 404
    return jsonify(person), 200

@app.route('/people', methods=['POST'])
def create_person():
    global next_id
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    if not all(k in data for k in ("name", "dob")):
        return jsonify({"error": "Missing required fields"}), 400
    
    person = Person(name=data['name'], dob=data['dob'], id=next_id)
    persons[next_id] = person
    next_id += 1
    return jsonify(person), 201

@app.route('/people/<int:person_id>', methods=['PUT'])
def update_person(person_id):
    if person_id not in persons:
        return jsonify({"error": "Person not found"}), 404
    
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    if not any(k in data for k in ("name", "dob")):
        return jsonify({"error": "At least one field (name or dob) is required"}), 400
    
    person = persons[person_id]
    if 'name' in data:
        person.name = data['name']
    if 'dob' in data:
        person.dob = data['dob']
    
    return jsonify(person), 200

@app.route('/people/<int:person_id>', methods=['DELETE'])
def delete_person(person_id):
    if person_id not in persons:
        return jsonify({"error": "Person not found"}), 404
    
    del persons[person_id]
    return '', 204

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
