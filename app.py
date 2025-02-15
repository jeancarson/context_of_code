import os
from flask import Flask, jsonify, send_from_directory, render_template, request
from lib.config import Config
import logging
from lib.models.remote_metrics import RemoteMetricsStore
from lib.person_handler import PersonHandler
from lib.metrics_service import MetricsService, ValidationError, get_db, Metrics
from lib.constants import StatusCode
import datetime

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

# Initialize remote metrics store
remote_metrics_store = RemoteMetricsStore()

# Initialize person handler
person_handler = PersonHandler()

# Initialize services
metrics_service = MetricsService()

# Verify database setup
with get_db() as db:
    try:
        # Try to query the Metrics table
        result = db.query(Metrics).first()
        logger.info("Metrics table exists and is accessible")
    except Exception as e:
        logger.error(f"Error accessing Metrics table: {e}")

@app.route("/")
def hello():
    """Render the main page with system metrics"""
    return render_template('index.html', remote_metrics=remote_metrics_store.get_all_metrics())

@app.route("/metrics")
def metrics_page():
    """Display metrics dashboard"""
    return render_template(
        'metrics.html',
        remote_metrics=remote_metrics_store.get_all_metrics()
    )

@app.route("/metrics", methods=["POST"])
def receive_metrics():
    """Receive metrics from remote machines"""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        metrics_data = request.get_json()
        
        # Store in the metrics database
        result = metrics_service.create_metrics(metrics_data)
        
        # Also update the remote metrics store
        machine_id = request.remote_addr
        remote_metrics_store.update_metrics(machine_id, metrics_data)
        
        # Return the created metrics with 201 status
        return jsonify(result), StatusCode.CREATED
        
    except ValidationError as e:
        return jsonify({"error": str(e)}), StatusCode.BAD_REQUEST
    except Exception as e:
        logger.error(f"Error processing metrics: {e}")
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_ERROR

@app.get("/metrics")
def get_metrics():
    """Get metrics with optional filtering"""
    try:
        device_id = request.args.get('device_id')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        limit = request.args.get('limit', 1000, type=int)
        
        # Convert string timestamps to datetime if provided
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')) if start_time else None
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00')) if end_time else None
        
        result = metrics_service.get_metrics(
            device_id=device_id,
            start_time=start_dt,
            end_time=end_dt,
            limit=limit
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Add this route to serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/persons', methods=['GET'])
def get_all_persons():
    return jsonify(person_handler.get_all_persons())

@app.route('/persons/<int:person_id>', methods=['GET'])
def get_person(person_id):
    return jsonify(person_handler.get_person(person_id))

@app.route('/persons', methods=['POST'])
def create_person():
    return jsonify(person_handler.create_person(request.json))

@app.route('/persons/<int:person_id>', methods=['PUT'])
def update_person(person_id):
    return jsonify(person_handler.update_person(person_id, request.json))

@app.route('/persons/<int:person_id>', methods=['DELETE'])
def delete_person(person_id):
    return jsonify(person_handler.delete_person(person_id))

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
