import os
from flask import Flask, jsonify, send_from_directory, render_template, request
from lib.config import Config
import logging
from lib.models.remote_metrics import RemoteMetricsStore
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

# Initialize remote metrics store
remote_metrics_store = RemoteMetricsStore()

# Initialize person handler
person_handler = PersonHandler()

@app.route("/")
def hello():
    """Render the main page with system metrics"""
    metrics = remote_metrics_store.get_latest_metrics()
    return render_template('index.html', metrics=metrics)

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
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    try:
        metrics_data = request.get_json()
        # Use the request's remote address as machine_id for now
        machine_id = request.remote_addr
        remote_metrics_store.update_metrics(machine_id, metrics_data)
        
        # You can add commands or config updates here
        response = {
            "status": "ok",
            # "command": "example_command",  # Uncomment to test command execution
            # "config": {"poll_interval_seconds": 60}  # Uncomment to test config updates
        }
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error processing metrics: {e}")
        return jsonify({"error": str(e)}), 500

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
