from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional, List, Dict, Union
from datetime import datetime
from enum import Enum

class MetricType(Enum):
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    MEMORY_AVAILABLE = "memory_available"
    MEMORY_TOTAL = "memory_total"

    def __str__(self):
        return self.value

@dataclass_json
@dataclass
class Metric:
    name: MetricType
    value: float
    unit: str
    timestamp: str

    @property
    def formatted_value(self) -> str:
        """Format the value with its unit"""
        if self.value is None:
            return "N/A"
        
        if self.unit == "percent":
            return f"{self.value:.1f}%"
        elif self.unit == "GB":
            return f"{self.value:.1f} GB"
        elif self.unit == "celsius":
            return f"{self.value:.1f}°C"
        return str(self.value)

@dataclass_json
@dataclass
class DeviceInfo:
    device_id: str
    hostname: str
    os_type: str
    os_version: str

@dataclass_json
@dataclass
class DeviceMetrics:
    device_info: DeviceInfo
    metrics: List[Metric]

    @classmethod #TODO, not sure that this should be referencing localhost
    def create_from_metrics(cls, metrics, device_id="local", hostname="localhost"):
        """Create a DeviceMetrics instance from SystemMonitor metrics"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get OS information
        import platform
        os_type = platform.system()
        os_version = platform.version()

        device_info = DeviceInfo(
            device_id=device_id,
            hostname=hostname,
            os_type=os_type,
            os_version=os_version
        )

        metric_list = [
            Metric(
                name=MetricType.CPU_USAGE,
                value=metrics.cpu_percent,
                unit="percent",
                timestamp=current_time
            ),
            Metric(
                name=MetricType.MEMORY_USAGE,
                value=metrics.memory_percent,
                unit="percent",
                timestamp=current_time
            ),
            Metric(
                name=MetricType.MEMORY_AVAILABLE,
                value=metrics.memory_available_gb,
                unit="GB",
                timestamp=current_time
            ),
            Metric(
                name=MetricType.MEMORY_TOTAL,
                value=metrics.memory_total_gb,
                unit="GB",
                timestamp=current_time
            )
        ]


        return cls(
            device_info=device_info,
            metrics=metric_list
        )

    def get_metric_value(self, metric_type: Union[MetricType, str]) -> Optional[float]:
        """Helper method to get a specific metric value"""
        if isinstance(metric_type, str):
            metric_type = MetricType(metric_type)
            
        try:
            for metric in self.metrics:
                if metric.name == metric_type:
                    return metric.value
        except (ValueError, AttributeError):
            pass
        return None

    def get_metric(self, metric_type: Union[MetricType, str]) -> Optional[Metric]:
        """Helper method to get a specific metric"""
        if isinstance(metric_type, str):
            metric_type = MetricType(metric_type)
            
        try:
            for metric in self.metrics:
                if metric.name == metric_type:
                    return metric
        except (ValueError, AttributeError):
            pass
        return None

    def get_formatted_value(self, metric_type: Union[MetricType, str], default: str = "N/A") -> str:
        """Get formatted value with unit, or default if not found"""
        metric = self.get_metric(metric_type)
        if metric is None:
            return default
        return metric.formatted_value

    def get_metric_with_unit(self, metric_type: MetricType) -> Optional[Dict[str, str]]:
        """Helper method to get a specific metric value with its unit"""
        for metric in self.metrics:
            if metric.name == metric_type:
                return {"value": metric.value, "unit": metric.unit}
        return None 