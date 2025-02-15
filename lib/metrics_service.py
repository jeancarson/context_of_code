from datetime import datetime
from typing import List, Dict, Any
from .database import get_db
from .models.metrics_model import Metrics
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    pass

class MetricsService:
    @staticmethod
    def validate_metrics_data(data: Dict[str, Any]) -> None:
        """Validate incoming metrics data"""
        required_fields = {
            'timestamp': str,
            'cpu_percent': (int, float),
            'memory_percent': (int, float),
            'memory_available_gb': (int, float),
            'memory_total_gb': (int, float)
        }
        
        # Check required fields and types
        for field, expected_type in required_fields.items():
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
            if not isinstance(data[field], expected_type):
                raise ValidationError(f"Invalid type for {field}: expected {expected_type}, got {type(data[field])}")
        
        # Validate numeric ranges
        if not 0 <= data['cpu_percent'] <= 100:
            raise ValidationError("cpu_percent must be between 0 and 100")
        if not 0 <= data['memory_percent'] <= 100:
            raise ValidationError("memory_percent must be between 0 and 100")
        if data['memory_available_gb'] < 0:
            raise ValidationError("memory_available_gb cannot be negative")
        if data['memory_total_gb'] < 0:
            raise ValidationError("memory_total_gb cannot be negative")
        if data['memory_available_gb'] > data['memory_total_gb']:
            raise ValidationError("memory_available_gb cannot be greater than memory_total_gb")
            
        # Validate timestamp format
        try:
            datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError("Invalid timestamp format. Expected ISO format.")

    def create_metrics(self, metrics_data: Dict[str, Any]) -> dict:
        """Create a new metrics entry"""
        # Validate data before processing
        try:
            logger.info(f"Validating metrics data: {metrics_data}")
            self.validate_metrics_data(metrics_data)
            
            with get_db() as db:
                # Convert timestamp string to datetime
                timestamp = datetime.fromisoformat(metrics_data['timestamp'].replace('Z', '+00:00'))
                
                # Create new metrics entry
                metrics = Metrics(
                    timestamp=timestamp,
                    cpu_percent=float(metrics_data['cpu_percent']),
                    memory_percent=float(metrics_data['memory_percent']),
                    memory_available_gb=float(metrics_data['memory_available_gb']),
                    memory_total_gb=float(metrics_data['memory_total_gb']),
                    device_id=metrics_data.get('device_id', 'unknown')
                )
                logger.info(f"Creating metrics entry: {metrics}")
                db.add(metrics)
                db.flush()  # Flush to get the ID
                logger.info(f"Created metrics entry with ID: {metrics.id}")
                
                return {
                    'id': metrics.id,
                    'timestamp': metrics.timestamp.isoformat(),
                    'cpu_percent': metrics.cpu_percent,
                    'memory_percent': metrics.memory_percent,
                    'memory_available_gb': metrics.memory_available_gb,
                    'memory_total_gb': metrics.memory_total_gb,
                    'device_id': metrics.device_id
                }
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating metrics: {e}")
            raise

    def get_metrics(self, device_id: str = None, start_time: datetime = None, 
                   end_time: datetime = None, limit: int = 1000) -> List[dict]:
        """Get metrics with optional filtering"""
        with get_db() as db:
            query = db.query(Metrics)
            
            if device_id:
                query = query.filter(Metrics.device_id == device_id)
            if start_time:
                query = query.filter(Metrics.timestamp >= start_time)
            if end_time:
                query = query.filter(Metrics.timestamp <= end_time)
                
            query = query.order_by(Metrics.timestamp.desc()).limit(limit)
            metrics_list = query.all()
            
            return [{
                'id': m.id,
                'timestamp': m.timestamp.isoformat(),
                'cpu_percent': m.cpu_percent,
                'memory_percent': m.memory_percent,
                'memory_available_gb': m.memory_available_gb,
                'memory_total_gb': m.memory_total_gb,
                'device_id': m.device_id
            } for m in metrics_list]
