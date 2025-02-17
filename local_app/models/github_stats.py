from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class GitHubStats:
    """Simple data class for GitHub stats before sending to server"""
    country_code: str
    country_name: str
    population: int
    commit_count: int
    commits_per_capita: float
    timestamp: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'country_code': self.country_code,
            'country_name': self.country_name,
            'population': self.population,
            'commit_count': self.commit_count,
            'commits_per_capita': self.commits_per_capita,
            'timestamp': self.timestamp.isoformat()
        }
