"""
Metrics SDK for interacting with the metrics collection server.
This package provides a clean interface for sending metrics data.
"""

from .api import MetricsAPI
from .dto import MetricSnapshotDTO, MetricValueDTO

__all__ = ['MetricsAPI', 'MetricSnapshotDTO', 'MetricValueDTO']
