from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session
from ..models.generated_models import Devices, MetricTypes, MetricSnapshots, MetricValues, Visits, Aggregators
from typing import List, Dict, Any
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
import math

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

def get_or_create_visit(db: Session, ip_address: str) -> tuple:
    """Get or create a visit record for an IP address
    
    Args:
        db (Session): Database session
        ip_address (str): IP address of the visitor
        
    Returns:
        tuple: (visit_record, visit_count, is_new)
    """
    visit = db.query(Visits).filter(Visits.ip_address == ip_address).first()
    is_new = False
    
    if visit:
        visit.count += 1
        visit.last_visit = datetime.now()
        visit_count = visit.count
    else:
        is_new = True
        visit = Visits(
            ip_address=ip_address,
            count=1,
            last_visit=datetime.now()
        )
        db.add(visit)
        visit_count = 1
    
    db.commit()
    return visit, visit_count, is_new

def get_aggregator_by_uuid(db: Session, aggregator_uuid: str) -> Aggregators:
    """Get an aggregator by UUID
    
    Args:
        db (Session): Database session
        aggregator_uuid (str): UUID of the aggregator
        
    Returns:
        Aggregators: Aggregator record or None if not found
    """
    return db.query(Aggregators).filter(
        Aggregators.aggregator_uuid == aggregator_uuid
    ).first()

def create_aggregator(db: Session, aggregator_uuid: str, name: str) -> Aggregators:
    """Create a new aggregator
    
    Args:
        db (Session): Database session
        aggregator_uuid (str): UUID of the aggregator
        name (str): Name of the aggregator
        
    Returns:
        Aggregators: Created aggregator record
    """
    aggregator = Aggregators(
        aggregator_uuid=aggregator_uuid,
        name=name,
        created_at=str(datetime.utcnow())
    )
    db.add(aggregator)
    db.commit()
    return aggregator

def get_device_by_uuid(db: Session, device_uuid: str) -> Devices:
    """Get a device by UUID
    
    Args:
        db (Session): Database session
        device_uuid (str): UUID of the device
        
    Returns:
        Devices: Device record or None if not found
    """
    return db.query(Devices).filter(
        Devices.device_uuid == device_uuid
    ).first()

def create_device(db: Session, device_uuid: str, device_name: str, aggregator_id: int) -> Devices:
    """Create a new device
    
    Args:
        db (Session): Database session
        device_uuid (str): UUID of the device
        device_name (str): Name of the device
        aggregator_id (int): ID of the aggregator
        
    Returns:
        Devices: Created device record
    """
    device = Devices(
        device_uuid=device_uuid,
        device_name=device_name,
        aggregator_id=aggregator_id,
        created_at=str(datetime.utcnow())
    )
    db.add(device)
    db.commit()
    return device

def create_metric_snapshot(db: Session, device_id: int, client_timestamp: str, 
                          client_timezone: int, server_timezone: int) -> MetricSnapshots:
    """Create a new metric snapshot
    
    Args:
        db (Session): Database session
        device_id (int): ID of the device
        client_timestamp (str): Client timestamp
        client_timezone (int): Client timezone offset in minutes
        server_timezone (int): Server timezone offset in minutes
        
    Returns:
        MetricSnapshots: Created snapshot record
    """
    snapshot = MetricSnapshots(
        device_id=device_id,
        client_timestamp_utc=client_timestamp,
        client_timezone_minutes=client_timezone,
        server_timestamp_utc=datetime.utcnow(),
        server_timezone_minutes=server_timezone
    )
    db.add(snapshot)
    db.flush()  # Get the snapshot ID without committing
    return snapshot

def get_or_create_metric_type(db: Session, device_id: int, metric_type_name: str) -> MetricTypes:
    """Get or create a metric type
    
    Args:
        db (Session): Database session
        device_id (int): ID of the device
        metric_type_name (str): Name of the metric type
        
    Returns:
        MetricTypes: Metric type record
    """
    metric_type = db.query(MetricTypes).filter(
        MetricTypes.metric_type_name == metric_type_name
    ).first()
    
    if not metric_type:
        metric_type = MetricTypes(
            device_id=device_id,
            metric_type_name=metric_type_name,
            created_at=str(datetime.utcnow())
        )
        db.add(metric_type)
        db.flush()  # Get the new metric type ID without committing
    
    return metric_type

def add_or_update_metric_value(db: Session, snapshot_id: int, metric_type_id: int, value: float) -> MetricValues:
    """Add or update a metric value
    
    Args:
        db (Session): Database session
        snapshot_id (int): ID of the snapshot
        metric_type_id (int): ID of the metric type
        value (float): Metric value
        
    Returns:
        MetricValues: Metric value record
    """
    existing = db.query(MetricValues).filter(
        MetricValues.metric_snapshot_id == snapshot_id,
        MetricValues.metric_type_id == metric_type_id
    ).first()
    
    if existing:
        existing.value = value
        return existing
    else:
        value_record = MetricValues(
            metric_snapshot_id=snapshot_id,
            metric_type_id=metric_type_id,
            value=value
        )
        db.add(value_record)
        return value_record

