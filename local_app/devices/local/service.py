import psutil
from typing import List
from ..base_device import BaseDevice, MetricDTO
import time
import logging

logger = logging.getLogger(__name__)

class LocalMetricsService(BaseDevice):
    def __init__(self, base_url: str, poll_interval: int):
        super().__init__(
            device_name="local",
            metric_type="local",  # Use consistent type for the device
            base_url=base_url,
            poll_interval=poll_interval
        )
        
    def get_current_metrics(self) -> List[MetricDTO]:
        """
        Get current system metrics
        
        Returns:
            List[MetricDTO]: List of system metrics, or an empty list if data collection fails
        """
        metrics = []
        
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(self.create_metric_with_type("CPUPercent", cpu_percent))
            
            # Memory Usage
            memory = psutil.virtual_memory()
            metrics.append(self.create_metric_with_type("RAMPercent", memory.percent))
            
            # Disk Usage
            disk = psutil.disk_usage('/')
            metrics.append(self.create_metric_with_type("DiskPercent", disk.percent))
            
        except Exception as e:
            logger.error(f"Error collecting local system metrics: {e}")
            # Return an empty list instead of partial or default data
            return []
        
        return metrics
        
    def create_metric_with_type(self, specific_type: str, value: float) -> MetricDTO:
        """Create a metric with a specific type"""
        return MetricDTO(
            type=specific_type,
            value=value,
            uuid=self.uuid,  # Always set the UUID from the device
            created_at=time.time()
        )
