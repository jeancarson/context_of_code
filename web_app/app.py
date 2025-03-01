import os
import uuid
import datetime
import requests
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
from lib.database import init_db, get_db
from lib.models.generated_models import Aggregators, Devices, MetricTypes, MetricSnapshots, MetricValues, Visits
from lib.constants import StatusCode, HTTPStatusCode
from sqlalchemy import select, func, and_, desc, text
import sys
from lib.models.dto import (
    AggregatorDTO, DeviceDTO, MetricTypeDTO, MetricSnapshotDTO, MetricValueDTO,
    convert_to_snapshot_orm, convert_to_metric_value_orm
)
from typing import Optional
from lib.services.orm_service import (
    get_all_devices,
    get_all_metric_types,
    get_recent_metrics,
    get_all_visits,
    get_latest_metrics_by_type
)
from threading import Lock
import time
from lib.ip_service import IPService

# Compute root directory once and use it throughout the file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize logging first
logger = logging.getLogger(__name__)
config = Config(os.path.join(ROOT_DIR, 'config.json'))
config.setup_logging()

# Initialize services
ip_service = IPService()

# Initialize Flask app with configuration
app = Flask(__name__)
app.config['DEBUG'] = config.debug
app.config['SECRET_KEY'] = config.server.secret_key

calculator_lock = Lock()
calculator_state = "A"  # Toggle between "A" and "B"

# Initialize IP service
ip_service = IPService()

def get_client_ip():
    """Get the client's IP address"""
    if request.headers.getlist("X-Forwarded-For"):
        # If behind a proxy, get real IP
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

def get_location_from_ip(ip: str) -> str:
    """Get location string from IP address using IPService"""
    location = ip_service.get_location(ip)
    if location:
        return f"{location.get('city', '')}, {location.get('country', '')}"
    return "Unknown Location"

@app.route("/")
def hello():
    """Display the main dashboard"""
    client_ip = get_client_ip()
    visit_count = 1
    location = get_location_from_ip(client_ip)
    
    try:
        # Get location info
        location_data = ip_service.get_location(client_ip)
        if location_data:
            location = f"{location_data['city']}, {location_data['region']}, {location_data['country']}"
        
        with get_db() as db:
            # Update visit count
            visit = db.query(Visits).filter(Visits.ip_address == client_ip).first()
            if visit:
                visit.count += 1
                visit.last_visit = datetime.datetime.now()
                visit_count = visit.count
            else:
                visit = Visits(
                    ip_address=client_ip,
                    count=1,
                    last_visit=datetime.datetime.now()
                )
                db.add(visit)
            db.commit()
    except Exception as e:
        logger.error(f"Error updating visit count: {e}")
    
    return render_template(
        "index.html",
        visit_count=visit_count,
        location=location
    )