def add_metrics_batch(db: Session, device_uuid: str, client_timestamp: str, 
                     client_timezone: int, metrics: List[Dict]) -> None:
    """Add a batch of metrics for a device
    
    Args:
        db (Session): Database session
        device_uuid (str): UUID of the device
        client_timestamp (str): Client timestamp
        client_timezone (int): Client timezone offset in minutes
        metrics (List[Dict]): List of metrics to add
    """
    try:
        # Get device
        device = get_device_by_uuid(db, device_uuid)
        if not device:
            raise ValueError(f"Device not found: {device_uuid}")

        # Create snapshot
        server_timezone = -datetime.now().astimezone().utcoffset().total_seconds() // 60
        snapshot = create_metric_snapshot(db, device.device_id, client_timestamp, 
                                         client_timezone, server_timezone)

        # Add metric values
        for metric in metrics:
            metric_type = get_or_create_metric_type(db, device.device_id, metric['type'])
            add_or_update_metric_value(db, snapshot.metric_snapshot_id, metric_type.metric_type_id, metric['value'])

        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def get_dropdown_options(db: Session) -> tuple:
    """Get options for all dropdowns
    
    Args:
        db (Session): Database session
        
    Returns:
        tuple: (metric_options, aggregator_options, device_options)
    """
    # Get metric types
    metric_types = db.query(MetricTypes).all()
    metric_options = [{'label': mt.metric_type_name, 'value': mt.metric_type_id} for mt in metric_types]
    
    # Get aggregators
    aggregators = db.query(Aggregators).all()
    aggregator_options = [{'label': agg.name, 'value': agg.aggregator_id} for agg in aggregators]
    
    # Get devices
    devices = db.query(Devices).all()
    device_options = [{'label': dev.device_name, 'value': dev.device_id} for dev in devices]
    
    return metric_options, aggregator_options, device_options

def get_filtered_metrics(db: Session, metric_type_id=None, start_date=None, end_date=None, 
                        min_value=None, max_value=None, aggregator_id=None, device_id=None, 
                        sort_order='desc', page_number=0, rows_per_page=20) -> tuple:
    """Get filtered metrics with pagination
    
    Args:
        db (Session): Database session
        metric_type_id: Optional filter by metric type ID
        start_date: Optional filter by start date
        end_date: Optional filter by end date
        min_value: Optional filter by minimum value
        max_value: Optional filter by maximum value
        aggregator_id: Optional filter by aggregator ID
        device_id: Optional filter by device ID
        sort_order: Sort order ('asc' or 'desc')
        page_number: Page number (0-indexed)
        rows_per_page: Number of rows per page
        
    Returns:
        tuple: (results, total_rows, total_pages)
    """
    # Build the base query with all joins
    base_query = (db.query(
        MetricValues.value,
        MetricSnapshots.client_timestamp_utc,
        Devices.device_name,
        Aggregators.name.label('aggregator_name'),
        MetricTypes.metric_type_name,
        MetricTypes.metric_type_id
    )
    .select_from(MetricValues)
    .join(
        MetricSnapshots,
        MetricValues.metric_snapshot_id == MetricSnapshots.metric_snapshot_id
    )
    .join(
        Devices,
        MetricSnapshots.device_id == Devices.device_id
    )
    .join(
        Aggregators,
        Devices.aggregator_id == Aggregators.aggregator_id
    )
    .join(
        MetricTypes,
        MetricValues.metric_type_id == MetricTypes.metric_type_id
    ))
    
    # Apply filters
    if metric_type_id:
        base_query = base_query.filter(MetricTypes.metric_type_id.in_(metric_type_id))
    if start_date:
        # Convert pandas Timestamp to Python datetime object if needed
        if isinstance(start_date, pd.Timestamp) or isinstance(start_date, str):
            start_date = pd.to_datetime(start_date).to_pydatetime()
        base_query = base_query.filter(MetricSnapshots.client_timestamp_utc >= start_date)
    if end_date:
        # Convert pandas Timestamp to Python datetime object if needed
        if isinstance(end_date, pd.Timestamp) or isinstance(end_date, str):
            end_date = pd.to_datetime(end_date).to_pydatetime()
        base_query = base_query.filter(MetricSnapshots.client_timestamp_utc <= end_date)
    if min_value is not None:
        base_query = base_query.filter(MetricValues.value >= min_value)
    if max_value is not None:
        base_query = base_query.filter(MetricValues.value <= max_value)
    if aggregator_id:
        base_query = base_query.filter(Aggregators.aggregator_id.in_(aggregator_id))
    if device_id:
        base_query = base_query.filter(Devices.device_id.in_(device_id))
        
    # Apply sorting
    if sort_order == 'desc':
        base_query = base_query.order_by(desc(MetricSnapshots.client_timestamp_utc))
    else:
        base_query = base_query.order_by(MetricSnapshots.client_timestamp_utc)
        
    # Get total count for pagination
    count_query = base_query.with_entities(func.count())
    total_rows = count_query.scalar()
    
    # Calculate total pages
    total_pages = max(1, math.ceil(total_rows / rows_per_page))
    
    # Ensure page_number is valid
    page_number = max(0, min(page_number, total_pages - 1))
    
    # Apply pagination
    offset = page_number * rows_per_page
    base_query = base_query.offset(offset).limit(rows_per_page)
    
    # Execute query
    results = base_query.all()
    
    return results, total_rows, total_pages

def get_visualization_data(db: Session, metric_type_id: int, limit: int = 1000) -> list:
    """Get data for visualization for a specific metric type
    
    Args:
        db (Session): Database session
        metric_type_id: Metric type ID
        limit: Maximum number of records to return
        
    Returns:
        list: Query results
    """
    # Get additional data for visualizations
    vis_query = (db.query(
        MetricValues.value,
        MetricSnapshots.client_timestamp_utc
    )
    .select_from(MetricValues)
    .join(
        MetricSnapshots,
        MetricValues.metric_snapshot_id == MetricSnapshots.metric_snapshot_id
    )
    .filter(MetricValues.metric_type_id == metric_type_id)
    .order_by(desc(MetricSnapshots.client_timestamp_utc))
    .limit(limit))
    
    return vis_query.all()


