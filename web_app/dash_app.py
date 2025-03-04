import os
import datetime
from decimal import Decimal
from dash import Dash, html, dcc, Input, Output, State, ctx
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from web_app.lib.config import Config
import logging
from web_app.lib.database import init_db, get_db
from web_app.lib.models.generated_models import Aggregators, Devices, MetricTypes, MetricSnapshots, MetricValues
from web_app.lib.constants import StatusCode, HTTPStatusCode
from sqlalchemy import select, func, and_, desc, asc
from web_app.lib.services.orm_service import (
    get_all_devices,
    get_all_metric_types,
    get_recent_metrics,
    get_latest_metrics_by_type
)

# Initialize logging and config
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)
config = Config(os.path.join(ROOT_DIR, 'config.json'))
config.setup_logging()

# Initialize Dash app
app = Dash(__name__, suppress_callback_exceptions=True)

# Define the layout
app.layout = html.Div([
    html.H1('Metrics Dashboard', className='header'),
    
    # Hidden div for storing initialization state
    html.Div(id='initialization-div', style={'display': 'none'}),
    
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

# Callbacks
@app.callback(
    [Output('metric-type-dropdown', 'options'),
     Output('aggregator-dropdown', 'options'),
     Output('device-dropdown', 'options')],
    [Input('initialization-div', 'children')],
    prevent_initial_call=False
)
def populate_dropdowns(_):
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

@app.callback(
    [Output('metric-gauge', 'figure'),
     Output('metric-history', 'figure'),
     Output('metric-gauge', 'style'),
     Output('metric-history', 'style'),
     Output('toggle-view-button', 'style'),
     Output('metrics-table', 'children')],
    [Input('metric-type-dropdown', 'value'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('min-value-input', 'value'),
     Input('max-value-input', 'value'),
     Input('aggregator-dropdown', 'value'),
     Input('device-dropdown', 'value'),
     Input('sort-order', 'value'),
     Input('toggle-view-button', 'n_clicks')]
)
def update_visualizations(metric_type_id, start_date, end_date, min_value, max_value,
                         aggregator_id, device_id, sort_order, n_clicks):
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
                    'timestamp': pd.to_datetime(r.client_timestamp_utc),  # Convert to pandas datetime immediately
                    'device': r.device_name,
                    'aggregator': r.aggregator_name,
                    'metric_type': r.metric_type_name,
                    'metric_type_id': r.metric_type_id
                }
                for r in results
            ])
            
            if df.empty:
                return {}, {}, {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, html.Div('No data available')
            
            # Create table with formatted timestamps
            df_display = df.copy()
            df_display['timestamp'] = df_display['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')  # Format for display
            df_display['value'] = df_display['value'].round(4)  # Round values for display
            # Remove metric_type_id from display
            df_display = df_display.drop('metric_type_id', axis=1)
            table = html.Table(
                [html.Tr([html.Th(col) for col in df_display.columns])] +
                [html.Tr([html.Td(df_display.iloc[i][col]) for col in df_display.columns])
                 for i in range(min(len(df_display), 10))]
            )
            
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
                    number={'valueformat': '.4g'},  # Format number with 4 significant digits
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
                    table
                )
            else:
                # Return empty visualizations but show table
                return (
                    {},
                    {},
                    {'display': 'none'},
                    {'display': 'none'},
                    {'display': 'none'},
                    table
                )
            
    except Exception as e:
        logger.error(f"Error updating visualizations: {e}")
        return {}, {}, {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, html.Div(
            'Unable to load data. Please try again later.',
            style={'color': '#721c24', 'background-color': '#f8d7da', 'padding': '15px', 'border-radius': '4px'}
        )

if __name__ == '__main__':
    try:
        # Initialize database
        init_db()
        logger.info("Database initialized")
        
        # Start the Dash app
        app.run_server(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1) 