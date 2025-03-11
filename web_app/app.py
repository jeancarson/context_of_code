import os
import sys
import requests

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import uuid
import datetime
import requests
from flask import Flask, jsonify, send_from_directory, request, render_template
from dash import Dash, html, dcc, Input, Output, State, ctx, clientside_callback
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from decimal import Decimal
from web_app.lib.config import Config
import logging
from web_app.lib.database import init_db, get_db
from web_app.lib.models.generated_models import Aggregators, Devices, MetricTypes, MetricSnapshots, MetricValues, Visits
from web_app.lib.constants import StatusCode, HTTPStatusCode
from sqlalchemy import select, func, and_, desc, asc, text
from web_app.lib.models.dto import (
    AggregatorDTO, DeviceDTO, MetricTypeDTO, MetricSnapshotDTO, MetricValueDTO,
    convert_to_snapshot_orm, convert_to_metric_value_orm
)
from typing import Optional
from web_app.lib.services.orm_service import (
    get_all_devices,
    get_all_metric_types,
    get_recent_metrics,
    get_all_visits,
    get_latest_metrics_by_type
)
from threading import Lock
import time
from web_app.lib.services.ip_service import IPService
import math
import dash
from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import json
import threading
from lib_utils.blocktimer import BlockTimer
from web_app.lib.utils.metrics_cache import MetricsCache
from lib_utils.logger import Logger

# Compute root directory once and use it throughout the file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize configuration first
config = Config(os.path.join(ROOT_DIR, 'config.json'))

# Initialize logging using the shared logger
logger = Logger.setup_from_config("Web App", config)

# Initialize services
ip_service = IPService()

# Initialize Flask app with configuration
server = Flask(__name__)
server.config['DEBUG'] = config.debug
server.config['SECRET_KEY'] = config.server.secret_key

# Initialize Dash app
dash_app = Dash(
    __name__,
    server=server,
    url_base_pathname='/',  # Change to root path
    suppress_callback_exceptions=True,
    title="JEAN"
)

# Initialize the metrics cache with a 30-second duration
metrics_cache = MetricsCache(cache_duration_seconds=30)

# State toggle system
state_lock = Lock()
# Initialize with current time to ensure it has a valid timestamp from the start
current_time = datetime.datetime.now().isoformat()
current_state = {
    "value": "A",  # Current state value (A or B)
    "timestamp": current_time,     # When the state was last changed
    "last_toggle_time": current_time  # Track the last time the state was toggled
}


