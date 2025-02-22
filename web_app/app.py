import os
import uuid
import datetime
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
from lib.database import init_db, get_db
from lib.models.generated_models import Devices, MetricTypes, Metrics
from lib.constants import StatusCode, HTTPStatusCode
from sqlalchemy import select, func, and_, desc, text
import sys
from lib.models.dto import MetricDTO, MetricsRequest, convert_to_orm
from typing import Optional
from lib.services.orm_service import (
    get_all_devices,
    get_all_metric_types,
    get_recent_metrics,
    get_all_visits
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
            # First check if metrics table exists
            try:
                metrics = db.query(Metrics).all()
                
                # Format metrics for display
                formatted_metrics = []
                for metric in metrics:
                    try:
                        formatted_metrics.append({
                            'device_id': str(metric.device),  # Just use the ID for now
                            'type': str(metric.type),  # Just use the ID for now
                            'value': float(metric.value),
                            'created_at': metric.created_at
                        })
                    except Exception as e:
                        logger.error(f"Error formatting metric {metric.id}: {e}")
                        continue
                    
                return formatted_metrics
            except Exception as e:
                logger.error(f"Error querying metrics: {e}")
                return []
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return []

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
        
        with get_db() as db:
            for metric_dto in metrics_request.metrics:
                try:
                    # Get or create metric type
                    metric_type = get_or_create_metric_type(db, metric_dto.type)
                    if not metric_type:
                        logger.error(f"Failed to get/create metric type: {metric_dto.type}")
                        continue

                    # Get device by UUID
                    device = get_device_by_uuid(db, metric_dto.device_id)
                    if not device:
                        return jsonify({
                            'error': f'Device not found: {metric_dto.device_id}',
                            'status': StatusCode.NOT_FOUND.value
                        }), HTTPStatusCode.NOT_FOUND.value
                    
                    # Create metric
                    metric = Metrics(
                        device=device.id,
                        type=metric_type.id,  # Use the ID of the metric type
                        value=metric_dto.value,
                        created_at=metric_dto.created_at
                    )
                    db.add(metric)
                
                except Exception as e:
                    logger.error(f"Error storing metric: {e}")
                    return jsonify({
                        'error': str(e),
                        'status': StatusCode.ERROR.value
                    }), HTTPStatusCode.INTERNAL_SERVER_ERROR.value
            
            db.commit()
            return jsonify({'status': StatusCode.OK.value})
            
    except Exception as e:
        logger.error(f"Error processing metrics request: {e}")
        return jsonify({
            'error': str(e),
            'status': StatusCode.ERROR.value
        }), HTTPStatusCode.INTERNAL_SERVER_ERROR.value

@app.route("/debug")
def debug():
    """Debug view showing all database tables"""
    return render_template(
        "debug.html",
        devices=get_all_devices(),
        metric_types=get_all_metric_types(),
        metrics=get_recent_metrics(limit=50),
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
