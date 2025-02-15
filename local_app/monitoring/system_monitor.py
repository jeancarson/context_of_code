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
        self.temp_monitoring_available = False
        self.is_windows = platform.system() == "Windows"
        self.device_id = self._get_or_create_device_id()
        
        # Initialize temperature monitoring if Windows
        if self.is_windows:
            try:
                import wmi
                self.wmi_client = wmi.WMI()
                temp = self.get_cpu_temperature()
                self.temp_monitoring_available = temp is not None
                if not self.temp_monitoring_available:
                    logger.warning("CPU temperature monitoring is not available on this system")
                else:
                    logger.info("CPU temperature monitoring initialized successfully")
            except Exception as e:
                logger.warning(f"Could not read CPU temperature: {e}")
                
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

    def get_cpu_temperature(self) -> float:
        """Get CPU temperature if available"""
        if not self.is_windows:
            return None
            
        try:
            temps = self.wmi_client.MSAcpi_ThermalZoneTemperature()
            if temps:
                # Convert tenths of Kelvin to Celsius
                return (float(temps[0].CurrentTemperature) / 10.0) - 273.15
        except Exception as e:
            logger.warning(f"Could not read CPU temperature: {e}")
        return None

    def get_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        return SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=psutil.cpu_percent(),
            memory_percent=psutil.virtual_memory().percent,
            cpu_temp=self.get_cpu_temperature(),
            memory_available_gb=psutil.virtual_memory().available / (1024**3),
            memory_total_gb=psutil.virtual_memory().total / (1024**3),
            device_id=self.device_id
        )
