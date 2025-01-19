import json
import os
from dataclasses import dataclass
from typing import Optional, Any
import logging
import logging.handlers
import colorlog

@dataclass
class DatabaseCredentials:
    username: str
    password: str

@dataclass
class DatabaseConfig:
    host: str
    port: int
    credentials: DatabaseCredentials

@dataclass
class ApiConfig:
    url: str
    timeout: int

@dataclass
class FlaskConfig:
    secret_key: str
    host: str
    port: int

@dataclass
class ConsoleLoggingConfig:
    enabled: bool
    level: str
    format: str
    date_format: str
    def get_level(self) -> int:
        return getattr(logging, self.level.upper())

@dataclass
class FileLoggingConfig(ConsoleLoggingConfig):
    log_dir: str
    filename: str
    max_bytes: int
    backup_count: int

@dataclass
class LoggingConfig:
    console_output: ConsoleLoggingConfig
    file_output: FileLoggingConfig


class FlaskFilter(logging.Filter):
    def filter(self, record):
        # Allow messages from our app, filter out Flask's internal messages
        return not record.name.startswith('werkzeug') and not record.name.startswith('flask')

	

class ColoredFlaskFilter(logging.Filter):
    def filter(self, record):
        # Only color messages from our app, let Flask messages through uncolored
        if record.name.startswith('werkzeug') or record.name.startswith('flask'):
            # For Flask messages, use a plain formatter
            record.plain_message = True
            return True
        record.plain_message = False
        return True


class CustomColoredFormatter(colorlog.ColoredFormatter):
    def format(self, record):
        # If it's a Flask message, use plain formatting
        if getattr(record, 'plain_message', False):
            return record.getMessage() #return plain message
        # Otherwise use colored formatting
        return super().format(record)


class Config:
    database: DatabaseConfig
    api: ApiConfig
    flask: FlaskConfig
    logging_config: LoggingConfig
    debug: bool
    max_retries: int

    @staticmethod
    def set_working_directory(script_path: str) -> str:
        script_dir = os.path.dirname(os.path.abspath(script_path))
        os.chdir(script_dir)
        return script_dir

    def __init__(self, script_path: str = None, config_path: str = "config.json"):
        if script_path:
            self.set_working_directory(script_path)
        self._config = self._load_config(config_path)
        
        # Explicitly convert the nested dictionaries to Config objects
        self.database = DatabaseConfig(
            host=self._config['database']['host'],
            port=self._config['database']['port'],
            credentials=DatabaseCredentials(**self._config['database']['credentials'])
        )
        self.api = ApiConfig(**self._config['api'])
        self.flask = FlaskConfig(**self._config['flask'])
        self.debug = self._config['debug']
        self.max_retries = self._config['max_retries']
        
        raw_logging_config = self._config['logging_config']
        self.logging_config = LoggingConfig(
            console_output=ConsoleLoggingConfig(**raw_logging_config['console_output']),
            file_output=FileLoggingConfig(**raw_logging_config['file_output'])
        )

        self.setup_logging()

    def _load_config(self, config_path: str) -> dict:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def setup_logging(self) -> logging.Logger:
        # Create logs directory if needed and file output is enabled
        if self.logging_config.file_output.enabled:
            os.makedirs(self.logging_config.file_output.log_dir, exist_ok=True)
                
        # Get root logger
        logger = logging.getLogger()

        # Create filters
        flask_filter = FlaskFilter()
        colored_flask_filter = ColoredFlaskFilter()

        # Set base filtering to be the lowest of all enabled handlers
        root_level = logging.NOTSET
        enabled_levels = []
        if self.logging_config.console_output.enabled:
            enabled_levels.append(self.logging_config.console_output.get_level())
        if self.logging_config.file_output.enabled:
            enabled_levels.append(self.logging_config.file_output.get_level())
        if enabled_levels:
            root_level = min(enabled_levels)
        logger.setLevel(root_level)

        # Clear any existing handlers
        logger.handlers.clear()
        
        # Add console handler if enabled
        if self.logging_config.console_output.enabled:
            console_handler = logging.StreamHandler()
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
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(self.logging_config.console_output.get_level())
            console_handler.addFilter(colored_flask_filter)  # Add colored filter to console
            logger.addHandler(console_handler)
        
        # Add file handler if enabled
        if self.logging_config.file_output.enabled:
            file_path = os.path.join(
                self.logging_config.file_output.log_dir,
                self.logging_config.file_output.filename
            )
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=self.logging_config.file_output.max_bytes,
                backupCount=self.logging_config.file_output.backup_count
            )
            file_formatter = logging.Formatter(
                fmt=self.logging_config.file_output.format,
                datefmt=self.logging_config.file_output.date_format
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(self.logging_config.file_output.get_level())
            file_handler.addFilter(flask_filter)  # Add filter to file handler
            logger.addHandler(file_handler)
        
        return logger