@app.route("/register/aggregator", methods=["POST"])
def register_aggregator():
    """Register a new aggregator and return its UUID"""
    try:
        data = request.get_json()
        aggregator_dto = AggregatorDTO(**data)
        
        with get_db() as db:
            # Generate UUID if not provided
            if not aggregator_dto.aggregator_uuid:
                aggregator_dto.aggregator_uuid = str(uuid.uuid4())
            
            # Check if aggregator already exists
            existing = db.query(Aggregators).filter(
                Aggregators.aggregator_uuid == aggregator_dto.aggregator_uuid
            ).first()
            
            if existing:
                return jsonify({
                    "status": StatusCode.ERROR,
                    "message": "Aggregator already exists",
                    "uuid": existing.aggregator_uuid
                }), HTTPStatusCode.BAD_REQUEST
            
            # Create new aggregator
            aggregator = Aggregators(
                aggregator_uuid=aggregator_dto.aggregator_uuid,
                name=aggregator_dto.name,
                created_at=str(datetime.datetime.utcnow())
            )
            db.add(aggregator)
            db.commit()
            
            return jsonify({
                "status": StatusCode.OK,
                "uuid": aggregator.aggregator_uuid
            })
            
    except Exception as e:
        logger.error(f"Error registering aggregator: {e}")
        return jsonify({
            "status": StatusCode.ERROR,
            "message": str(e)
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR

@app.route("/register/device", methods=["POST"])
def register_device():
    """Register a new device and return its UUID"""
    try:
        data = request.get_json()
        device_dto = DeviceDTO(**data)
        
        with get_db() as db:
            # Get aggregator
            aggregator = db.query(Aggregators).filter(
                Aggregators.aggregator_uuid == device_dto.aggregator_uuid
            ).first()
            
            if not aggregator:
                return jsonify({
                    "status": StatusCode.ERROR,
                    "message": "Aggregator not found"
                }), HTTPStatusCode.NOT_FOUND
            
            # Generate UUID if not provided
            if not device_dto.device_uuid:
                device_dto.device_uuid = str(uuid.uuid4())
            
            # Check if device already exists
            existing = db.query(Devices).filter(
                Devices.device_uuid == device_dto.device_uuid
            ).first()
            
            if existing:
                return jsonify({
                    "status": StatusCode.ERROR,
                    "message": "Device already exists",
                    "uuid": existing.device_uuid
                }), HTTPStatusCode.BAD_REQUEST
            
            # Create new device
            device = Devices(
                device_uuid=device_dto.device_uuid,
                device_name=device_dto.device_name,
                aggregator_id=aggregator.aggregator_id,
                created_at=str(datetime.datetime.utcnow())
            )
            db.add(device)
            db.commit()
            
            return jsonify({
                "status": StatusCode.OK,
                "uuid": device.device_uuid
            })
            
    except Exception as e:
        logger.error(f"Error registering device: {e}")
        return jsonify({
            "status": StatusCode.ERROR,
            "message": str(e)
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR

@app.route("/metrics", methods=["POST"])
def add_metrics():
    """Add metrics from a device"""
    try:
        data = request.get_json()
        device_uuid = data.get('device_uuid')
        client_timestamp = data.get('client_timestamp')
        client_timezone = data.get('client_timezone_minutes', 0)  # Default to UTC if not provided
        metrics = data.get('metrics', [])

        with get_db() as db:
            # Get device
            device = db.query(Devices).filter(Devices.device_uuid == device_uuid).first()
            if not device:
                raise ValueError(f"Device not found: {device_uuid}")

            # Create snapshot
            snapshot = MetricSnapshots(
                device_id=device.device_id,
                client_timestamp_utc=client_timestamp,
                client_timezone_minutes=client_timezone,
                server_timestamp_utc=datetime.datetime.utcnow(),
                server_timezone_minutes=-time.timezone // 60  # Local server timezone
            )
            db.add(snapshot)
            db.flush()  # Get the snapshot ID

            # Add metric values, handling duplicates
            for metric in metrics:
                metric_type = db.query(MetricTypes).filter(
                    MetricTypes.metric_type_name == metric['type']
                ).first()
                if not metric_type:
                    continue

                # Check for existing value
                existing = db.query(MetricValues).filter(
                    MetricValues.metric_snapshot_id == snapshot.metric_snapshot_id,
                    MetricValues.metric_type_id == metric_type.metric_type_id
                ).first()

                if existing:
                    # Update existing value
                    existing.value = metric['value']
                else:
                    # Create new value
                    value = MetricValues(
                        metric_snapshot_id=snapshot.metric_snapshot_id,
                        metric_type_id=metric_type.metric_type_id,
                        value=metric['value']
                    )
                    db.add(value)

            db.commit()

        return jsonify({
            "status": "SUCCESS",
            "message": "Metrics added successfully"
        })

    except Exception as e:
        logger.error(f"Error adding metrics: {e}")
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR

@app.route("/toggle-calculator", methods=["POST"])
def toggle_calculator():
    """Toggle calculator state between A and B"""
    global calculator_state
    with calculator_lock:
        calculator_state = "B" if calculator_state == "A" else "A"
        return jsonify({
            "calculator_state": calculator_state,
            "calculator_requested": True
        })

@app.route("/check-calculator", methods=["GET"])
def check_calculator():
    """Return current calculator state"""
    global calculator_state
    with calculator_lock:
        return jsonify({
            "calculator_state": calculator_state
        })

@app.route("/debug")
def debug():
    """Debug view showing all database tables"""
    try:
        with get_db() as db:
            devices = get_all_devices(db)
            metric_types = get_all_metric_types(db)
            metrics = get_recent_metrics(db)  # Changed variable name to match template
            latest_metrics = get_latest_metrics_by_type(db)
            visits = get_all_visits(db)

            return render_template(
                "debug.html",
                devices=devices,
                metric_types=metric_types,
                metrics=metrics,  # Changed to match template
                latest_metrics=latest_metrics,
                visits=visits
            )
    except Exception as e:
        logger.error(f"Error in debug view: {e}")
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR

@app.route("/static/<path:path>")
def send_static(path):
    """Serve static files"""
    return send_from_directory("static", path)

if __name__ == "__main__":
    try:
        # Initialize the database before running the app
        init_db()
        
        # Start the Flask app
        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)