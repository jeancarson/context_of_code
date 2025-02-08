import psutil
import logging
from pydantic import BaseModel
from typing import Optional
import platform

logger = logging.getLogger(__name__)

class SystemMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    cpu_temp: Optional[float]
    memory_available_gb: float
    memory_total_gb: float

class SystemMonitor:
    def __init__(self):
        self.temp_monitoring_available = False
        self.is_windows = platform.system() == "Windows"
        
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
                logger.warning(f"Failed to initialize temperature monitoring: {e}")
        else:
            logger.info("Skipping WMI initialization for non-Windows platforms")
        
        logger.info("System monitor initialized")

    def get_cpu_temperature(self) -> Optional[float]:
        if not self.is_windows:
            logger.warning("CPU temperature monitoring is not supported on this platform")
            return None
        
        try:
            # First attempt: MSAcpi_ThermalZoneTemperature
            temperatures = self.wmi_client.MSAcpi_ThermalZoneTemperature()
            if temperatures:
                temp_kelvin = float(temperatures[0].CurrentTemperature) / 10
                return temp_kelvin - 273.15

            # Second attempt: Win32_TemperatureProbe
            temperature_probes = self.wmi_client.Win32_TemperatureProbe()
            if temperature_probes:
                for probe in temperature_probes:
                    if probe.CurrentReading:
                        return float(probe.CurrentReading)

            logger.warning("No temperature data available through WMI")
            return None

        except Exception as e:
            logger.warning(f"Could not read CPU temperature: {e}")
            return None

    def get_metrics(self) -> SystemMetrics:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Get memory information
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024 ** 3)  # Convert to GB
        memory_available_gb = memory.available / (1024 ** 3)  # Convert to GB
        
        # Get CPU temperature
        cpu_temp = self.get_cpu_temperature() if self.is_windows else None

        metrics = SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            cpu_temp=cpu_temp,
            memory_available_gb=round(memory_available_gb, 2),
            memory_total_gb=round(memory_total_gb, 2)
        )

        logger.debug(f"Collected metrics: {metrics}")
        return metrics
