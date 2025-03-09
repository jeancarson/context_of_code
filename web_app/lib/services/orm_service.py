from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session
from ..models.generated_models import Devices, MetricTypes, MetricSnapshots, MetricValues, Visits, Aggregators
from typing import List, Dict, Any
from datetime import datetime
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

def get_all_devices(db: Session) -> List[Dict[str, Any]]:
    """Get all devices with their aggregator info and metric counts"""
    devices = (
        db.query(
            Devices,
            Aggregators,
            func.count(MetricValues.metric_snapshot_id).label('metric_count')
        )
        .outerjoin(Aggregators)
        .outerjoin(MetricSnapshots)
        .outerjoin(MetricValues)
        .group_by(Devices.device_id)
        .all()
    )

    return [{
        'id': device.device_id,
        'uuid': device.device_uuid,
        'name': device.device_name,
        'aggregator_name': aggregator.name if aggregator else None,
        'aggregator_uuid': aggregator.aggregator_uuid if aggregator else None,
        'created_at': device.created_at,
        'metric_count': metric_count
    } for device, aggregator, metric_count in devices]

def get_all_metric_types(db: Session) -> List[Dict[str, Any]]:
    """Get all metric types with their metric counts"""
    types = (
        db.query(
            MetricTypes,
            func.count(MetricValues.metric_snapshot_id).label('metric_count')
        )
        .outerjoin(MetricValues)
        .group_by(MetricTypes.metric_type_id)
        .all()
    )
    
    return [{
        'id': type.metric_type_id,
        'type': type.metric_type_name,
        'device_id': type.device_id,
        'created_at': type.created_at,
        'metric_count': metric_count
    } for type, metric_count in types]

def get_recent_metrics(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent metrics with their types and devices"""
    metrics = (
        db.query(MetricSnapshots, Devices, MetricValues, MetricTypes)
        .select_from(MetricSnapshots)
        .join(
            Devices,
            Devices.device_id == MetricSnapshots.device_id
        )
        .join(
            MetricValues,
            MetricValues.metric_snapshot_id == MetricSnapshots.metric_snapshot_id
        )
        .join(
            MetricTypes,
            and_(
                MetricTypes.metric_type_id == MetricValues.metric_type_id,
                MetricTypes.device_id == Devices.device_id
            )
        )
        .order_by(desc(MetricSnapshots.server_timestamp_utc))
        .limit(limit)
        .all()
    )
    
    def convert_timestamp(client_timestamp_str: str, client_offset: int, server_offset: int) -> str:
        """Convert client timestamp to server local time"""
        try:
            # Parse the client timestamp
            client_time = datetime.fromisoformat(client_timestamp_str.replace('Z', '+00:00'))
            
            # Add client offset to get UTC (if timestamp wasn't already UTC)
            if not client_timestamp_str.endswith('Z'):
                client_time = client_time + timedelta(minutes=client_offset)
            
            # Subtract server offset to get server local time
            server_time = client_time - timedelta(minutes=server_offset)
            
            return server_time.isoformat()
        except Exception as e:
            logger.error(f"Error converting timestamp {client_timestamp_str}: {e}")
            return client_timestamp_str
    
    return [{
        'device_uuid': device.device_uuid,
        'device_name': device.device_name,
        'metric_type': type.metric_type_name,
        'value': float(value.value),
        'timestamp': convert_timestamp(
            snapshot.client_timestamp_utc,
            snapshot.client_timezone_minutes,
            snapshot.server_timezone_minutes
        )
    } for snapshot, device, value, type in metrics]

def get_all_visits(db: Session) -> List[Dict[str, Any]]:
    """Get all visit records"""
    visits = db.query(Visits).all()
    return [{
        'ip_address': visit.ip_address,
        'count': visit.count,
        'last_visit': visit.last_visit
    } for visit in visits]

def get_latest_metrics_by_type(db: Session, metric_type_name: str = None) -> List[Dict[str, Any]]:
    """Get the most recent metric for each type"""
    # First get a subquery of the latest snapshot for each metric type
    latest_snapshots = (
        db.query(
            MetricTypes.metric_type_id,
            func.max(MetricSnapshots.metric_snapshot_id).label('latest_snapshot_id')
        )
        .join(MetricValues, MetricValues.metric_type_id == MetricTypes.metric_type_id)
        .join(MetricSnapshots, MetricSnapshots.metric_snapshot_id == MetricValues.metric_snapshot_id)
        .group_by(MetricTypes.metric_type_id)
        .subquery()
    )
    
    # Then join this with our main tables to get the actual values
    query = (
        db.query(MetricSnapshots, Devices, MetricValues, MetricTypes)
        .select_from(latest_snapshots)
        .join(
            MetricSnapshots,
            MetricSnapshots.metric_snapshot_id == latest_snapshots.c.latest_snapshot_id
        )
        .join(
            MetricValues,
            and_(
                MetricValues.metric_snapshot_id == MetricSnapshots.metric_snapshot_id,
                MetricValues.metric_type_id == latest_snapshots.c.metric_type_id
            )
        )
        .join(
            Devices,
            Devices.device_id == MetricSnapshots.device_id
        )
        .join(
            MetricTypes,
            MetricTypes.metric_type_id == latest_snapshots.c.metric_type_id
        )
    )
    
    if metric_type_name:
        query = query.filter(MetricTypes.metric_type_name == metric_type_name)
    
    metrics = query.all()
    
    return [{
        'device_uuid': device.device_uuid,
        'device_name': device.device_name,
        'metric_type': type.metric_type_name,
        'value': float(value.value),
        'timestamp': snapshot.server_timestamp_utc
    } for snapshot, device, value, type in metrics]

def add_metric_values(db: Session, snapshot_id: int, metrics: List[Dict]) -> None:
    """Add metric values to a snapshot

    Args:
        db (Session): Database session
        snapshot_id (int): ID of the snapshot
        metrics (List[Dict]): List of metrics to add
    """
    try:
        # First check for existing values to avoid duplicates
        for metric in metrics:
            existing = db.query(MetricValues).filter(
                MetricValues.metric_snapshot_id == snapshot_id,
                MetricValues.metric_type_id == metric['metric_type_id']
            ).first()
            
            if existing:
                # Update existing value
                existing.value = metric['value']
            else:
                # Create new value
                value = MetricValues(
                    metric_snapshot_id=snapshot_id,
                    metric_type_id=metric['metric_type_id'],
                    value=metric['value']
                )
                db.add(value)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def get_db():
    # Assuming this function is defined elsewhere in your codebase
    pass
