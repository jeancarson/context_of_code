import os
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
from lib.database import init_db, get_db
from lib.constants import StatusCode
import datetime
from sqlalchemy import select, func, and_, desc
import sys
import uuid
from lib.ip_service import IPService

# Import models from generated_models
from lib.models.generated_models import (
    Base, Metrics, Visits, Countries, Currencies,
    ExchangeRates, CapitalTemperatures
)

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
ip_service = IPService()

# Global variable to track calculator request
calculator_requested = False

def get_client_ip():
    """Get the client's IP address"""
    if request.headers.getlist("X-Forwarded-For"):
        # If behind a proxy, get real IP
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

def get_latest_metrics():
    """Get the latest metrics for each device from the database"""
    with get_db() as db:
        # Subquery to get the latest timestamp for each device
        latest_timestamps = db.query(
            Metrics.device_id,
            func.max(Metrics.timestamp).label('max_timestamp')
        ).group_by(Metrics.device_id).subquery()
        
        # Join with metrics to get the full records
        latest_metrics = db.query(Metrics).join(
            latest_timestamps,
            and_(
                Metrics.device_id == latest_timestamps.c.device_id,
                Metrics.timestamp == latest_timestamps.c.max_timestamp
            )
        ).all()
        
        # Return as dict keyed by device_id
        return {
            m.device_id: {
                'timestamp': m.timestamp,  # Keep as datetime for template
                'cpu_percent': m.cpu_percent,
                'memory_percent': m.memory_percent,
                'memory_available_gb': m.memory_available_gb,
                'memory_total_gb': m.memory_total_gb,
                'device_id': m.device_id
            } for m in latest_metrics
        }

@app.route("/")
def hello():
    """Render the main page with system metrics"""
    # Get client IP
    client_ip = get_client_ip()
    
    with get_db() as db:
        # Get or create visit count for this IP
        visit = db.query(Visits).filter_by(ip_address=client_ip).first()
        
        if not visit:
            # First visit from this IP
            visit = Visits(
                ip_address=client_ip,
                count=1,
                last_visit=datetime.datetime.utcnow()
            )
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
        remote_metrics=get_latest_metrics()
    )

@app.route("/metrics")
def metrics_page():
    """Display metrics dashboard"""
    return render_template(
        "metrics.html",
        remote_metrics=get_latest_metrics()
    )

@app.route("/metrics", methods=["POST"])
def receive_metrics():
    """Receive metrics from remote machines"""
    global calculator_requested
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        metrics = Metrics(
            id=None,  # Auto-generated
            timestamp=datetime.datetime.fromisoformat(data['timestamp']),
            cpu_percent=data['cpu_percent'],
            memory_percent=data['memory_percent'],
            memory_available_gb=data['memory_available_gb'],
            memory_total_gb=data['memory_total_gb'],
            device_id=data['device_id']
        )
        
        with get_db() as db:
            db.add(metrics)
            db.commit()
            
        # Check if calculator should be opened
        response = {"status": "success"}
        if calculator_requested:
            response["open_calculator"] = True
            calculator_requested = False
            
        return jsonify(response), StatusCode.CREATED
        
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Invalid data format: {str(e)}"}), StatusCode.BAD_REQUEST
    except Exception as e:
        logger.error(f"Error storing metrics: {e}")
        return jsonify({"error": "Internal server error"}), StatusCode.INTERNAL_SERVER_ERROR

@app.route("/metrics/<device_id>")
def get_metrics(device_id):
    """Get metrics for a specific device"""
    try:
        with get_db() as db:
            metrics = db.query(Metrics).filter_by(device_id=device_id).order_by(desc(Metrics.timestamp)).all()
            return jsonify([{
                'timestamp': m.timestamp.isoformat(),
                'cpu_percent': m.cpu_percent,
                'memory_percent': m.memory_percent,
                'memory_available_gb': m.memory_available_gb,
                'memory_total_gb': m.memory_total_gb,
                'device_id': m.device_id
            } for m in metrics]), StatusCode.OK
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        return jsonify({"error": "Internal server error"}), StatusCode.INTERNAL_SERVER_ERROR

