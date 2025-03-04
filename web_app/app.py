import os
import uuid
import datetime
import requests
from flask import Flask, jsonify, send_from_directory, request, render_template
from dash import Dash, html, dcc, Input, Output, State, ctx
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
import sys
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
from web_app.lib.ip_service import IPService

# Compute root directory once and use it throughout the file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize logging first
logger = logging.getLogger(__name__)
config = Config(os.path.join(ROOT_DIR, 'config.json'))
config.setup_logging()

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
    url_base_pathname='/dashboard/',
    suppress_callback_exceptions=True, 
    title="METRICS"
)

# Define the Dash layout
dash_app.layout = html.Div([
    html.H1('Metrics Dashboard', className='header'),
    
    # Hidden div for storing initialization state
    html.Div(id='initialization-div', style={'display': 'none'}),
    
    # Add interval component for automatic updates (every 5 seconds)
    dcc.Interval(
        id='interval-component',
        interval=30*1000,  # in milliseconds
        n_intervals=0
    ),
    
    # Filters Section
    html.Div([
        html.Div([
            html.Label('Metric Type (optional)'),
            dcc.Dropdown(
                id='metric-type-dropdown',
                placeholder='Select a metric type',
                options=[],
                clearable=True
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
                placeholder='Select an aggregator',
                options=[],
                clearable=True
            )
        ], className='filter-item'),
        
        html.Div([
            html.Label('Device (optional)'),
            dcc.Dropdown(
                id='device-dropdown',
                placeholder='Select a device',
                options=[],
                clearable=True
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
    
    # Add last update time display
    html.Div(id='last-update-time', className='update-info'),
    
    # Visualization Section
    html.Div([
        html.Div([
            dcc.Graph(id='metric-gauge', style={'display': 'none'}),
            dcc.Graph(id='metric-history', style={'display': 'none'}),
            html.Button('Toggle View', id='toggle-view-button', style={'display': 'none'})
        ], className='visualization-container'),
        
        # Data Table
        html.Div([
            dcc.Loading(
                id="loading-table",
                children=[html.Div(id='metrics-table')]
            )
        ], className='table-container')
    ], className='content-container')
])

calculator_lock = Lock()
calculator_state = "A"  # Toggle between "A" and "B"

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
@server.route("/")
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

@server.route("/toggle-calculator", methods=["POST"])
def toggle_calculator():
    """Toggle calculator state between A and B"""
    global calculator_state
    with calculator_lock:
        calculator_state = "B" if calculator_state == "A" else "A"
        return jsonify({
            "calculator_state": calculator_state,
            "calculator_requested": True
        })

@server.route("/check-calculator", methods=["GET"])
def check_calculator():
    """Return current calculator state"""
    global calculator_state
    with calculator_lock:
        return jsonify({
            "calculator_state": calculator_state
        })

@server.route("/debug")
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
     Input('interval-component', 'n_intervals')],  # Add interval trigger
    prevent_initial_call=False
)
def populate_dropdowns(_, n_intervals):
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
     Output('metric-gauge', 'style'),
     Output('metric-history', 'style'),
     Output('toggle-view-button', 'style'),
     Output('metrics-table', 'children'),
     Output('last-update-time', 'children')],  # Add output for update time
    [Input('metric-type-dropdown', 'value'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('min-value-input', 'value'),
     Input('max-value-input', 'value'),
     Input('aggregator-dropdown', 'value'),
     Input('device-dropdown', 'value'),
     Input('sort-order', 'value'),
     Input('toggle-view-button', 'n_clicks'),
     Input('interval-component', 'n_intervals')],  # Add interval trigger
)
def update_visualizations(metric_type_id, start_date, end_date, min_value, max_value,
                         aggregator_id, device_id, sort_order, n_clicks, n_intervals):
    """Update all visualizations based on selected filters"""
    show_gauge = bool(n_clicks and n_clicks % 2 == 0) if n_clicks else True
    logger.info(f"Updating visualizations with metric_type_id={metric_type_id}")
    
    try:
        with get_db() as db:
            # Build base query
            base_query = db.query(
                MetricValues.value,
                MetricSnapshots.client_timestamp_utc,
                Devices.device_name,
                Aggregators.name.label('aggregator_name'),
                MetricTypes.metric_type_name,
                MetricTypes.metric_type_id
            ).select_from(MetricValues).join(
                MetricSnapshots,
                MetricValues.metric_snapshot_id == MetricSnapshots.metric_snapshot_id
            ).join(
                Devices,
                MetricSnapshots.device_id == Devices.device_id
            ).join(
                Aggregators,
                Devices.aggregator_id == Aggregators.aggregator_id
            ).join(
                MetricTypes,
                MetricValues.metric_type_id == MetricTypes.metric_type_id
            )
            
            # Apply filters
            if metric_type_id:
                base_query = base_query.filter(MetricTypes.metric_type_id == metric_type_id)
            if start_date:
                base_query = base_query.filter(MetricSnapshots.client_timestamp_utc >= start_date)
            if end_date:
                base_query = base_query.filter(MetricSnapshots.client_timestamp_utc <= end_date)
            if min_value is not None:
                base_query = base_query.filter(MetricValues.value >= min_value)
            if max_value is not None:
                base_query = base_query.filter(MetricValues.value <= max_value)
            if aggregator_id:
                base_query = base_query.filter(Aggregators.aggregator_id == aggregator_id)
            if device_id:
                base_query = base_query.filter(Devices.device_id == device_id)
            
            # Apply sorting
            if sort_order == 'desc':
                base_query = base_query.order_by(desc(MetricSnapshots.client_timestamp_utc))
            else:
                base_query = base_query.order_by(asc(MetricSnapshots.client_timestamp_utc))
            
            results = base_query.all()
            logger.info(f"Found {len(results)} results")
            
            # Convert to pandas DataFrame with proper decimal handling
            df = pd.DataFrame([
                {
                    'value': float(r.value) if isinstance(r.value, Decimal) else r.value,
                    'timestamp': pd.to_datetime(r.client_timestamp_utc),
                    'device': r.device_name,
                    'aggregator': r.aggregator_name,
                    'metric_type': r.metric_type_name,
                    'metric_type_id': r.metric_type_id
                }
                for r in results
            ])
            
            if df.empty:
                return {}, {}, {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, html.Div('No data available'), 'No data available'
            
            # Create table with formatted timestamps
            df_display = df.copy()
            df_display['timestamp'] = df_display['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df_display['value'] = df_display['value'].round(4)
            df_display = df_display.drop('metric_type_id', axis=1)
            table = html.Table(
                [html.Tr([html.Th(col) for col in df_display.columns])] +
                [html.Tr([html.Td(df_display.iloc[i][col]) for col in df_display.columns])
                 for i in range(min(len(df_display), 10))]
            )
            
            # Create update time string
            update_time = f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Only create visualizations if a specific metric type is selected
            if metric_type_id:
                # Get the most recent value
                df_sorted = df.sort_values('timestamp', ascending=False)
                latest_value = float(df_sorted.iloc[0]['value'])
                
                # Get historical min/max for gauge range
                min_val = float(df['value'].min())
                max_val = float(df['value'].max())
                
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
                    df.sort_values('timestamp'), 
                    x='timestamp', 
                    y='value',
                    title=f"Historical Values for {df['metric_type'].iloc[0]}"
                )
                history.update_layout(
                    xaxis_title="Timestamp",
                    yaxis_title="Value",
                    yaxis_range=[min_val, max_val]
                )
                
                # Show visualization controls
                vis_style = {'display': 'block'}
                
                return (
                    gauge,
                    history,
                    {'display': 'block' if show_gauge else 'none'},
                    {'display': 'none' if show_gauge else 'block'},
                    vis_style,
                    table,
                    update_time
                )
            else:
                # Return empty visualizations but show table
                return (
                    {},
                    {},
                    {'display': 'none'},
                    {'display': 'none'},
                    {'display': 'none'},
                    table,
                    update_time
                )
            
    except Exception as e:
        logger.error(f"Error updating visualizations: {e}")
        return {}, {}, {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, html.Div(
            'Unable to load data. Please try again later.',
            style={'color': '#721c24', 'background-color': '#f8d7da', 'padding': '15px', 'border-radius': '4px'}
        ), 'Error updating data'

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