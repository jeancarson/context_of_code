import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from ..models.metric_dto import MetricDTO

logger = logging.getLogger(__name__)

class BaseDevice:
    def __init__(self, device_name: str, metric_type: str, base_url: str, poll_interval: int):
        self.device_name = device_name
        self.metric_type = metric_type
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.uuid: Optional[uuid.UUID] = None
        self._load_or_request_uuid()

    def _load_or_request_uuid(self):
        """Load UUID from guid file or request a new one"""
        guid_path = Path(os.path.dirname(__file__)) / self.device_name / "guid"
        
        if guid_path.exists():
            with open(guid_path, "r") as f:
                self.uuid = uuid.UUID(f.read().strip())
            logger.info(f"Loaded existing UUID for {self.device_name}: {self.uuid}")
        else:
            # TODO: Implement the getUUID request to server
            # For now, we'll just create a new one locally
            self.uuid = uuid.uuid4()
            guid_path.parent.mkdir(parents=True, exist_ok=True)
            with open(guid_path, "w") as f:
                f.write(str(self.uuid))
            logger.info(f"Created new UUID for {self.device_name}: {self.uuid}")

    def create_metric(self, value: float) -> MetricDTO:
        """Create a metric DTO with the current timestamp"""
        return MetricDTO(
            type=self.metric_type,
            value=value,
            uuid=self.uuid,
            timestamp=time.time()
        )
