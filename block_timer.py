import time
import logging
from typing import Optional

class BlockTimer:
    """Simple RAII timer that logs execution time of a code block at debug level."""
    
    def __init__(self, block_name: str, logger: Optional[logging.Logger] = None):
        """Initialize the timer with a name for the code block being timed.
        
        Args:
            block_name (str): Name to identify this timed block in logs
            logger (Optional[logging.Logger]): Logger instance to use for output. 
                                             If None, uses root logger.
        """
        self.block_name = block_name
        self.logger = logger or logging.getLogger()
        
    def __enter__(self):
        """Start timing when entering the context."""
        self.start_time = time.perf_counter_ns()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log the elapsed time when exiting the context."""
        end_time = time.perf_counter_ns()
        duration_ms = (end_time - self.start_time) / 1_000_000  # Convert ns to ms
        self.logger.debug("%s took %.2fms to execute", self.block_name, duration_ms)
