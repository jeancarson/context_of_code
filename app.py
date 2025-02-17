import os
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
from lib.models.country_commits_model import CountryCommits
from lib.models.temperature_model import CapitalTemperature
from lib.database import init_db, get_session
from lib.constants import StatusCode
import datetime
from sqlalchemy import select, func, and_
import sys
import uuid
from lib.ip_service import IPService
from lib.models.remote_metrics import RemoteMetricsStore
from lib.metrics_service import MetricsService, ValidationError, get_db, Metrics
from lib.models.visit_model import Visit


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

# Initialize services
remote_metrics_store = RemoteMetricsStore()
metrics_service = MetricsService()
ip_service = IPService()


def get_client_ip():
    """Get the client's IP address"""
    if request.headers.getlist("X-Forwarded-For"):
        # If behind a proxy, get real IP
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr


@app.route("/")
def hello():
    """Render the main page with system metrics"""
    # Get client IP
    client_ip = get_client_ip()
    
    with get_db() as db:
        # Get or create visit count for this IP
        visit = db.query(Visit).filter_by(ip_address=client_ip).first()
        
        if not visit:
            # First visit from this IP
            visit = Visit(ip_address=client_ip)
            db.add(visit)
        else:
            # Increment existing visit count
            visit.count += 1
            visit.last_visit = datetime.datetime.utcnow()
        
        db.commit()
        count = visit.count
    
    # Get location info for the IP
    location = ip_service.get_location(client_ip)
    location_str = "Unknown Location"
    if location:
        location_str = f"{location['city']}, {location['region']}, {location['country']}"
    
    return render_template(
        'index.html', 
        visit_count=count,
        location=location_str,
        remote_metrics=remote_metrics_store.get_all_metrics()
    )

@app.route("/metrics")
def metrics_page():
    """Display metrics dashboard"""
    # Get latest metrics for all machines
    remote_metrics = remote_metrics_store.get_all_metrics()
    
    return render_template(
        "metrics.html",
        remote_metrics=remote_metrics
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
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR

@app.route("/metrics/query", methods=["GET"])
def get_metrics():
    """Get metrics with optional filtering"""
    try:
        device_id = request.args.get('device_id')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        limit = request.args.get('limit', 1000, type=int)
        
        # Convert string timestamps to datetime if provided
        start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00')) if start_time else None
        end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00')) if end_time else None
        
        result = metrics_service.get_metrics(
            device_id=device_id,
            start_time=start_dt,
            end_time=end_dt,
            limit=limit
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), StatusCode.BAD_REQUEST

@app.route("/github", methods=["GET", "POST"])
def github():
    """Handle GitHub stats - both display and data submission"""
    if request.method == "POST":
        # Handle data submission
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
        
        try:
            data = request.get_json()
            stats = data.get('stats')
            
            if not stats:
                return jsonify({"error": "No stats data provided"}), StatusCode.BAD_REQUEST
            
            with get_session() as db:
                # Store each country's stats
                for stat in stats:
                    stat_record = CountryCommits(
                        id=str(uuid.uuid4()),
                        country_code=stat['country_code'],
                        country_name=stat['country_name'],
                        population=stat['population'],
                        commit_count=stat['commit_count'],
                        commits_per_capita=stat['commits_per_capita'],
                        timestamp=datetime.datetime.fromisoformat(stat['timestamp'])
                    )
                    db.add(stat_record)
                db.commit()
            
            return jsonify({"message": "GitHub stats stored successfully"}), StatusCode.OK
            
        except Exception as e:
            logger.error(f"Error storing GitHub stats: {e}")
            return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR
    
    else:  # GET request
        try:
            with get_session() as db:
                # Get latest stats with temperature data using model method
                stats = CountryCommits.get_latest_stats_with_temperature(db)
                
                return render_template(
                    'github_stats.html',
                    countries=[{
                        'country_code': stat[0].country_code,
                        'country_name': stat[0].country_name,
                        'population': stat[0].population,
                        'commit_count': stat[0].commit_count,
                        'commits_per_capita': stat[0].commits_per_capita,
                        'timestamp': stat[0].timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        'temperature': stat[1].temperature if stat[1] else None,
                        'temperature_timestamp': stat[1].timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if stat[1] else None
                    } for stat in stats],
                    last_updated=stats[0][0].timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if stats else 'Never'
                )
                
        except Exception as e:
            logger.error(f"Error retrieving GitHub stats: {e}")
            return render_template(
                'github_stats.html',
                countries=[],
                last_updated='Error retrieving data',
                error=str(e)
            )

@app.route("/temperatures", methods=["POST"])
def store_temperatures():
    """Store temperature data received from local app"""
    logger.info("Received temperature data request")
    if not request.is_json:
        logger.error("Request Content-Type is not application/json")
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        logger.info(f"Received temperature data: {data}")
        temperatures = data.get('temperatures')
        
        if not temperatures:
            logger.error("No temperature data provided in request")
            return jsonify({"error": "No temperature data provided"}), StatusCode.BAD_REQUEST
        
        logger.info(f"Processing {len(temperatures)} temperature records")
        with get_session() as db:
            # Store each country's temperature
            for temp in temperatures:
                logger.info(f"Processing temperature for country: {temp.get('country_code')}")
                temp_record = CapitalTemperature(
                    id=str(uuid.uuid4()),
                    country_code=temp['country_code'],
                    temperature=temp['temperature'],
                    timestamp=datetime.datetime.fromisoformat(temp['timestamp'])
                )
                db.add(temp_record)
            db.commit()
            logger.info("Successfully stored all temperature records")
        
        return jsonify({"message": "Temperatures stored successfully"}), StatusCode.OK
        
    except Exception as e:
        logger.error(f"Error storing temperatures: {e}", exc_info=True)
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

if __name__ == "__main__":
    try:
        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        sys.exit(1)
