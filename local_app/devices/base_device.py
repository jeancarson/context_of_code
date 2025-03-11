import json
import logging
import os
import time
import uuid
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MetricDTO:
    type: str  # e.g., "GPBtoEURexchangeRate", "RAMPercent", "Temperature"
    value: float
    uuid: Optional[UUID] = None  # Will be None if not yet assigned
    created_at: Optional[float] = None  # Will be set by the service before sending

class BaseDevice:
    def __init__(self, device_name: str, metric_type: str, base_url: str, poll_interval: int):
        self.device_name = device_name
        self.metric_type = metric_type
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.uuid: Optional[uuid.UUID] = None
        self.aggregator_uuid: Optional[uuid.UUID] = None
        # Create a logger with the device name for better log identification
        self.logger = logging.getLogger(f"{__name__}.{device_name}")
        self._load_or_request_uuid()

    def _load_or_request_uuid(self):
        """Load UUID from guid file or request a new one from server"""
        # Use a common location for the aggregator UUID
        base_dir = Path(os.path.dirname(os.path.dirname(__file__)))  # Go up one level to get the devices directory
        aggregator_path = base_dir / "aggregator_guid"
        device_dir = Path(os.path.dirname(__file__)) / self.device_name
        guid_path = device_dir / "guid"
        
        # First, get or create aggregator UUID
        if aggregator_path.exists():
            with open(aggregator_path, "r") as f:
                self.aggregator_uuid = uuid.UUID(f.read().strip())
            logger.info(f"Loaded existing aggregator UUID: {self.aggregator_uuid}")
        else:
            try:
                # Request new aggregator UUID from server
                response = requests.post(
                    f"{self.base_url}/register/aggregator",
                    json={"name": "LocalAggregator"}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK':
                        self.aggregator_uuid = uuid.UUID(data['uuid'])
                        # Save the UUID
                        aggregator_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(aggregator_path, "w") as f:
                            f.write(str(self.aggregator_uuid))
                        logger.info(f"Registered new aggregator UUID: {self.aggregator_uuid}")
                    else:
                        raise Exception(f"Server returned error status: {data.get('message', data['status'])}")
                else:
                    raise Exception(f"Server returned status code: {response.status_code}")
            except Exception as e:
                logger.error(f"Error registering aggregator: {e}")
                raise
        
        # Then, get or create device UUID
        if guid_path.exists():
            with open(guid_path, "r") as f:
                self.uuid = uuid.UUID(f.read().strip())
            logger.info(f"Loaded existing UUID for {self.device_name}: {self.uuid}")
        else:
            try:
                # Request new UUID from server
                response = requests.post(
                    f"{self.base_url}/register/device",
                    json={
                        "device_name": self.device_name,
                        "aggregator_uuid": str(self.aggregator_uuid)
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK':
                        self.uuid = uuid.UUID(data['uuid'])
                        # Save the UUID
                        device_dir.mkdir(parents=True, exist_ok=True)
                        with open(guid_path, "w") as f:
                            f.write(str(self.uuid))
                        logger.info(f"Registered new UUID for {self.device_name}: {self.uuid}")
                    else:
                        raise Exception(f"Server returned error status: {data.get('message', data['status'])}")
                else:
                    raise Exception(f"Server returned status code: {response.status_code}")
            except Exception as e:
                logger.error(f"Error registering device {self.device_name}: {e}")
                raise

    def create_metric(self, value: float) -> MetricDTO:
        """Create a metric DTO with the current timestamp"""
        return MetricDTO(
            type=self.metric_type,
            value=value,
            uuid=self.uuid,
            created_at=time.time()
        )

    def publish_metrics(self, metrics: list[MetricDTO]):
        """Publish metrics to the server"""
        if not self.uuid:
            raise Exception(f"No device ID for service {self.metric_type}")
            
        try:
            # Convert metrics to new snapshot format
            payload = {
                "device_uuid": str(self.uuid),
                "client_timestamp_utc": str(datetime.utcnow()),
                "client_timezone_minutes": -time.timezone // 60,  # Convert seconds to minutes
                "metric_values": [
                    {
                        "metric_type_name": metric.type,
                        "value": metric.value
                    }
                    for metric in metrics
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/metrics",
                json=payload
            )
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Error publishing metrics: {response.status_code} - {error_data.get('message', 'Unknown error')}")
                return
                
            data = response.json()
            if data['status'] != 'OK':
                logger.error(f"Error publishing metrics: {data.get('message', data['status'])}")
            
        except Exception as e:
            logger.error(f"Error publishing metrics: {e}")
