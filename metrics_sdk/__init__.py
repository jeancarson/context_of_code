"""
Metrics SDK for interacting with the metrics collection server.
This package provides a clean interface for sending metrics data
and handling state changes from the server.
"""

from .api import MetricsAPI
from .dto import MetricSnapshotDTO, MetricValueDTO
from .state_api import StateAPI

__all__ = ['MetricsAPI', 'MetricSnapshotDTO', 'MetricValueDTO', 'StateAPI']
