import time
import threading
from typing import TypeVar, Generic, Callable

T = TypeVar('T')

class MetricsCache(Generic[T]):
    def __init__(self, fetch_func: Callable[[], T], cache_duration_seconds=30):
        """Generic cache for any type of metrics.
        
        Args:
            fetch_func: Function that returns fresh metrics when called
            cache_duration_seconds: How long to cache the metrics for
        """
        self.fetch_func = fetch_func
        self.cache_duration = cache_duration_seconds
        self.cache_lock = threading.Lock()
        self.cached_metrics = None
        self.last_update = 0
        
    def get_metrics(self) -> T:
        """Get metrics, either from cache or by fetching fresh ones."""
        #lock means only one thread can update the cache at a time
        #nobody can see partially updated cache
        with self.cache_lock:
            current_time = time.time()
            
            # Check if cache is valid
            if (self.cached_metrics is None or 
                current_time - self.last_update > self.cache_duration):
                
                # Get fresh metrics using the provided function
                self.cached_metrics = self.fetch_func()
                self.last_update = current_time
            
            return self.cached_metrics
