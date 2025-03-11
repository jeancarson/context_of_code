import time
import threading
import logging
import hashlib
import json
from typing import Dict, Any, Tuple, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MetricsCache:
    """
    Cache for metrics data to reduce database load.
    Uses time-based expiration and filter-based cache keys.
    """
    
    def __init__(self, cache_duration_seconds: int = 30):
        """
        Initialize the metrics cache.
        
        Args:
            cache_duration_seconds: How long to keep cached results (default: 30 seconds)
        """
        self.cache_duration = cache_duration_seconds
        self.cache: Dict[str, Tuple[float, Any]] = {}  # {cache_key: (timestamp, data)}
        self.cache_lock = threading.Lock()
        # Track which thread has the lock and when it was acquired
        self.lock_owner = None
        self.lock_acquire_time = None
        # Maximum time a thread can hold the lock (in seconds)
        self.max_lock_time = 10 
    
    @contextmanager
    def safe_lock(self):
        """Context manager that handles lock timeouts and forced release"""
        try:
            # Check if lock is stuck
            if self.lock_owner is not None:
                current_time = time.time()
                if current_time - self.lock_acquire_time > self.max_lock_time:
                    logger.warning(f"Lock held by thread {self.lock_owner} for > {self.max_lock_time}s. Forcing release.")
                    # Force release the lock
                    self.cache_lock = threading.Lock()
                    self.lock_owner = None
                    self.lock_acquire_time = None
            
            # Try to acquire the lock
            self.cache_lock.acquire()
            # Track lock ownership
            self.lock_owner = threading.current_thread().ident
            self.lock_acquire_time = time.time()
            
            yield
            
        finally:
            # Only release if we're the owner
            if self.lock_owner == threading.current_thread().ident:
                self.lock_owner = None
                self.lock_acquire_time = None
                self.cache_lock.release()
    
    def _generate_cache_key(self, **filter_params) -> str:
        """
        Generate a unique cache key based on filter parameters.
        Excludes n_clicks from the key since it changes on every refresh.
        
        Args:
            **filter_params: Filter parameters to include in the cache key
        
        Returns:
            A string hash representing the unique combination of filters
        """
        # Remove n_clicks from parameters as it changes on every refresh
        if 'n_clicks' in filter_params:
            del filter_params['n_clicks']
            
        # Convert parameters to a sorted string representation
        param_str = json.dumps(filter_params, sort_keys=True)
        
        # Create a hash of the parameters
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def get_cached_data(self, **filter_params) -> Optional[Tuple[Any, float]]:
        """
        Get data from cache if it exists and is not expired.
        
        Args:
            **filter_params: Filter parameters to generate the cache key
            
        Returns:
            Tuple of (cached_data, age_in_seconds) if cache hit, None if cache miss
        """
        cache_key = self._generate_cache_key(**filter_params)
        
        with self.safe_lock():
            if cache_key in self.cache:
                timestamp, data = self.cache[cache_key]
                current_time = time.time()
                age = current_time - timestamp
                
                # Check if cache is still valid
                if age < self.cache_duration:
                    logger.info(f"Cache hit for key {cache_key[:8]}... (age: {age:.1f}s)")
                    return data, age
                else:
                    logger.info(f"Cache expired for key {cache_key[:8]}... (age: {age:.1f}s)")
            else:
                logger.info(f"Cache miss for key {cache_key[:8]}...")
                
        return None
    
    def set_cached_data(self, data: Any, **filter_params) -> None:
        """
        Store data in the cache.
        
        Args:
            data: The data to cache
            **filter_params: Filter parameters to generate the cache key
        """
        cache_key = self._generate_cache_key(**filter_params)
        
        with self.safe_lock():
            self.cache[cache_key] = (time.time(), data)
            logger.info(f"Updated cache for key {cache_key[:8]}...")
    
    def invalidate_cache(self, **filter_params) -> None:
        """
        Invalidate a specific cache entry.
        
        Args:
            **filter_params: Filter parameters to generate the cache key
        """
        cache_key = self._generate_cache_key(**filter_params)
        
        with self.safe_lock():
            if cache_key in self.cache:
                del self.cache[cache_key]
                logger.info(f"Invalidated cache for key {cache_key[:8]}...")
    
    def invalidate_all(self) -> None:
        """Invalidate all cached data."""
        with self.safe_lock():
            self.cache.clear()
            logger.info("Invalidated all cached data") 