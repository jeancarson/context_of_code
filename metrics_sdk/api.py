import aiohttp
import asyncio
from typing import List, Optional
import logging
from datetime import datetime

from .dto import MetricSnapshotDTO, MetricValueDTO

logger = logging.getLogger(__name__)

class MetricsAPI:
    """Main class for interacting with the metrics collection server"""
    
    def __init__(self, base_url: str):
        """
        Initialize the MetricsAPI
        
        Args:
            base_url: The base URL of the metrics server
        """
        self.base_url = base_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Support async context manager pattern"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when used as context manager"""
        await self.close()
    
    async def connect(self):
        """Create the HTTP session"""
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _ensure_session(self):
        """Ensure we have an active session"""
        if not self._session:
            raise RuntimeError("No active session. Use 'async with MetricsAPI(base_url)' or await connect()")
    
    async def send_metrics(self, snapshot: MetricSnapshotDTO) -> bool:
        """
        Send metrics to the server
        
        Args:
            snapshot: MetricSnapshotDTO containing the metrics to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        self._ensure_session()
        
        try:
            async with self._session.post(
                f"{self.base_url}/metrics",
                json=snapshot.dict()
            ) as response:
                if response.status == 200:
                    logger.info(f"Successfully sent {len(snapshot.metrics)} metrics")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send metrics. Status: {response.status}, Error: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending metrics: {str(e)}")
            return False
