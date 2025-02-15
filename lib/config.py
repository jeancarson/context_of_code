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

class DatabaseConfig(BaseModel):
    db_name: str = 'db.db'  # Default value, can be overridden
    database_url: str

    #@property allows you to define a method as a property, so you can call it like a normal attribute
    @property
    def db_path(self) -> str:
        return os.path.join(ROOT_DIR, self.db_name)

    def __init__(self, **data):
        super().__init__(**data)
        if 'database_url' not in data:
            self.database_url = f'sqlite:///{self.db_path}'

class ConfigModel(BaseModel):
    server: ServerConfig
    cache: CacheConfig
    logging: LoggingConfig
    database: DatabaseConfig
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
        self._config = ConfigModel(**config_data)
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {config_path}: {e}")

    def __getattr__(self, name: str):
        """Delegate attribute access to the Pydantic model."""
        try:
            return getattr(self._config, name)
        except AttributeError:
            raise AttributeError(f"'Config' object has no attribute '{name}'")

    def setup_logging(self):
        """Set up logging configuration."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Set up console logging if enabled
        if self._config.logging.console.enabled:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self._config.logging.console.get_level())
            console_formatter = CustomColoredFormatter(
                fmt='%(log_color)s' + self._config.logging.console.format,
                datefmt=self._config.logging.console.date_format,
                reset=True,
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        # Set up file logging if enabled
        if self._config.logging.file.enabled:
            os.makedirs(self._config.logging.file.log_dir, exist_ok=True)
            log_path = os.path.join(
                self._config.logging.file.log_dir,
                self._config.logging.file.filename
            )
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=self._config.logging.file.max_bytes,
                backupCount=self._config.logging.file.backup_count
            )
            file_handler.setLevel(self._config.logging.file.get_level())
            file_formatter = logging.Formatter(
                fmt=self._config.logging.file.format,
                datefmt=self._config.logging.file.date_format
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

        # Set root logger level to the minimum of console and file levels
        min_level = min(
            self._config.logging.console.get_level() if self._config.logging.console.enabled else logging.CRITICAL,
            self._config.logging.file.get_level() if self._config.logging.file.enabled else logging.CRITICAL
        )
        root_logger.setLevel(min_level)

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load the configuration file
config_instance = Config(os.path.join(ROOT_DIR, 'config.json'))

# Get database configuration from the loaded config
database = config_instance.database
