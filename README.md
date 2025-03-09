# Context of Code - Metrics Collection System

A distributed system for collecting, processing, and visualizing metrics from various sources. This project consists of a local metrics collection application and a web application for data visualization and management.

## Project Structure

```
project/
├── local_app/                  # Local metrics collection application
│   ├── devices/                # Device-specific metric collectors
│   │   ├── base_device.py      # Base class for all device services
│   │   ├── exchange_rate/      # Exchange rate metrics collector
│   │   ├── local/              # System metrics collector
│   │   └── temperature/        # Temperature metrics collector
│   ├── services/               # General-purpose services
│   │   └── calculator.py       # Calculator service
│   ├── utils/                  # Utility functions
│   │   └── calculator.py       # Calculator utility functions
│   ├── config.json             # Configuration file
│   └── main.py                 # Main application entry point
│
├── web_app/                    # Web application for metrics visualization
│   ├── lib/                    # Library code
│   │   ├── database.py         # Database connection and initialization
│   │   ├── models/             # Database models
│   │   │   └── generated_models.py  # SQLAlchemy ORM models
│   │   └── services/           # Service layer
│   │       └── orm_service.py  # ORM service for database operations
│   ├── scripts/                # Utility scripts
│   │   └── insert_devices.py   # Script for inserting device records
│   ├── static/                 # Static assets
│   ├── templates/              # HTML templates
│   └── app.py                  # Flask web application
│
└── logs/                       # Application logs
    └── app.log                 # Main log file
```

## Features

- **Multi-source Metrics Collection**: Collects metrics from various sources including:
  - System resources (CPU, RAM, Disk)
  - Temperature data (via weather API)
  - Exchange rates (GBP to EUR)

- **Robust Error Handling**: Properly handles API failures and connectivity issues without reporting false data

- **Web Dashboard**: Visualizes collected metrics with filtering and sorting capabilities

- **RESTful API**: Provides endpoints for registering devices and submitting metrics

- **Database Storage**: Persists metrics and device information in a relational database using SQLAlchemy ORM

## Architecture

### Local Application

The local application follows a modular architecture:

- **BaseDevice**: Abstract base class that provides common functionality for all device services
  - UUID management
  - Metric creation
  - Publishing metrics to server

- **Device Services**: Inherit from BaseDevice and implement specific metric collection logic
  - `TemperatureService`: Collects temperature data from a weather API
  - `ExchangeRateService`: Collects GBP to EUR exchange rate data
  - `LocalMetricsService`: Collects system resource metrics (CPU, RAM, Disk)

- **Utility Services**: Standalone services that provide additional functionality
  - `CalculatorService`: Provides calculator-related functionality

### Web Application

The web application is built with Flask and follows a layered architecture:

- **Presentation Layer**: Flask routes and Dash components for visualization
- **Service Layer**: ORM services for database operations
- **Data Access Layer**: SQLAlchemy ORM models for database interaction

## Setup and Installation

### Prerequisites

- Python 3.8+
- SQLite or another database supported by SQLAlchemy

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/context_of_code.git
   cd context_of_code
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the application:
   - Edit `local_app/config.json` to set API endpoints and polling intervals
   - Configure database connection in `web_app/lib/database.py` if needed

## Usage

### Running the Web Application

```bash
cd web_app
python app.py
```

The web application will be available at http://localhost:5000/

### Running the Local Metrics Collector

```bash
cd local_app
python main.py
```

### Running the Metrics Server Locally

```bash
python local_metrics_server.py
```

## Development

### Adding a New Device Service

1. Create a new directory under `local_app/devices/`
2. Create a `service.py` file that implements a class inheriting from `BaseDevice`
3. Implement the required methods:
   - `__init__`: Initialize the service with configuration
   - `get_current_metrics`: Collect and return metrics

### Adding a New API Endpoint

1. Add a new route in `web_app/app.py`
2. Implement the endpoint logic
3. Update the ORM service if database operations are needed

## Error Handling

The application implements robust error handling:

- API failures are properly logged and do not result in default/fake values being reported
- Database errors are caught and logged
- Network connectivity issues are handled gracefully

## Contributors

- Jean Carson 
- John Savage - `lib_utils` including `blocktimer.py` and `logger.py`were taken from in class code demos/excerises