@app.route("/temperatures", methods=["POST"])
def store_temperatures():
    """Store temperature data received from local app"""
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        if not data or 'temperatures' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        with get_db() as db:
            for temp_data in data['temperatures']:
                temp = CapitalTemperatures(
                    country_id=temp_data['country_id'],
                    temperature=temp_data['temperature'],
                    timestamp=datetime.datetime.fromisoformat(temp_data['timestamp'])
                )
                db.add(temp)
            db.commit()

        return jsonify({'status': 'success'}), 201

    except Exception as e:
        logger.error(f"Error storing temperatures: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/exchange_rates", methods=["POST"])
def store_exchange_rate():
    """Store exchange rate data received from local app"""
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        if not data or 'exchange_rate' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        rate_data = data['exchange_rate']
        with get_db() as db:
            rate = ExchangeRates(
                from_currency=rate_data['from_currency'],
                to_currency=rate_data['to_currency'],
                rate=rate_data['rate'],
                timestamp=datetime.datetime.fromisoformat(rate_data['timestamp'])
            )
            db.add(rate)
            db.commit()

        return jsonify({'status': 'success'}), 201

    except Exception as e:
        logger.error(f"Error storing exchange rate: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/exchange-rates", methods=["POST"])
def add_exchange_rate():
    """Store exchange rate data received from local app"""
    global calculator_requested
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        
        with get_db() as db:
            # Get currencies
            from_currency = db.query(Currencies).filter_by(currency_code=data['from_currency']).first()
            to_currency = db.query(Currencies).filter_by(currency_code=data['to_currency']).first()
            
            if not from_currency or not to_currency:
                return jsonify({"error": "Currency not found"}), StatusCode.NOT_FOUND
            
            # Create exchange rate record
            rate = ExchangeRates(
                id=str(uuid.uuid4()),
                from_currency=from_currency.id,
                to_currency=to_currency.id,
                rate=data['rate'],
                timestamp=datetime.datetime.fromisoformat(data['timestamp'])
            )
            
            db.add(rate)
            db.commit()
            
            # Check if calculator should be opened
            response = {"status": "success"}
            if calculator_requested:
                response["open_calculator"] = True
                calculator_requested = False
                
            return jsonify(response), StatusCode.CREATED
            
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Invalid data format: {str(e)}"}), StatusCode.BAD_REQUEST
    except Exception as e:
        logger.error(f"Error storing exchange rate: {e}")
        return jsonify({"error": "Internal server error"}), StatusCode.INTERNAL_SERVER_ERROR

@app.route("/toggle-calculator", methods=["POST"])
def toggle_calculator():
    """Toggle the calculator request flag"""
    global calculator_requested
    calculator_requested = not calculator_requested
    return jsonify({"calculator_requested": calculator_requested}), StatusCode.OK

@app.route("/check-calculator")
def check_calculator():
    """Check if calculator should be opened"""
    global calculator_requested
    response = {"open_calculator": calculator_requested}
    if calculator_requested:
        calculator_requested = False
    return jsonify(response), StatusCode.OK

@app.route("/dashboard/<country>")
def country_dashboard(country):
    """Display country dashboard with temperature and exchange rate"""
    try:
        with get_db() as db:
            # Get country and its currency
            country_data = db.query(Countries).filter_by(country_name=country).first()
            if not country_data:
                return jsonify({"error": "Country not found"}), StatusCode.NOT_FOUND
            
            # Get latest temperature
            latest_temp = db.query(CapitalTemperatures)\
                .filter_by(country_id=country_data.id)\
                .order_by(desc(CapitalTemperatures.timestamp))\
                .first()
            
            # Get latest exchange rates for the country's currency
            latest_rates = db.query(ExchangeRates)\
                .filter(ExchangeRates.from_currency == country_data.currency_id)\
                .order_by(desc(ExchangeRates.timestamp))\
                .all()
            
            return render_template(
                "country_dashboard.html",
                country=country_data,
                temperature=latest_temp,
                exchange_rates=latest_rates
            )
            
    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {e}")
        return jsonify({"error": "Internal server error"}), StatusCode.INTERNAL_SERVER_ERROR

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

if __name__ == "__main__":
    try:
        # Initialize the database before running the app
        init_db()
        
        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
