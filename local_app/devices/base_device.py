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
        self._load_or_request_uuid()

    def _load_or_request_uuid(self):
        """Load UUID from guid file or request a new one from server"""
        guid_path = Path(os.path.dirname(__file__)) / self.device_name / "guid"
        
        if guid_path.exists():
            with open(guid_path, "r") as f:
                self.uuid = uuid.UUID(f.read().strip())
            logger.info(f"Loaded existing UUID for {self.device_name}: {self.uuid}")
        else:
            try:
                # Request new UUID from server
                response = requests.post(f"{self.base_url}/api/device/register")
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK':
                        self.uuid = uuid.UUID(data['device_id'])
                        # Save the UUID
                        guid_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(guid_path, "w") as f:
                            f.write(str(self.uuid))
                        logger.info(f"Registered new UUID for {self.device_name}: {self.uuid}")
                    else:
                        raise Exception(f"Server returned error status: {data.get('error', data['status'])}")
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
            payload = {
                "metrics": [
                    {
                        "type": metric.type,
                        "value": metric.value,
                        "device_id": str(self.uuid),
                        "created_at": metric.created_at
                    }
                    for metric in metrics
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/api/metrics",
                json=payload
            )
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Error publishing metrics: {response.status_code} - {error_data.get('error', 'Unknown error')}")
                return
                
            data = response.json()
            if data['status'] != 'OK':
                logger.error(f"Error publishing metrics: {data.get('error', data['status'])}")
            
        except Exception as e:
            logger.error(f"Error publishing metrics: {e}")
