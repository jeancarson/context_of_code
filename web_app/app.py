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

@app.route("/dashboard")
def country_dashboard():
    """Display dashboard with all countries"""
    try:
        with get_db() as db:
            # Get all countries
            countries = db.query(Countries).all()
            logger.info(f"Found {len(countries)} countries")
            
            if not countries:
                logger.warning("No countries found in database")
                return render_template('country_info.html', country=None, latest_metrics=None)

            # Get first country's data for now (we can expand to multiple later)
            country = countries[0]
            
            # Get latest temperature
            latest_temp = db.query(CapitalTemperatures)\
                .filter_by(country_id=country.id)\
                .order_by(CapitalTemperatures.timestamp.desc())\
                .first()
            logger.info(f"Latest temperature: {latest_temp.temperature if latest_temp else 'No data'}")

            # Get exchange rates
            latest_rate = db.query(ExchangeRates)\
                .join(Currencies, ExchangeRates.from_currency == Currencies.id)\
                .filter(Currencies.currency_code == country.currency.currency_code)\
                .order_by(ExchangeRates.timestamp.desc())\
                .first()
            logger.info(f"Latest exchange rate: {latest_rate.rate if latest_rate else 'No data'} (from {country.currency.currency_code} to EUR)")

            # Get system metrics
            latest_metrics = db.query(Metrics)\
                .order_by(Metrics.timestamp.desc())\
                .first()
            logger.info(f"Latest metrics: CPU={latest_metrics.cpu_percent if latest_metrics else 'No data'}%, Memory={latest_metrics.memory_percent if latest_metrics else 'No data'}%")

            return render_template(
                'country_info.html',
                country=country,
                latest_temperature=latest_temp,
                latest_exchange_rate=latest_rate,
                latest_metrics=latest_metrics
            )

    except Exception as e:
        logger.error(f"Error in country dashboard: {e}", exc_info=True)
        return str(e), 500

@app.route("/countries")
def list_countries():
    """Return a list of all countries and their IDs"""
    try:
        with get_db() as db:
            # Join with currencies to get the data in one query
            countries = db.query(Countries)\
                .join(Currencies, Countries.currency_id == Currencies.id)\
                .all()
            
            logger.info("Found countries: %s", [f"{c.id}: {c.country_name}" for c in countries])
            
            result = [{
                'id': c.id,
                'name': c.country_name,
                'capital': c.capital_city,
                'currency': c.currency.currency_code  # This should work now due to the join
            } for c in countries]
            
            logger.info("Returning countries: %s", result)
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error listing countries: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route("/country/<int:country_id>")
def country_info(country_id):
    """Display information about a specific country"""
    try:
        with get_db() as db:
            # Get country info
            country = db.query(Countries).filter_by(id=country_id).first()
            logger.info(f"Found country: {country.country_name if country else 'Not found'}")
            
            if not country:
                logger.error(f"Country not found: {country_id}")
                return "Country not found", 404

            # Get latest temperature
            latest_temp = db.query(CapitalTemperatures)\
                .filter_by(country_id=country_id)\
                .order_by(CapitalTemperatures.timestamp.desc())\
                .first()
            logger.info(f"Latest temperature: {latest_temp.temperature if latest_temp else 'No data'}")

            # Get exchange rates
            latest_rate = db.query(ExchangeRates)\
                .join(Currencies, ExchangeRates.from_currency == Currencies.id)\
                .filter(Currencies.currency_code == country.currency.currency_code)\
                .order_by(ExchangeRates.timestamp.desc())\
                .first()
            logger.info(f"Latest exchange rate: {latest_rate.rate if latest_rate else 'No data'} (from {country.currency.currency_code} to EUR)")

            # Get system metrics
            latest_metrics = db.query(Metrics)\
                .order_by(Metrics.timestamp.desc())\
                .first()
            logger.info(f"Latest metrics: CPU={latest_metrics.cpu_percent if latest_metrics else 'No data'}%, Memory={latest_metrics.memory_percent if latest_metrics else 'No data'}%")

            return render_template(
                'country_info.html',
                country=country,
                latest_temperature=latest_temp,
                latest_exchange_rate=latest_rate,
                latest_metrics=latest_metrics
            )
    except Exception as e:
        logger.error(f"Error in country_info route: {e}", exc_info=True)
        return f"Error: {str(e)}", 500

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
            logger.error("Request Content-Type is not application/json")
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        logger.info(f"Received temperature data: {data}")
        
        if not data:
            logger.error("No data in request")
            return jsonify({'error': 'No data in request'}), 400
            
        if 'temperatures' not in data:
            logger.error(f"Invalid request data format. Expected 'temperatures' key. Got: {data.keys()}")
            return jsonify({'error': 'Invalid request data format. Missing temperatures key'}), 400

        with get_db() as db:
            for temp_data in data['temperatures']:
                if not all(k in temp_data for k in ['country_id', 'temperature', 'timestamp']):
                    logger.error(f"Missing required fields in temperature data: {temp_data}")
                    return jsonify({'error': 'Missing required fields in temperature data'}), 400
                    
                temp = CapitalTemperatures(
                    id=str(uuid.uuid4()),  # Generate UUID for each record
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
        logger.info(f"Received exchange rate data: {data}")
        
        if not data or 'exchange_rate' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        rate_data = data['exchange_rate']
        with get_db() as db:
            # Get or create currencies
            from_currency = db.query(Currencies).filter_by(currency_code=rate_data['from_currency']).first()
            if not from_currency:
                from_currency = Currencies(currency_code=rate_data['from_currency'], currency_name=rate_data['from_currency'])
                db.add(from_currency)
                db.flush()  # Get the ID

            to_currency = db.query(Currencies).filter_by(currency_code=rate_data['to_currency']).first()
            if not to_currency:
                to_currency = Currencies(currency_code=rate_data['to_currency'], currency_name=rate_data['to_currency'])
                db.add(to_currency)
                db.flush()  # Get the ID
            
            rate = ExchangeRates(
                id=str(uuid.uuid4()),
                from_currency=from_currency.id,
                to_currency=to_currency.id,
                rate=rate_data['rate'],
                timestamp=datetime.datetime.fromisoformat(rate_data['timestamp'].replace('Z', '+00:00'))
            )
            db.add(rate)
            db.commit()
            logger.info("Successfully stored exchange rate")

        return jsonify({'status': 'success'}), 201

    except Exception as e:
        logger.error(f"Error storing exchange rate: {e}", exc_info=True)
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
    logger.info(f"Toggling calculator flag from {calculator_requested} to {not calculator_requested}")
    calculator_requested = not calculator_requested
    logger.info(f"Calculator flag is now set to {calculator_requested}")
    return jsonify({"calculator_requested": calculator_requested}), StatusCode.OK

@app.route("/check-calculator")
def check_calculator():
    """Check if calculator should be opened"""
    global calculator_requested
    logger.info(f"Checking calculator flag, current value: {calculator_requested}")
    response = {"open_calculator": calculator_requested}
    if calculator_requested:
        calculator_requested = False
        logger.info("Resetting calculator flag to False after check")
    return jsonify(response), StatusCode.OK

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
