import json
import os
import logging
import logging.handlers
import colorlog
from pydantic import BaseModel, Field
from typing import Optional

class DatabaseCredentials(BaseModel):
    username: str
    password: str

class DatabaseConfig(BaseModel):
    host: str
    port: int
    credentials: DatabaseCredentials

class ConsoleLoggingConfig(BaseModel):
    enabled: bool
    level: str
    format: str
    date_format: str

    def get_level(self) -> int:
        return getattr(logging, self.level.upper())

class FileLoggingConfig(ConsoleLoggingConfig):
    log_dir: str
    filename: str
    max_bytes: int
    backup_count: int

class LoggingConfig(BaseModel):
    console_output: ConsoleLoggingConfig
    file_output: FileLoggingConfig

class FlaskConfig(BaseModel):
    secret_key: str
    host: str
    port: int

class ApiConfig(BaseModel):
    url: str
    timeout: int

class ConfigModel(BaseModel):
    database: DatabaseConfig
    api: ApiConfig
    logging_config: LoggingConfig
    flask: FlaskConfig
    debug: bool = Field(default=False)
    max_retries: int = Field(default=3)

class FlaskFilter(logging.Filter):
    def filter(self, record):
        return not record.name.startswith('werkzeug') and not record.name.startswith('flask')

class ColoredFlaskFilter(logging.Filter):
    def filter(self, record):
        if record.name.startswith('werkzeug') or record.name.startswith('flask'):
            record.plain_message = True
            return True
        record.plain_message = False
        return True

class CustomColoredFormatter(colorlog.ColoredFormatter):
    def format(self, record):
        if getattr(record, 'plain_message', False):
            return record.getMessage()
        return super().format(record)

class Config:
    def __init__(self, script_path: str = None, config_path: str = "config.json"):
        if script_path:
            self.set_working_directory(script_path)
            
        # Load and validate config using Pydantic
        config_data = self._load_config(config_path)
        
        # Detect if running on PythonAnywhere
        is_pythonanywhere = 'PYTHONANYWHERE_SITE' in os.environ
        
        # Modify host settings based on environment
        if is_pythonanywhere:
            config_data['flask']['host'] = '0.0.0.0'
            if 'database' in config_data:
                config_data['database']['host'] = '0.0.0.0'
        else:
            # Local environment
            config_data['flask']['host'] = 'localhost'
            if 'database' in config_data:
                config_data['database']['host'] = 'localhost'
        
        self._config = ConfigModel(**config_data)
        
        # Setup logging
        self.setup_logging()

    @staticmethod
    def set_working_directory(script_path: str) -> str:
        script_dir = os.path.dirname(os.path.abspath(script_path))
        os.chdir(script_dir)
        return script_dir

    def _load_config(self, config_path: str) -> dict:
        if not os.path.isabs(config_path):
            # Get absolute path based on the project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up one level from lib_config
            config_path = os.path.join(project_root, config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            return json.load(f)


    def __getattr__(self, name: str):
        # Delegate attribute access to the Pydantic model
        return getattr(self._config, name)

    def setup_logging(self):
        """Set up logging configuration."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create filters
        flask_filter = FlaskFilter()
        colored_flask_filter = ColoredFlaskFilter()

        # Create formatters
        file_formatter = logging.Formatter(
            fmt=self.logging_config.file_output.format,
            datefmt=self.logging_config.file_output.date_format
        )
        
        console_formatter = CustomColoredFormatter(
            fmt='%(log_color)s' + self.logging_config.console_output.format,
            datefmt=self.logging_config.console_output.date_format,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white'
            }
        )

        # Set up file logging
        if self.logging_config.file_output.enabled:
            # Ensure log directory exists
            os.makedirs(self.logging_config.file_output.log_dir, exist_ok=True)
            log_file = os.path.join(
                self.logging_config.file_output.log_dir,
                self.logging_config.file_output.filename
            )
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.logging_config.file_output.max_bytes,
                backupCount=self.logging_config.file_output.backup_count
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(self.logging_config.file_output.get_level())
            file_handler.addFilter(flask_filter)  # Add filter to file handler
            root_logger.addHandler(file_handler)

        # Set up console logging
        if self.logging_config.console_output.enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(self.logging_config.console_output.get_level())
            console_handler.addFilter(colored_flask_filter)  # Add colored filter to console
            root_logger.addHandler(console_handler)

        # Set the root logger level to the lowest level of any handler
        root_logger.setLevel(min(
            self.logging_config.file_output.get_level() if self.logging_config.file_output.enabled else logging.CRITICAL,
            self.logging_config.console_output.get_level() if self.logging_config.console_output.enabled else logging.CRITICAL
        ))