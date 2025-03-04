import aiohttp
import asyncio
from typing import List, Optional, Deque
import logging
from datetime import datetime
from collections import deque
import json
import os
import aiofiles
from pathlib import Path

from .dto import MetricSnapshotDTO, MetricValueDTO

logger = logging.getLogger(__name__)

class MetricsAPI:
    """Main class for interacting with the metrics collection server"""
    
    def __init__(self, base_url: str, storage_dir: Optional[str] = None):
        """
        Initialize the MetricsAPI
        
        Args:
            base_url: The base URL of the metrics server
            storage_dir: Directory to store offline metrics queue (defaults to ./metrics_queue)
        """
        self.base_url = base_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
        self._queue: Deque[MetricSnapshotDTO] = deque()
        self._storage_dir = storage_dir or os.path.join(os.getcwd(), 'metrics_queue')
        self._queue_file = os.path.join(self._storage_dir, 'metrics_queue.json')
        self._ensure_storage_dir()
        self._cleanup_old_files()  # Clean up any old metric files

    def _ensure_storage_dir(self):
        """Ensure the storage directory exists"""
        os.makedirs(self._storage_dir, exist_ok=True)

    def _cleanup_old_files(self):
        """Clean up old individual metric JSON files from previous versions"""
        try:
            for file in Path(self._storage_dir).glob('*.json'):
                if file.name != 'metrics_queue.json':  # Don't delete our queue file
                    try:
                        os.remove(file)
                        logger.info(f"Cleaned up old metric file: {file.name}")
                    except Exception as e:
                        logger.error(f"Error deleting old metric file {file.name}: {e}")
        except Exception as e:
            logger.error(f"Error during cleanup of old metric files: {e}")

    async def _save_queue_to_disk(self):
        """Save entire queue to a single JSON file"""
        try:
            # Convert queue to list of dictionaries
            queue_data = [snapshot.dict() for snapshot in self._queue]
            
            async with aiofiles.open(self._queue_file, 'w') as f:
                await f.write(json.dumps(queue_data, indent=2))
                
            logger.info(f"Successfully saved {len(self._queue)} snapshots to queue file")
        except Exception as e:
            logger.error(f"Failed to save queue to disk: {e}")

    async def _load_persisted_queue(self):
        """Load persisted queue from single JSON file"""
        try:
            if not os.path.exists(self._queue_file):
                return

            async with aiofiles.open(self._queue_file, 'r') as f:
                content = await f.read()
                if not content:
                    return
                    
                queue_data = json.loads(content)
                for snapshot_dict in queue_data:
                    try:
                        snapshot = MetricSnapshotDTO(**snapshot_dict)
                        self._queue.append(snapshot)
                    except Exception as e:
                        logger.error(f"Error parsing persisted snapshot: {e}")

            logger.info(f"Loaded {len(self._queue)} snapshots from persisted queue")

        except Exception as e:
            logger.error(f"Error loading persisted queue: {e}")

    async def _clear_queue_file(self):
        """Clear the queue file after successful send"""
        try:
            if os.path.exists(self._queue_file):
                os.remove(self._queue_file)
        except Exception as e:
            logger.error(f"Error clearing queue file: {e}")

    async def __aenter__(self):
        """Support async context manager pattern"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when used as context manager"""
        await self.close()
    
    async def connect(self):
        """Create the HTTP session and load persisted queue"""
        if not self._session:
            self._session = aiohttp.ClientSession()
            await self._load_persisted_queue()  # Load queue when connecting
    
    async def close(self):
        """Close the HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _ensure_session(self):
        """Ensure we have an active session"""
        if not self._session:
            raise RuntimeError("No active session. Use 'async with MetricsAPI(base_url)' or await connect()")

    async def send_metrics_batch(self, snapshots: List[MetricSnapshotDTO]) -> bool:
        """
        Send multiple metric snapshots in a single batch. If server is unreachable, store metrics for later retry.
        
        Args:
            snapshots: List of MetricSnapshotDTO containing the metrics to send
            
        Returns:
            bool: True if successful or queued for later, False if unrecoverable error
        """
        if not snapshots:
            return True

        self._ensure_session()
        
        try:
            # First try to send any queued metrics
            await self.flush_queue()
            
            # Then try to send the new batch
            total_metrics = sum(len(snapshot.metrics) for snapshot in snapshots)
            logger.info(f"Attempting to send batch of {len(snapshots)} snapshots ({total_metrics} metrics)")
            
            success = True
            for snapshot in snapshots:
                try:
                    async with self._session.post(
                        f"{self.base_url}/metrics",
                        json=snapshot.dict()
                    ) as response:
                        if response.status == 200:
                            continue
                        elif response.status >= 500:
                            await self._queue_metric(snapshot)
                        else:
                            error_text = await response.text()
                            logger.error(f"Failed to send snapshot. Status: {response.status}, Error: {error_text}")
                            success = False
                            
                except aiohttp.ClientError as e:
                    # Connection error - queue for retry
                    logger.warning("Cannot connect to web app. Caching metrics for later retry.")
                    logger.debug(f"Connection error details: {str(e)}")
                    await self._queue_metric(snapshot)
                    
                except Exception as e:
                    # Unrecoverable error
                    logger.error(f"Unrecoverable error sending metrics: {str(e)}")
                    success = False

            if success:
                logger.info(f"Successfully sent batch of {len(snapshots)} snapshots ({total_metrics} metrics)")
            return success
                    
        except Exception as e:
            # Unrecoverable error
            logger.error(f"Unrecoverable error sending metrics batch: {str(e)}")
            return False

    async def send_metrics(self, snapshot: MetricSnapshotDTO) -> bool:
        """
        Send metrics to the server. If server is unreachable, store metrics for later retry.
        
        Args:
            snapshot: MetricSnapshotDTO containing the metrics to send
            
        Returns:
            bool: True if successful or queued for later, False if unrecoverable error
        """
        self._ensure_session()
        
        try:
            # First try to send any queued metrics
            await self.flush_queue()
            
            # Then try to send the new metrics
            async with self._session.post(
                f"{self.base_url}/metrics",
                json=snapshot.dict()
            ) as response:
                if response.status == 200:
                    logger.info(f"Successfully sent {len(snapshot.metrics)} metrics to web app")
                    return True
                else:
                    error_text = await response.text()
                    if response.status >= 500:
                        logger.warning(f"Web app server error (HTTP {response.status}). Caching metrics for later retry.")
                        await self._queue_metric(snapshot)
                        return True
                    logger.error(f"Failed to send metrics. Status: {response.status}, Error: {error_text}")
                    return False
                    
        except aiohttp.ClientError as e:
            # Connection error - queue for retry
            logger.warning("Cannot connect to web app. Caching metrics for later retry.")
            logger.debug(f"Connection error details: {str(e)}")
            await self._queue_metric(snapshot)
            return True
            
        except Exception as e:
            # Unrecoverable error
            logger.error(f"Unrecoverable error sending metrics: {str(e)}")
            return False

    async def _queue_metric(self, snapshot: MetricSnapshotDTO):
        """Add a metric to the retry queue and persist to disk"""
        self._queue.append(snapshot)
        await self._save_queue_to_disk()
        logger.info(f"Cached {len(snapshot.metrics)} metrics for later delivery (queue size: {len(self._queue)})")

    async def flush_queue(self) -> bool:
        """
        Attempt to send all queued metrics to the server
        
        Returns:
            bool: True if all metrics were sent successfully, False otherwise
        """
        if not self._queue:
            return True

        total_snapshots = len(self._queue)
        total_metrics = sum(len(snapshot.metrics) for snapshot in self._queue)
        logger.info(f"Attempting to send {total_snapshots} queued snapshots ({total_metrics} total metrics)")

        success = True
        metrics_sent = 0
        
        while self._queue:
            snapshot = self._queue[0]  # Peek at first item
            try:
                async with self._session.post(
                    f"{self.base_url}/metrics",
                    json=snapshot.dict()
                ) as response:
                    if response.status == 200:
                        self._queue.popleft()  # Remove on success
                        metrics_sent += len(snapshot.metrics)
                    else:
                        error_text = await response.text()
                        logger.warning(f"Web app not ready to receive metrics (HTTP {response.status}). Will retry later.")
                        logger.debug(f"Server response: {error_text}")
                        success = False
                        break
            except aiohttp.ClientError as e:
                logger.warning("Web app still not reachable. Keeping metrics in cache.")
                logger.debug(f"Connection error details: {str(e)}")
                success = False
                break
            except Exception as e:
                logger.error(f"Error processing queued metrics: {str(e)}")
                self._queue.popleft()  # Remove on unrecoverable error
                success = False

        if success and metrics_sent > 0:
            logger.info(f"Successfully delivered {metrics_sent} metrics from queue")
            await self._clear_queue_file()
        elif self._queue:
            # Only save if there are remaining items
            await self._save_queue_to_disk()

        return success

    @property
    def queue_size(self) -> int:
        """Get the number of metric snapshots in the queue"""
        return len(self._queue)
