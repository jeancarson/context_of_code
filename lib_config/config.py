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

class ConfigModel(BaseModel):
    database: DatabaseConfig
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

    def setup_logging(self) -> logging.Logger:
        # Create logs directory if needed and file output is enabled
        if self._config.logging_config.file_output.enabled:
            os.makedirs(self._config.logging_config.file_output.log_dir, exist_ok=True)
                
        # Get root logger
        logger = logging.getLogger()

        # Create filters
        flask_filter = FlaskFilter()
        colored_flask_filter = ColoredFlaskFilter()

        # Set base filtering to be the lowest of all enabled handlers
        root_level = logging.NOTSET
        enabled_levels = []
        if self._config.logging_config.console_output.enabled:
            enabled_levels.append(self._config.logging_config.console_output.get_level())
        if self._config.logging_config.file_output.enabled:
            enabled_levels.append(self._config.logging_config.file_output.get_level())
        if enabled_levels:
            root_level = min(enabled_levels)
        logger.setLevel(root_level)

        # Clear any existing handlers
        logger.handlers.clear()
        
        # Add console handler if enabled
        if self._config.logging_config.console_output.enabled:
            console_handler = logging.StreamHandler()
            console_formatter = CustomColoredFormatter(
                fmt='%(log_color)s' + self._config.logging_config.console_output.format,
                datefmt=self._config.logging_config.console_output.date_format,
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
            console_handler.setLevel(self._config.logging_config.console_output.get_level())
            console_handler.addFilter(colored_flask_filter)  # Add colored filter to console
            logger.addHandler(console_handler)
        
        # Add file handler if enabled
        if self._config.logging_config.file_output.enabled:
            file_path = os.path.join(
                self._config.logging_config.file_output.log_dir,
                self._config.logging_config.file_output.filename
            )
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=self._config.logging_config.file_output.max_bytes,
                backupCount=self._config.logging_config.file_output.backup_count
            )
            file_formatter = logging.Formatter(
                fmt=self._config.logging_config.file_output.format,
                datefmt=self._config.logging_config.file_output.date_format
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(self._config.logging_config.file_output.get_level())
            file_handler.addFilter(flask_filter)  # Add filter to file handler
            logger.addHandler(file_handler)
        
        return logger