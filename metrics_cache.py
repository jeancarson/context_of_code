import time
import threading
from models.device_metrics import DeviceMetrics
from system_monitor import SystemMonitor

class MetricsCache:
    def __init__(self, cache_duration_seconds=30):
        self.cache_duration = cache_duration_seconds
        self.cache_lock = threading.Lock()
        self.cached_metrics = None
        self.last_update = 0
        self.system_monitor = SystemMonitor()
        
    def get_metrics(self):
        #lock means only one thread can update the cache at a time
        #nobody can se epartially updated cache
        with self.cache_lock:
            current_time = time.time()
            
            # Check if cache is valid
            if (self.cached_metrics is None or 
                current_time - self.last_update > self.cache_duration):
                
                # Get fresh metrics
                metrics = self.system_monitor.get_metrics()
                self.cached_metrics = DeviceMetrics.create_from_metrics(metrics)
                self.last_update = current_time
            
            return self.cached_metrics
