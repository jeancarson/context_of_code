from datetime import datetime
import logging
from local_app.services.github_stats_service import GitHubStatsService

logger = logging.getLogger(__name__)

class GitHubCollector:
    def __init__(self, metrics_url: str, github_config: dict):
        self.metrics_url = metrics_url
        self.github_service = GitHubStatsService(
            github_token=github_config.get('github_token')
        )
    
    def collect_country_stats(self) -> list:
        """Collect GitHub stats for all tracked countries"""
        try:
            stats = self.github_service.get_country_stats()
            # Stats already have timestamp in ISO format string from the service
            return stats
        except Exception as e:
            logger.error(f"Error collecting GitHub stats: {e}")
            return []
