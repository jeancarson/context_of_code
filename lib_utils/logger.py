import os
import logging
import logging.handlers
import colorlog
from typing import Dict, Optional, Any

class CustomColoredFormatter(colorlog.ColoredFormatter):
    """Custom formatter that adds color to log messages."""
    pass

class Logger:
    """
    Shared logging utility for both web and client applications.
    Provides consistent logging format and file handling.
    """
    
    @staticmethod
    def setup(
        app_name: str,
        console_level: str = "INFO",
        file_level: str = "DEBUG",
        log_dir: str = "logs",
        log_filename: Optional[str] = None,
        console_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        file_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S",
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5,
        additional_loggers: Dict[str, str] = None
    ) -> logging.Logger:
        """
        Set up logging with console and file handlers.
        
        Args:
            app_name: Name of the application (used for logger name and default filename)
            console_level: Logging level for console output
            file_level: Logging level for file output
            log_dir: Directory to store log files
            log_filename: Name of the log file (defaults to app_name.log)
            console_format: Format string for console logs
            file_format: Format string for file logs
            date_format: Date format for log timestamps
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup log files to keep
            additional_loggers: Dict of logger names and their levels to configure
            
        Returns:
            The configured root logger
        """
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Set up console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, console_level.upper()))
        console_formatter = CustomColoredFormatter(
            fmt='%(log_color)s' + console_format,
            datefmt=date_format,
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
        
        # Set up file handler
        if log_filename is None:
            log_filename = f"{app_name.lower().replace(' ', '_')}.log"
            
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, log_filename)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, file_level.upper()))
        file_formatter = logging.Formatter(
            fmt=file_format,
            datefmt=date_format
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Set root logger level to the minimum of console and file levels
        min_level = min(
            getattr(logging, console_level.upper()),
            getattr(logging, file_level.upper())
        )
        root_logger.setLevel(min_level)
        
        # Configure additional loggers if specified
        if additional_loggers:
            for logger_name, level in additional_loggers.items():
                logging.getLogger(logger_name).setLevel(getattr(logging, level.upper()))
        
        # Create a logger for the application
        logger = logging.getLogger(app_name)
        logger.info(f"Logging initialized for {app_name}")
        logger.info(f"Log file: {log_path}")
        
        return logger
    
    @staticmethod
    def setup_from_config(app_name: str, config: Any) -> logging.Logger:
        """
        Set up logging using configuration from a Config object.
        
        Args:
            app_name: Name of the application
            config: Configuration object with logging settings
            
        Returns:
            The configured logger
        """
        console_config = config.logging.console
        file_config = config.logging.file
        
        return Logger.setup(
            app_name=app_name,
            console_level=console_config.level,
            file_level=file_config.level,
            log_dir=file_config.log_dir,
            log_filename=file_config.filename,
            console_format=console_config.format,
            file_format=file_config.format,
            date_format=console_config.date_format,
            max_bytes=file_config.max_bytes,
            backup_count=file_config.backup_count
        ) 