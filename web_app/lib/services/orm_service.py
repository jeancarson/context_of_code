from typing import List, Dict, Any
from sqlalchemy import desc, func, and_
from sqlalchemy.exc import IntegrityError
from ..models.generated_models import Metrics, Devices, MetricTypes, Visits
from ..database import get_db
import logging

logger = logging.getLogger(__name__)

def get_all_devices() -> List[Dict[str, Any]]:
    """Get all devices with their UUIDs"""
    with get_db() as db:
        devices = db.query(Devices).all()
        return [
            {
                'id': device.id,
                'uuid': device.uuid,  
                'created_at': device.created_at,
                'metric_count': len(device.metrics)
            }
            for device in devices
        ]

def get_all_metric_types() -> List[Dict[str, Any]]:
    """Get all metric types"""
    with get_db() as db:
        types = db.query(MetricTypes).all()
        return [
            {
                'id': type.id,
                'type': type.type,
                'created_at': type.created_at,
                'metric_count': len(type.metrics)
            }
            for type in types
        ]

def get_recent_metrics(limit: int = 50) -> List[Dict[str, Any]]:
    """Get most recent metrics with device and type information"""
    with get_db() as db:
        metrics = db.query(Metrics)\
            .join(Devices)\
            .join(MetricTypes)\
            .order_by(desc(Metrics.created_at))\
            .limit(limit)\
            .all()
        
        return [
            {
                'id': metric.id,
                'device_uuid': metric.devices.uuid,  
                'type': metric.metric_types.type,
                'value': float(metric.value),
                'created_at': metric.created_at
            }
            for metric in metrics
        ]

def get_all_visits() -> List[Dict[str, Any]]:
    """Get all visits"""
    with get_db() as db:
        visits = db.query(Visits).order_by(desc(Visits.last_visit)).all()
        return [
            {
                'id': visit.id,
                'ip_address': visit.ip_address,
                'count': visit.count,
                'last_visit': visit.last_visit.isoformat() if visit.last_visit else None
            }
            for visit in visits
        ]

def get_latest_metrics_by_type():
    """Get only the most recent metric for each type"""
    try:
        with get_db() as db:
            # Use a subquery to get the latest metric for each type
            latest_metrics = (
                db.query(
                    Metrics.type,
                    func.max(Metrics.created_at).label('max_created_at')
                )
                .group_by(Metrics.type)
                .subquery()
            )

            # Join with the original metrics table to get the full metric data
            metrics = (
                db.query(Metrics, MetricTypes, Devices)
                .join(MetricTypes, Metrics.type == MetricTypes.id)
                .join(Devices, Metrics.device == Devices.id)
                .join(
                    latest_metrics,
                    and_(
                        Metrics.type == latest_metrics.c.type,
                        Metrics.created_at == latest_metrics.c.max_created_at
                    )
                )
                .all()
            )

            # Format the results
            return [{
                'id': metric.id,
                'device_uuid': device.uuid,
                'type': metric_type.type,
                'value': float(metric.value),
                'created_at': metric.created_at
            } for metric, metric_type, device in metrics]
    except Exception as e:
        logger.error(f"Error getting latest metrics by type: {e}")
        return []