# Define the Dash layout with routing
dash_app.layout = html.Div([
    # Include Font Awesome for icons (using a different approach)
    html.Link(
        rel="stylesheet",
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"
    ),
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# Callback to handle routing
@dash_app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/':
        # Home page layout
        client_ip = get_client_ip()
        visit_count = 1
        location = get_location_from_ip(client_ip)
        
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
        
        return html.Div([
            html.Div([
                html.Div([
                    html.Div(f"You have visited this page {visit_count} time{'s' if visit_count != 1 else ''}! Why are you so obsessed with me? 🤨"),
                    html.Div(f"Visiting from: {location}", className='location-text')
                ], className='visit-banner'),
                html.Div([
                    dcc.Link('View Metrics Dashboard', href='/dashboard', className='button dashboard'),
                    html.Button('ExcecuteAggregator Actions', id='toggle-button', className='button', n_clicks=0)
                ], className='container'),
                
                # Add notification div
                html.Div(id='toggle-notification', className='notification', style={
                    'display': 'none',
                    'position': 'fixed',
                    'top': '20px',
                    'right': '20px',
                    'padding': '15px 20px',
                    'background-color': '#4CAF50',
                    'color': 'white',
                    'border-radius': '4px',
                    'box-shadow': '0 4px 8px rgba(0,0,0,0.2)',
                    'z-index': '1000',
                    'opacity': '0.9',
                    'transition': 'opacity 0.5s'
                })
            ])
        ])
    
    elif pathname == '/dashboard':
        # Dashboard layout with back button
        return html.Div([
            html.Div([
                dcc.Link('← Back to Home', href='/', className='back-button'),
                html.H1('Metrics Dashboard', className='header')
            ], className='dashboard-header'),
            
            # Hidden div for storing initialization state
            html.Div(id='initialization-div', style={'display': 'none'}),
            
            # Dashboard controls section
            html.Div([
                # Refresh button with prominent styling
                html.Button(
                    [
                        html.I(className="fas fa-sync-alt", style={"margin-right": "8px"}),
                        "Refresh Data"
                    ], 
                    id='refresh-button', 
                    className='refresh-button-prominent', 
                    n_clicks=0
                ),
                
                # Add refresh status div
                html.Div(id='refresh-status', className='refresh-status'),
                
                # Last update time display
                html.Div(id='last-update-time', className='update-info')
            ], className='dashboard-controls'),
            
            # Filters Section
            html.Div([
                html.Div([
                    html.Label('Metric Type (optional)'),
                    dcc.Dropdown(
                        id='metric-type-dropdown',
                        placeholder='Select metric type(s)',
                        options=[],
                        clearable=True,
                        multi=True
                    )
                ], className='filter-item'),
                
                html.Div([
                    html.Label('Date Range (optional)'),
                    dcc.DatePickerRange(
                        id='date-picker',
                        start_date=None,
                        end_date=None,
                        display_format='YYYY-MM-DD'
                    )
                ], className='filter-item'),
                
                html.Div([
                    html.Label('Value Range (optional)'),
                    html.Div([
                        dcc.Input(
                            id='min-value-input',
                            type='number',
                            placeholder='Min value',
                            className='value-input'
                        ),
                        html.Span('to', className='value-range-separator'),
                        dcc.Input(
                            id='max-value-input',
                            type='number',
                            placeholder='Max value',
                            className='value-input'
                        )
                    ], className='value-range-inputs')
                ], className='filter-item'),
                
                html.Div([
                    html.Label('Aggregator (optional)'),
                    dcc.Dropdown(
                        id='aggregator-dropdown',
                        placeholder='Select aggregator(s)',
                        options=[],
                        clearable=True,
                        multi=True
                    )
                ], className='filter-item'),
                
                html.Div([
                    html.Label('Device (optional)'),
                    dcc.Dropdown(
                        id='device-dropdown',
                        placeholder='Select device(s)',
                        options=[],
                        clearable=True,
                        multi=True
                    )
                ], className='filter-item'),
                
                html.Div([
                    html.Label('Sort Order'),
                    dcc.RadioItems(
                        id='sort-order',
                        options=[
                            {'label': 'Newest First', 'value': 'desc'},
                            {'label': 'Oldest First', 'value': 'asc'}
                        ],
                        value='desc',
                        className='sort-options'
                    )
                ], className='filter-item'),
            ], className='filters-container'),
            
            # Add pagination controls
            html.Div([
                html.Div([
                    html.Label('Page:'),
                    html.Button('Previous', id='prev-page-button', className='page-button'),
                    dcc.Input(
                        id='page-number',
                        type='number',
                        min=0,
                        max=99,
                        value=0,
                        className='page-input'
                    ),
                    html.Button('Next', id='next-page-button', className='page-button'),
                ], className='page-controls'),
                
                html.Div([
                    html.Label('Rows per page:'),
                    dcc.Input(
                        id='rows-per-page',
                        type='number',
                        min=10,
                        max=100,
                        step=10,
                        value=20,
                        className='rows-input'
                    ),
                ], className='rows-controls'),
                
                html.Div(id='pagination-info', className='pagination-info')
            ], className='pagination-controls'),
            
            # Visualization Section
            html.Div([
                html.Div([
                    dcc.Graph(id='metric-gauge'),
                    dcc.Graph(id='metric-history'),
                    html.Button('Toggle View', id='toggle-view-button', style={'display': 'none'})
                ], className='visualization-container', id='visualization-container'),
                
                # No data message panel
                html.Div(
                    dcc.Markdown(id='no-data-message-text', children="No visualizations for selected filters"),
                    id='no-data-message',
                    style={
                        'display': 'none',
                        'padding': '20px',
                        'textAlign': 'center',
                        'backgroundColor': '#f8f9fa',
                        'border': '1px solid #ddd',
                        'borderRadius': '4px',
                        'marginBottom': '20px',
                        'fontSize': '16px',
                        'color': '#6c757d'
                    }
                ),
                
                # Data Table
                html.Div([
                    dcc.Loading(
                        id="loading-table",
                        children=[html.Div(id='metrics-table')]
                    )
                ], className='table-container')
            ], className='content-container')
        ])
    
    return '404'

# Initialize database if running directly (not through WSGI)
if __name__ == "__main__":
    init_db()

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

# Flask routes
@server.route("/register/aggregator", methods=["POST"])
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

@server.route("/register/device", methods=["POST"])
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

@server.route("/metrics", methods=["POST"])
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

@server.route("/check-state", methods=["GET"])
def check_state():
    """Check the current state and reset it to A if it's B"""
    with state_lock:
        # Log the current state for debugging
        logger.debug(f"Checking current state: {current_state}")
        
        # Get the current state value
        current_value = current_state["value"]
        
        # Create a copy of the current state to return
        state_response = current_state.copy()
        
        # If the state is B, reset it to A after checking
        if current_value == "B":
            logger.info(f"Resetting state from B to A after check")
            current_state["value"] = "A"
            current_state["timestamp"] = datetime.datetime.now().isoformat()
        
        # Return the original state (before reset)
        return jsonify(state_response)

@server.route("/toggle-state", methods=["POST"])
def toggle_state():
    """Toggle the current state to trigger aggregator actions"""
    try:
        # Get the current time
        current_time = datetime.datetime.now()
        
        with state_lock:
            # Check if we need to enforce the delay
            if current_state["last_toggle_time"] is not None:
                # Calculate the time since the last toggle
                last_toggle = datetime.datetime.fromisoformat(current_state["last_toggle_time"])
                time_since_last_toggle = (current_time - last_toggle).total_seconds()
                
                # If it's been less than 2 seconds, don't allow the toggle
                if time_since_last_toggle < 2.0:
                    return jsonify({
                        "status": "WAIT",
                        "message": f"Please wait {2.0 - time_since_last_toggle:.1f} seconds before toggling again",
                        "state": current_state["value"],
                        "wait_time": 2.0 - time_since_last_toggle
                    })
            
            # Get the old state for logging
            old_state = current_state["value"]
            
            # Always set to state B to trigger aggregator actions
            # The check_state endpoint will reset it to A after it's been checked
            new_state = "B"
            current_state["value"] = new_state
            
            # Update timestamps
            current_time_iso = current_time.isoformat()
            current_state["timestamp"] = current_time_iso
            current_state["last_toggle_time"] = current_time_iso
            
            # Log the state change
            logger.info(f"State manually set to B to trigger aggregator actions at {current_time_iso}")
        
        return jsonify({
            "status": "SUCCESS",
            "previous_state": old_state,
            "new_state": new_state,
            "message": "Aggregator action request sent",
            "timestamp": current_time_iso
        })
    except Exception as e:
        logger.error(f"Error toggling state: {e}")
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500

@server.route("/static/<path:path>")
def send_static(path):
    """Serve static files"""
    return send_from_directory("static", path)

# Dash callbacks
@dash_app.callback(
    [Output('metric-type-dropdown', 'options'),
     Output('aggregator-dropdown', 'options'),
     Output('device-dropdown', 'options')],
    [Input('initialization-div', 'children'),
     Input('refresh-button', 'n_clicks')],  # New refresh button instead of interval
    prevent_initial_call=False
)
def populate_dropdowns(_, n_clicks):
    """Populate all dropdowns with data from the database"""
    logger.info("Populating dropdowns...")
    try:
        with get_db() as db:
            # Get metric types
            metric_types = db.query(MetricTypes).all()
            metric_options = [{'label': mt.metric_type_name, 'value': mt.metric_type_id} for mt in metric_types]
            logger.info(f"Found {len(metric_options)} metric types")
            
            # Get aggregators
            aggregators = db.query(Aggregators).all()
            aggregator_options = [{'label': agg.name, 'value': agg.aggregator_id} for agg in aggregators]
            logger.info(f"Found {len(aggregator_options)} aggregators")
            
            # Get devices
            devices = db.query(Devices).all()
            device_options = [{'label': dev.device_name, 'value': dev.device_id} for dev in devices]
            logger.info(f"Found {len(device_options)} devices")
            
            return metric_options, aggregator_options, device_options
    except Exception as e:
        logger.error(f"Error populating dropdowns: {e}")
        return [], [], []

@dash_app.callback(
    [Output('metric-gauge', 'figure'),
     Output('metric-history', 'figure'),
     Output('metrics-table', 'children'),
     Output('pagination-info', 'children'),
     Output('page-number', 'max'),
     Output('last-update-time', 'children')],
    [Input('metric-type-dropdown', 'value'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('min-value-input', 'value'),
     Input('max-value-input', 'value'),
     Input('aggregator-dropdown', 'value'),
     Input('device-dropdown', 'value'),
     Input('sort-order', 'value'),
     Input('page-number', 'value'),
     Input('rows-per-page', 'value'),
     Input('refresh-button', 'n_clicks')]
)
def update_visualizations(metric_type_id, start_date, end_date, min_value, max_value,
                         aggregator_id, device_id, sort_order, page_number, rows_per_page, n_clicks):
    """Server-side filtering and pagination of data with caching"""
    try:
        # Create a dictionary of all filter parameters for cache key generation
        filter_params = {
            'metric_type_id': metric_type_id,
            'start_date': start_date,
            'end_date': end_date,
            'min_value': min_value,
            'max_value': max_value,
            'aggregator_id': aggregator_id,
            'device_id': device_id,
            'sort_order': sort_order,
            'page_number': page_number,
            'rows_per_page': rows_per_page
        }
        
        # Check if we have a cache hit
        cached_result = metrics_cache.get_cached_data(**filter_params)
        
        # If we have a cache hit, use cached data regardless of refresh button
        if cached_result is not None:
            cached_data, age = cached_result
            
            logger.info(f"Using cached data (age: {age:.1f}s)")
            
            # Unpack the cached data
            gauge, history, table, pagination_info, total_pages, original_update_time = cached_data
            
            # Update the last update time to show it's from cache and include the original query time
            # Extract the original query time if it exists
            query_time_info = ""
            if isinstance(original_update_time, str) and "Query time:" in original_update_time:
                query_time_parts = original_update_time.split("Query time:")
                if len(query_time_parts) > 1:
                    query_time_info = f"Query time:{query_time_parts[1].split(')')[0]})"
            
            # Format the timestamp part
            timestamp_part = original_update_time.split(" (")[0] if " (" in original_update_time else original_update_time
            
            # Create the updated message
            last_update_time = f"{timestamp_part} ({query_time_info} [Cached: {age:.1f}s old]"
            
            return gauge, history, table, pagination_info, total_pages, last_update_time
        
        # Use BlockTimer for performance measurement
        with BlockTimer("update_visualizations", logger) as timer:
            # Default page number to 0 if None
            if page_number is None:
                page_number = 0
                
            # Default rows per page to 20 if None
            if rows_per_page is None:
                rows_per_page = 20
                
            logger.info(f"Fetching page {page_number} with {rows_per_page} rows per page")
            logger.info(f"Filters: metric_type={metric_type_id}, aggregator={aggregator_id}, device={device_id}")
            
            with get_db() as db:
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
                    start_date = pd.to_datetime(start_date)
                    # Convert pandas Timestamp to Python datetime object
                    start_date = start_date.to_pydatetime()
                    base_query = base_query.filter(MetricSnapshots.client_timestamp_utc >= start_date)
                if end_date:
                    end_date = pd.to_datetime(end_date)
                    # Convert pandas Timestamp to Python datetime object
                    end_date = end_date.to_pydatetime()
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
                    base_query = base_query.order_by(asc(MetricSnapshots.client_timestamp_utc))
                    
                # Get total count for pagination
                count_query = base_query.with_entities(func.count())
                total_rows = count_query.scalar()
                logger.info(f"Total filtered records: {total_rows}")
                
                # Calculate total pages
                total_pages = max(1, math.ceil(total_rows / rows_per_page))
                
                # Ensure page_number is valid
                page_number = max(0, min(page_number, total_pages - 1))
                
                # Apply pagination
                offset = page_number * rows_per_page
                base_query = base_query.offset(offset).limit(rows_per_page)
                
                # Execute query
                results = base_query.all()
                logger.info(f"Fetched {len(results)} records for current page")
                
                # Convert to list of dicts
                data = [{
                    'value': float(r.value) if isinstance(r.value, Decimal) else r.value,
                    'timestamp': r.client_timestamp_utc.isoformat() if hasattr(r.client_timestamp_utc, 'isoformat') else r.client_timestamp_utc,
                    'device': r.device_name,
                    'aggregator': r.aggregator_name,
                    'metric_type': r.metric_type_name,
                    'metric_type_id': r.metric_type_id
                } for r in results]
                
                # Convert to DataFrame for visualization
                df = pd.DataFrame(data)
                
                # Handle empty results
                if df.empty:
                    empty_result = ({}, {}, html.Div('No data matches the selected filters.'), '', total_pages - 1, f"Error: No data matches the selected filters.")
                    # Don't cache empty results
                    return empty_result
                    
                # Convert timestamp strings to datetime objects for visualization
                try:
                    # Try to convert timestamps to datetime with flexible parsing
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
                    
                    # Drop any rows where timestamp conversion failed
                    df = df.dropna(subset=['timestamp'])
                    
                    if df.empty:
                        logger.warning("All timestamp conversions failed, table will be empty")
                        empty_result = ({}, {}, html.Div('Error converting timestamps, no valid data to display.'), '', total_pages - 1, "Error: Failed to parse timestamps")
                        # Don't cache empty results
                        return empty_result
                except Exception as e:
                    logger.error(f"Error converting timestamps: {e}")
                    error_result = ({}, {}, html.Div(f'Error converting timestamps: {str(e)}'), '', total_pages - 1, f"Error: {str(e)}")
                    # Don't cache error results
                    return error_result
                
                # Create table with formatted timestamps
                df_display = df.copy()
                df_display['timestamp'] = df_display['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                df_display['value'] = df_display['value'].round(4)
                df_display = df_display.drop('metric_type_id', axis=1)
                table = html.Table(
                    [html.Tr([html.Th(col) for col in df_display.columns])] +
                    [html.Tr([html.Td(df_display.iloc[i][col]) for col in df_display.columns])
                     for i in range(len(df_display))]
                )
                
                # Get the current time for the last update timestamp
                end_time = datetime.datetime.now()
                
                # Use the timer's elapsed_time_ms method to get the query time
                query_time_ms = timer.elapsed_time_ms()
                query_time_sec = query_time_ms / 1000  # Convert to seconds
                
                # Format the last update timestamp
                last_update_time = f"Last updated: {end_time.strftime('%Y-%m-%d %H:%M:%S')} (Query time: {query_time_sec:.3f}s)"
                
                pagination_info = html.Div([
                    html.Span(f"Page {page_number + 1} of {total_pages} "),
                    html.Span(f"(Showing {len(results)} of {total_rows} total records)"),
                    html.Span(f" - Query time: {query_time_sec:.3f}s", style={"font-style": "italic", "margin-left": "10px"})
                ])
                
                # Only create visualizations if exactly one metric type is selected and we have data
                if metric_type_id and len(metric_type_id) == 1 and not df.empty:
                    single_metric_id = metric_type_id[0]  # Get the single selected metric ID
                    # DUAL-QUERY APPROACH:
                    # 1. For the table, we only fetch the current page of data (e.g., 20 records)
                    # 2. For visualizations, we need more historical context, so we fetch more records
                    # This balances:
                    #   - Efficiency: We don't load everything for the table
                    #   - Context: Charts have enough data to be meaningful
                    #   - Performance: We limit the visualization data to 1000 records
                    
                    # Get additional data for visualizations (limited to 1000 records)
                    vis_query = (db.query(
                        MetricValues.value,
                        MetricSnapshots.client_timestamp_utc
                    )
                    .select_from(MetricValues)
                    .join(
                        MetricSnapshots,
                        MetricValues.metric_snapshot_id == MetricSnapshots.metric_snapshot_id
                    )
                    .filter(MetricValues.metric_type_id == single_metric_id)
                    .order_by(desc(MetricSnapshots.client_timestamp_utc))
                    .limit(1000))
                    
                    vis_results = vis_query.all()
                    vis_data = [{
                        'value': float(r.value) if isinstance(r.value, Decimal) else r.value,
                        'timestamp': r.client_timestamp_utc.isoformat() if hasattr(r.client_timestamp_utc, 'isoformat') else r.client_timestamp_utc
                    } for r in vis_results]
                    
                    vis_df = pd.DataFrame(vis_data)
                    
                    # Use a more flexible datetime parsing approach
                    try:
                        # Try to convert timestamps to datetime with flexible parsing
                        vis_df['timestamp'] = pd.to_datetime(vis_df['timestamp'], format='mixed', errors='coerce')
                        
                        # Drop any rows where timestamp conversion failed
                        vis_df = vis_df.dropna(subset=['timestamp'])
                        
                        if vis_df.empty:
                            logger.warning("All timestamp conversions failed, visualization will be empty")
                            result = ({}, {}, table, pagination_info, total_pages - 1, last_update_time)
                            metrics_cache.set_cached_data(result, **filter_params)
                            return result
                    except Exception as e:
                        logger.error(f"Error converting timestamps: {e}")
                        error_result = ({}, {}, table, pagination_info, total_pages - 1, f"Error with visualization data: {str(e)}")
                        # Don't cache error results
                        return error_result
                    
                    # Get the most recent value
                    latest_value = float(vis_df.iloc[0]['value'])
                    
                    # Get historical min/max for gauge range
                    min_val = float(vis_df['value'].min())
                    max_val = float(vis_df['value'].max())
                    
                    # Add padding to range
                    range_padding = (max_val - min_val) * 0.05 if max_val != min_val else max_val * 0.05
                    min_val = min_val - range_padding
                    max_val = max_val + range_padding
                    
                    # Create gauge with historical context
                    gauge = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=latest_value,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': f"Latest Value ({df['metric_type'].iloc[0]})"},
                        number={'valueformat': '.4g'},
                        gauge={
                            'axis': {'range': [min_val, max_val]},
                            'bar': {'color': "darkblue"},
                            'steps': [
                                {'range': [min_val, (max_val + min_val)/2], 'color': "lightgray"},
                                {'range': [(max_val + min_val)/2, max_val], 'color': "gray"}
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': latest_value
                            }
                        }
                    ))
                    
                    # Create history graph
                    history = px.line(
                        vis_df.sort_values('timestamp'), 
                        x='timestamp', 
                        y='value',
                        title=f"Historical Values for {df['metric_type'].iloc[0]}"
                    )
                    history.update_layout(
                        xaxis_title="Timestamp",
                        yaxis_title="Value",
                        yaxis_range=[min_val, max_val]
                    )
                    
                    # At the end, before returning the result, cache it
                    result = (gauge, history, table, pagination_info, total_pages - 1, last_update_time)
                    metrics_cache.set_cached_data(result, **filter_params)
                    
                    return result
                else:
                    # Create a message figure for when no metric is selected
                    message_fig = go.Figure()
                    message_fig.add_annotation(
                        text="Please select a metric to view visualizations",
                        xref="paper", yref="paper",
                        x=0.5, y=0.5,
                        showarrow=False,
                        font=dict(size=16)
                    )
                    message_fig.update_layout(
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                    )
                    
                    # Return the message figure for both visualizations
                    result = (message_fig, message_fig, table, pagination_info, total_pages - 1, last_update_time)
                    metrics_cache.set_cached_data(result, **filter_params)
                    return result
                
    except Exception as e:
        logger.error(f"Error updating visualizations: {e}")
        error_result = ({}, {}, html.Div(f'Error loading data: {str(e)}'), '', 0, f"Error: {str(e)}")
        # Don't cache error results
        return error_result

# Callback to control visualization container visibility
@dash_app.callback(
    [Output('visualization-container', 'style'),
     Output('no-data-message', 'style'),
     Output('no-data-message-text', 'children')],
    [Input('metric-type-dropdown', 'value'),
     Input('metric-gauge', 'figure')]
)
def toggle_visualization_visibility(metric_type_id, gauge_figure):
    # Check if we have exactly one metric selected and a valid gauge figure
    if (metric_type_id and len(metric_type_id) == 1 and 
        gauge_figure and 'data' in gauge_figure and len(gauge_figure['data']) > 0):
        # Show visualizations, hide message
        return {'display': 'block'}, {'display': 'none'}, ""
    else:
        # Hide visualizations, show message
        message_text = "No visualizations for selected filters"
        if not metric_type_id:
            message_text = "Please select a metric to view visualizations"
        elif len(metric_type_id) > 1:
            message_text = "Please select only one metric type to view visualizations"
            
        return {'display': 'none'}, {
            'display': 'block',
            'padding': '20px',
            'textAlign': 'center',
            'backgroundColor': '#f8f9fa',
            'border': '1px solid #ddd',
            'borderRadius': '4px',
            'marginBottom': '20px',
            'fontSize': '16px',
            'color': '#6c757d'
        }, message_text

# Update page number when prev/next buttons are clicked
@dash_app.callback(
    Output('page-number', 'value'),
    [Input('prev-page-button', 'n_clicks'),
     Input('next-page-button', 'n_clicks')],
    [State('page-number', 'value'),
     State('page-number', 'max')],
    prevent_initial_call=True
)
def update_page_number(prev_clicks, next_clicks, current_page, max_page):
    """Update page number based on prev/next button clicks"""
    # Determine which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_page
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'prev-page-button' and current_page > 0:
        return current_page - 1
    elif button_id == 'next-page-button' and current_page < max_page:
        return current_page + 1
    else:
        return current_page

# Replace the existing refresh button callback with this simplified version
@dash_app.callback(
    Output('refresh-status', 'children'),
    [Input('refresh-button', 'n_clicks')]
)
def handle_refresh_click(n_clicks):
    """Handle refresh button clicks - just show a status message"""
    if not n_clicks:
        return ""
    
    # Simply indicate that refresh was requested, but don't invalidate cache
    return html.Div("Refresh requested - using cached data if available", 
                   style={"color": "green", "margin-top": "5px", "font-style": "italic"})

# Remove the clientside_callback and add a regular Dash callback
@dash_app.callback(
    [Output('toggle-notification', 'children'),
     Output('toggle-notification', 'style'),
     Output('toggle-button', 'disabled')],
    Input('toggle-button', 'n_clicks'),
    prevent_initial_call=True
)
def handle_toggle_button(n_clicks):
    if n_clicks:
        # Always disable the button immediately when clicked
        # This prevents rapid clicking and provides immediate visual feedback
        try:
            # Toggle the state to trigger aggregator actions
            # Use request.url_root to get the base URL of the current server
            toggle_response = requests.post(f"{request.url_root}toggle-state")
            
            if toggle_response.status_code == 200:
                response_data = toggle_response.json()
                
                # If we get a success response, show the success notification
                if response_data.get("status") == "SUCCESS":
                    # Create a prettier notification about the aggregator actions
                    notification = html.Div([
                        html.Div([
                            html.I(className="fas fa-cogs", style={
                                "font-size": "24px",
                                "margin-right": "10px",
                                "color": "#4CAF50"
                            }),
                            html.Span("Action Request Sent", style={
                                "font-weight": "bold",
                                "font-size": "18px"
                            })
                        ], style={"display": "flex", "align-items": "center", "margin-bottom": "10px"}),
                        html.P("The action request has been sent to connected aggregators.", 
                               style={"margin-bottom": "15px", "color": "#555"}),
                        html.Button([
                            html.I(className="fas fa-times", style={"margin-right": "5px"}),
                            "Close"
                        ], id="close-notification", className="btn btn-sm btn-outline-secondary")
                    ], style={"padding": "15px"})
                    
                    # Return the notification with improved styling
                    notification_style = {
                        'display': 'block',
                        'position': 'fixed',
                        'top': '20px',
                        'right': '20px',
                        'padding': '0',
                        'background-color': 'white',
                        'color': '#333',
                        'border-radius': '8px',
                        'box-shadow': '0 4px 12px rgba(0,0,0,0.15)',
                        'z-index': '1000',
                        'min-width': '300px',
                        'max-width': '400px',
                        'border-left': '4px solid #4CAF50',
                        'transition': 'opacity 0.3s ease-out, transform 0.3s ease-out'
                    }
                    
                    return notification, notification_style, True
                # If we get a WAIT response, just disable the button without showing any notification
                elif response_data.get("status") == "WAIT":
                    # Just disable the button without showing an error notification
                    return dash.no_update, {'display': 'none'}, True
                # For other errors, show an error notification but still disable the button
                else:
                    # Handle error in toggle request with prettier styling
                    error_message = response_data.get('message', 'Unknown error')
                    notification = html.Div([
                        html.Div([
                            html.I(className="fas fa-exclamation-triangle", style={
                                "font-size": "24px",
                                "margin-right": "10px",
                                "color": "#f44336"
                            }),
                            html.Span("Error", style={
                                "font-weight": "bold",
                                "font-size": "18px"
                            })
                        ], style={"display": "flex", "align-items": "center", "margin-bottom": "10px"}),
                        html.P(f"Error sending action request: {error_message}", 
                               style={"margin-bottom": "15px", "color": "#555"}),
                        html.Button([
                            html.I(className="fas fa-times", style={"margin-right": "5px"}),
                            "Close"
                        ], id="close-notification", className="btn btn-sm btn-outline-secondary")
                    ], style={"padding": "15px"})
                    
                    # Return the error notification with improved styling
                    error_style = {
                        'display': 'block',
                        'position': 'fixed',
                        'top': '20px',
                        'right': '20px',
                        'padding': '0',
                        'background-color': 'white',
                        'color': '#333',
                        'border-radius': '8px',
                        'box-shadow': '0 4px 12px rgba(0,0,0,0.15)',
                        'z-index': '1000',
                        'min-width': '300px',
                        'max-width': '400px',
                        'border-left': '4px solid #f44336',
                        'transition': 'opacity 0.3s ease-out, transform 0.3s ease-out'
                    }
                    
                    return notification, error_style, True
            else:
                # Handle HTTP error with prettier styling
                notification = html.Div([
                    html.Div([
                        html.I(className="fas fa-exclamation-circle", style={
                            "font-size": "24px",
                            "margin-right": "10px",
                            "color": "#ff9800"
                        }),
                        html.Span("HTTP Error", style={
                            "font-weight": "bold",
                            "font-size": "18px"
                        })
                    ], style={"display": "flex", "align-items": "center", "margin-bottom": "10px"}),
                    html.P(f"Error: HTTP {toggle_response.status_code}", 
                           style={"margin-bottom": "15px", "color": "#555"}),
                    html.Button([
                        html.I(className="fas fa-times", style={"margin-right": "5px"}),
                        "Close"
                    ], id="close-notification", className="btn btn-sm btn-outline-secondary")
                ], style={"padding": "15px"})
                
                # Return the HTTP error notification with improved styling
                http_error_style = {
                    'display': 'block',
                    'position': 'fixed',
                    'top': '20px',
                    'right': '20px',
                    'padding': '0',
                    'background-color': 'white',
                    'color': '#333',
                    'border-radius': '8px',
                    'box-shadow': '0 4px 12px rgba(0,0,0,0.15)',
                    'z-index': '1000',
                    'min-width': '300px',
                    'max-width': '400px',
                    'border-left': '4px solid #ff9800',
                    'transition': 'opacity 0.3s ease-out, transform 0.3s ease-out'
                }
                
                return notification, http_error_style, True
        except Exception as e:
            # Handle any other exceptions with prettier styling
            notification = html.Div([
                html.Div([
                    html.I(className="fas fa-bug", style={
                        "font-size": "24px",
                        "margin-right": "10px",
                        "color": "#9c27b0"
                    }),
                    html.Span("Exception", style={
                        "font-weight": "bold",
                        "font-size": "18px"
                    })
                ], style={"display": "flex", "align-items": "center", "margin-bottom": "10px"}),
                html.P(f"Error: {str(e)}", 
                       style={"margin-bottom": "15px", "color": "#555"}),
                html.Button([
                    html.I(className="fas fa-times", style={"margin-right": "5px"}),
                    "Close"
                ], id="close-notification", className="btn btn-sm btn-outline-secondary")
            ], style={"padding": "15px"})
            
            # Return the exception notification with improved styling
            exception_style = {
                'display': 'block',
                'position': 'fixed',
                'top': '20px',
                'right': '20px',
                'padding': '0',
                'background-color': 'white',
                'color': '#333',
                'border-radius': '8px',
                'box-shadow': '0 4px 12px rgba(0,0,0,0.15)',
                'z-index': '1000',
                'min-width': '300px',
                'max-width': '400px',
                'border-left': '4px solid #9c27b0',
                'transition': 'opacity 0.3s ease-out, transform 0.3s ease-out'
            }
            
            return notification, exception_style, True
    
    # Default return if n_clicks is None
    return dash.no_update, dash.no_update, dash.no_update

# Add callback to close the notification
@dash_app.callback(
    Output('toggle-notification', 'style', allow_duplicate=True),
    Input('close-notification', 'n_clicks'),
    prevent_initial_call=True
)
def close_notification(n_clicks):
    """Close the notification when the close button is clicked"""
    if n_clicks:
        return {'display': 'none'}
    return dash.no_update

# Add callback to re-enable the button after 2 seconds
@dash_app.callback(
    Output('toggle-button', 'disabled', allow_duplicate=True),
    Input('toggle-button', 'disabled'),
    prevent_initial_call=True
)
def enable_button_after_delay(disabled):
    """Re-enable the button after a 2-second delay"""
    if disabled:
        # Use a fixed delay of 2 seconds to ensure the button is disabled long enough
        time.sleep(2)
        return False
    return dash.no_update

if __name__ == '__main__':
    try:
        # Initialize database
        init_db()
        logger.info("Database initialized")
        
        # Start the Flask app
        server.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

# Make the app variable available for WSGI
application = server