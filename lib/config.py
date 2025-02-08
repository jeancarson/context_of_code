import json
import os
import logging
import logging.handlers
import colorlog
from pydantic import BaseModel
from typing import Optional

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
    console: ConsoleLoggingConfig
    file: FileLoggingConfig

class ServerConfig(BaseModel):
    host: str
    port: int
    secret_key: str

class CacheConfig(BaseModel):
    enabled: bool
    duration_seconds: int

class ConfigModel(BaseModel):
    server: ServerConfig
    cache: CacheConfig
    logging: LoggingConfig
    debug: bool = False

class FlaskFilter(logging.Filter):
    def filter(self, record):
        return True

class ColoredFlaskFilter(logging.Filter):
    def filter(self, record):
        return True

class CustomColoredFormatter(colorlog.ColoredFormatter):
    def format(self, record):
        return super().format(record)

class Config:
    """Configuration manager that loads and validates config from JSON."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration JSON file
        """
        # Load and validate config using Pydantic
        config_data = self._load_config(config_path)
        
        # Detect if running on PythonAnywhere
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {config_path}: {e}")

    def __getattr__(self, name: str):
        """Delegate attribute access to the Pydantic model."""
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
            fmt=self.logging.file.format,
            datefmt=self.logging.file.date_format
        )
        
        console_formatter = CustomColoredFormatter(
            fmt='%(log_color)s' + self.logging.console.format,
            datefmt=self.logging.console.date_format,
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
        if self.logging.file.enabled:
            # Ensure log directory exists
            os.makedirs(self.logging.file.log_dir, exist_ok=True)
            log_file = os.path.join(
                self.logging.file.log_dir,
                self.logging.file.filename
            )
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.logging.file.max_bytes,
                backupCount=self.logging.file.backup_count
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(self.logging.file.get_level())
            file_handler.addFilter(flask_filter)
            root_logger.addHandler(file_handler)

        # Set up console logging
        if self.logging.console.enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(self.logging.console.get_level())
            console_handler.addFilter(colored_flask_filter)
            root_logger.addHandler(console_handler)

        # Set the root logger level to the lowest level of any handler
        root_logger.setLevel(min(
            self.logging.file.get_level() if self.logging.file.enabled else logging.CRITICAL,
            self.logging.console.get_level() if self.logging.console.enabled else logging.CRITICAL
        ))