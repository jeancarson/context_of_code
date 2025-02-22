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
from lib.models.dto import MetricDTO, MetricsRequest, convert_to_orm

# Import models from generated_models
from lib.models.generated_models import (
    Base, Metrics, Visits, Devices, MetricTypes
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
    with get_db() as db:
        # Get the latest timestamp for each device and metric type
        latest_metrics = db.query(
            Metrics.device,
            Metrics.type,
            func.max(Metrics.timestamp).label('max_timestamp')
        ).group_by(Metrics.device, Metrics.type).subquery()
        
        # Join with the metrics table to get the actual metric values
        metrics = db.query(Metrics).join(
            latest_metrics,
            and_(
                Metrics.device == latest_metrics.c.device,
                Metrics.type == latest_metrics.c.type,
                Metrics.timestamp == latest_metrics.c.max_timestamp
            )
        ).all()
        
        # Format metrics for display
        formatted_metrics = []
        for metric in metrics:
            formatted_metrics.append({
                'device_id': metric.device,
                'type': metric.metric_types.type,
                'value': float(metric.value),
                'timestamp': metric.timestamp
            })
            
        return formatted_metrics

@app.route("/")
def hello():
    """Display the main dashboard"""
    client_ip = get_client_ip()
    
    with get_db() as db:
        # Update visit count
        visit = db.query(Visits).filter(Visits.ip_address == client_ip).first()
        if visit:
            visit.count += 1
            visit.last_visit = datetime.datetime.now()
        else:
            visit = Visits(
                ip_address=client_ip,
                count=1,
                last_visit=datetime.datetime.now()
            )
            db.add(visit)
        db.commit()
    
    return render_template(
        "index.html",
        remote_metrics=get_latest_metrics(),
        visit_count=visit.count if visit else 1
    )

@app.route("/metrics")
def metrics_page():
    """Display metrics dashboard"""
    return render_template(
        "metrics.html",
        remote_metrics=get_latest_metrics()
    )

@app.route("/api/metrics", methods=["POST"])
def store_metrics():
    """Store metrics received from devices"""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        metrics_request = MetricsRequest(
            metrics=[
                MetricDTO(
                    type=m["type"],
                    value=float(m["value"]),
                    uuid=uuid.UUID(m["uuid"]) if m["uuid"] else None,
                    timestamp=m["timestamp"]
                ) for m in data["metrics"]
            ]
        )
        
        with get_db() as db:
            for metric in metrics_request.metrics:
                # Skip metrics without device UUID
                if not metric.uuid:
                    logger.warning(f"Skipping metric without UUID: {metric}")
                    continue
                    
                # Get or create device
                device_bytes = metric.uuid.bytes
                device = db.query(Devices).filter(Devices.uuid == device_bytes).first()
                if not device:
                    device = Devices(uuid=device_bytes)
                    db.add(device)
                    db.flush()  # Get the device ID
                    
                # Get or create metric type
                metric_type = db.query(MetricTypes).filter(MetricTypes.type == metric.type).first()
                if not metric_type:
                    metric_type = MetricTypes(type=metric.type)
                    db.add(metric_type)
                    db.flush()  # Get the type ID
                
                # Create and store the metric
                orm_metric = convert_to_orm(metric, device.id, metric_type.id)
                db.add(orm_metric)
            
            db.commit()
            
        return jsonify({"status": "success"}), StatusCode.CREATED
        
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Invalid data format: {str(e)}"}), StatusCode.BAD_REQUEST
    except Exception as e:
        logger.error(f"Error storing metrics: {e}")
        return jsonify({"error": "Internal server error"}), StatusCode.INTERNAL_SERVER_ERROR

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
