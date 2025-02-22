from typing import List, Dict, Any
from sqlalchemy import desc
from ..models.generated_models import Metrics, Devices, MetricTypes, Visits
from ..database import get_db

def get_all_devices() -> List[Dict[str, Any]]:
    """Get all devices with their UUIDs"""
    with get_db() as db:
        devices = db.query(Devices).all()
        return [
            {
                'id': device.id,
                'uuid': device.uuid.hex(),
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
                'device_uuid': metric.devices.uuid.hex(),
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
                'last_visit': visit.last_visit.strftime('%Y-%m-%d %H:%M:%S')
            }
            for visit in visits
        ]
