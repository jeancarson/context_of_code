import os
import uuid
import datetime
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
from lib.database import init_db, get_db
from lib.models.generated_models import Devices, MetricTypes, Metrics, Visits
from lib.constants import StatusCode, HTTPStatusCode
from sqlalchemy import select, func, and_, desc, text
import sys
from lib.models.dto import MetricDTO, MetricsRequest, convert_to_orm
from typing import Optional
from lib.services.orm_service import (
    get_all_devices,
    get_all_metric_types,
    get_recent_metrics,
    get_all_visits,
    get_latest_metrics_by_type
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

calculator_requested = False

def get_client_ip():
    """Get the client's IP address"""
    if request.headers.getlist("X-Forwarded-For"):
        # If behind a proxy, get real IP
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

def get_latest_metrics():
    """Get the latest metrics for each device from the database"""
    try:
        with get_db() as db:
            # Get all metrics with their types and devices
            metrics = (
                db.query(Metrics, MetricTypes, Devices)
                .join(MetricTypes, Metrics.type == MetricTypes.id)
                .join(Devices, Metrics.device == Devices.id)
                .order_by(Metrics.created_at.desc())
                .all()
            )

            # Group metrics by device
            metrics_by_device = {}
            for metric, metric_type, device in metrics:
                if device.uuid not in metrics_by_device:
                    metrics_by_device[device.uuid] = {
                        'timestamp': datetime.datetime.strptime(metric.created_at, '%Y-%m-%d %H:%M:%S.%f'),
                        'metrics': {}
                    }
                metrics_by_device[device.uuid]['metrics'][metric_type.type] = float(metric.value)

            return metrics_by_device
    except Exception as e:
        logger.error(f"Error getting latest metrics: {e}")
        return {}

@app.route("/")
def hello():
    """Display the main dashboard"""
    client_ip = get_client_ip()
    visit_count = 1
    
    try:
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
        remote_metrics=get_latest_metrics(),
        visit_count=visit_count
    )

@app.route("/metrics")
def metrics_page():
    """Display metrics dashboard"""
    return render_template(
        "metrics.html",
        remote_metrics=get_latest_metrics()
    )

@app.route("/api/device/register", methods=["POST"])
def register_device():
    """Register a new device and return its UUID"""
    try:
        device_uuid = uuid.uuid4()
        device = Devices(
            uuid=device_uuid.hex,
            created_at=str(datetime.datetime.now())
        )
        
        with get_db() as db:
            db.add(device)
            db.commit()
            
        return jsonify({
            'status': StatusCode.OK.value,
            'device_id': device_uuid.hex
        })
    except Exception as e:
        logger.error(f"Error registering device: {e}")
        return jsonify({
            'error': str(e),
            'status': StatusCode.ERROR.value
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR.value

def get_or_create_metric_type(db, type_name: str) -> MetricTypes:
    """Get or create a metric type by name"""
    metric_type = db.query(MetricTypes).filter(MetricTypes.type == type_name).first()
    if not metric_type:
        metric_type = MetricTypes(
            type=type_name,
            created_at=datetime.datetime.now()
        )
        db.add(metric_type)
        db.commit()
    return metric_type

def get_device_by_uuid(db, uuid_hex: str) -> Optional[Devices]:
    """Get a device by its UUID hex string"""
    try:
        return db.query(Devices).filter(Devices.uuid == uuid_hex).first()
    except Exception as e:
        logger.error(f"Error finding device with UUID {uuid_hex}: {e}")
        return None

@app.route("/api/metrics", methods=['POST'])
def store_metrics():
    """Store metrics received from devices"""
    try:
        if not request.is_json:
            return jsonify({
                'error': 'Invalid content type',
                'status': StatusCode.BAD_REQUEST.value
            }), HTTPStatusCode.BAD_REQUEST.value

        metrics_request = MetricsRequest(**request.json)
        errors = []
        
        with get_db() as db:
            for metric_dto in metrics_request.metrics:
                try:
                    # Get or create metric type
                    metric_type = get_or_create_metric_type(db, metric_dto.type)
                    if not metric_type:
                        errors.append(f"Failed to get/create metric type: {metric_dto.type}")
                        continue

                    # Get device by UUID
                    device = get_device_by_uuid(db, metric_dto.device_id)
                    if not device:
                        errors.append(f"Device not found: {metric_dto.device_id}")
                        continue
                    
                    # Create metric
                    metric = Metrics(
                        device=device.id,
                        type=metric_type.id,  # Use the ID of the metric type
                        value=metric_dto.value,
                        created_at=metric_dto.created_at
                    )
                    db.add(metric)
                
                except Exception as e:
                    errors.append(f"Error storing metric: {e}")
                    continue
            
            try:
                db.commit()
            except Exception as e:
                errors.append(f"Error committing to database: {e}")
                return jsonify({
                    'error': str(e),
                    'errors': errors,
                    'status': StatusCode.ERROR.value
                }), HTTPStatusCode.INTERNAL_SERVER_ERROR.value
            
            # Return success even if some metrics failed
            return jsonify({
                'status': StatusCode.OK.value,
                'errors': errors if errors else None
            })
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': StatusCode.ERROR.value
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR.value

@app.route("/toggle-calculator", methods=['POST'])
def toggle_calculator():
    """Toggle calculator flag for next response"""
    global calculator_requested
    calculator_requested = True
    logger.info("Calculator request received")
    return jsonify({"calculator_requested": True})

@app.route("/check-calculator", methods=['POST'])
def check_calculator():
    """Check and reset calculator flag"""
    global calculator_requested
    was_requested = calculator_requested
    calculator_requested = False  # Reset after checking
    logger.info(f"Calculator check - was requested: {was_requested}")
    return jsonify({"calculator_requested": was_requested})

@app.route("/debug")
def debug():
    """Debug view showing all database tables"""
    return render_template(
        "debug.html",
        devices=get_all_devices(),
        metric_types=get_all_metric_types(),
        metrics=get_latest_metrics_by_type(),
        visits=get_all_visits()
    )

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
