import psutil
import logging
import platform
from datetime import datetime
from local_app.models.system_metrics import SystemMetrics
import uuid
import os

logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        self.device_id = self._get_or_create_device_id()
        
        logger.info("System monitor initialized")

    def _get_or_create_device_id(self) -> str:
        """Get or create a unique device identifier"""
        id_file = os.path.join(os.path.dirname(__file__), ".device_id")
        if os.path.exists(id_file):
            with open(id_file, "r") as f:
                return f.read().strip()
        
        # Create new device ID
        device_id = f"{platform.node()}-{str(uuid.uuid4())[:8]}"
        with open(id_file, "w") as f:
            f.write(device_id)
        return device_id


    def get_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        return SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=psutil.cpu_percent(),
            memory_percent=psutil.virtual_memory().percent,
            memory_available_gb=psutil.virtual_memory().available / (1024**3),
            memory_total_gb=psutil.virtual_memory().total / (1024**3),
            device_id=self.device_id
        )
