from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class RemoteMetrics(BaseModel):
    """Model for metrics received from remote machines"""
    machine_id: str
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    memory_total_gb: float
    timestamp: datetime = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now()
        super().__init__(**data)

class RemoteMetricsStore:
    """Store for keeping track of metrics from multiple remote machines"""
    def __init__(self):
        self._metrics: Dict[str, RemoteMetrics] = {}

    def update_metrics(self, machine_id: str, metrics: Dict[str, Any]):
        """Update metrics for a specific machine"""
        self._metrics[machine_id] = RemoteMetrics(machine_id=machine_id, **metrics)

    def get_metrics(self, machine_id: str) -> Optional[RemoteMetrics]:
        """Get metrics for a specific machine"""
        return self._metrics.get(machine_id)

    def get_all_metrics(self) -> Dict[str, RemoteMetrics]:
        """Get metrics for all machines"""
        return self._metrics.copy()

    def remove_machine(self, machine_id: str):
        """Remove a machine's metrics"""
        self._metrics.pop(machine_id, None)
