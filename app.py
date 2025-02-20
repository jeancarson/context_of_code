import os
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
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
from sqlalchemy import desc
from lib.models.generated_models import ExchangeRates



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

# Global variable to track calculator request
calculator_requested = False

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


@app.route("/temperatures", methods=["POST"])
def store_temperatures():
    """Store temperature data received from local app"""
    global calculator_requested
    logger.warning(f"Current calculator_requested flag: {calculator_requested}")
    
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        temperatures = data.get('temperatures', [])
        
        if not temperatures:
            return jsonify({"error": "No temperature data provided"}), StatusCode.BAD_REQUEST
        
        try:
            with get_session() as session:
                for temp_data in temperatures:
                    temp = CapitalTemperature(
                        country_code=temp_data['country_code'],
                        temperature=temp_data['temperature'],
                        timestamp=datetime.datetime.fromisoformat(temp_data['timestamp'])
                    )
                    session.add(temp)
                session.commit()
            
            # Include calculator flag in response if requested
            response = {"status": "success", "message": f"Stored {len(temperatures)} temperature records"}
            if calculator_requested:
                logger.info("Adding open_calculator flag to response")
                response["open_calculator"] = True
                calculator_requested = False  # Reset the flag
                logger.info("Reset calculator_requested flag to False")
            
            return jsonify(response)
        
        except Exception as e:
            logger.error(f"Error storing temperatures: {e}")
            return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR
        
    except Exception as e:
        logger.error(f"Error storing temperatures: {e}")
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR

@app.route("/toggle-task-manager", methods=["POST"])
def toggle_calculator():
    """Toggle the calculator request flag"""
    global calculator_requested
    calculator_requested = True
    logger.info("calculator flag set to True")
    return jsonify({"status": "success", "message": "calculator request will be sent in next response"})

@app.route("/check-task-manager", methods=["GET"])
def check_calculator():
    """Check if calculator should be opened"""
    global calculator_requested
    response = {"open_calculator": calculator_requested}
    if calculator_requested:
        calculator_requested = False  # Reset the flag
        logger.info("calculator flag checked and reset")
    return jsonify(response)

@app.route('/exchange-rates', methods=['POST'])
def add_exchange_rate():
    """Store exchange rate data received from local app"""
    logger.info("Received exchange rate data request")
    if not request.is_json:
        logger.error("Request Content-Type is not application/json")
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        logger.info(f"Received exchange rate data: {data}")
        
        with get_session() as db:
            # Get the last update time
            last_update = db.query(ExchangeRates)\
                .order_by(desc(ExchangeRates.timestamp))\
                .first()
            
            # Only update if newer data or no existing data
            if not last_update or data['timestamp'] > last_update.timestamp.isoformat():
                rate_record = ExchangeRates(
                    rate=data['rate'],
                    timestamp=datetime.datetime.fromisoformat(data['timestamp'])
                )
                db.add(rate_record)
                db.commit()
                logger.info("Successfully stored exchange rate record")
                return jsonify({"message": "Exchange rate stored successfully"}), StatusCode.OK
            else:
                logger.info("Skipping older exchange rate data")
                return jsonify({"message": "Skipped older data"}), StatusCode.OK
        
    except Exception as e:
        logger.error(f"Error storing exchange rate: {e}", exc_info=True)
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR


@app.route("/london")
def london_dashboard():
    """Display London dashboard with temperature and exchange rate"""
    logger.info("Loading London dashboard")
    try:
        with get_session() as db:
            # Get latest temperature for London
            latest_temp = db.query(CapitalTemperature)\
                .filter(CapitalTemperature.country_code == 'GB')\
                .order_by(desc(CapitalTemperature.timestamp))\
                .first()

            # Get latest exchange rate
            latest_rate = db.query(ExchangeRates)\
                .order_by(desc(ExchangeRates.timestamp))\
                .first()

            # Get last updated time
            last_updated = None
            if latest_temp and latest_rate:
                last_updated = max(latest_temp.timestamp, latest_rate.timestamp)
            elif latest_temp:
                last_updated = latest_temp.timestamp
            elif latest_rate:
                last_updated = latest_rate.timestamp

            return render_template(
                'london.html',
                temperature=latest_temp.temperature if latest_temp else 'N/A',
                exchange_rate=f"{latest_rate.rate:.6f}" if latest_rate else 'N/A',
                last_updated=last_updated.strftime('%Y-%m-%d %H:%M:%S UTC') if last_updated else 'Never'
            )
    except Exception as e:
        logger.error(f"Error loading London dashboard: {e}", exc_info=True)
        return jsonify({"error": "Failed to load dashboard"}), StatusCode.INTERNAL_SERVER_ERROR

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
