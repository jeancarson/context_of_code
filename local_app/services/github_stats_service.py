import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GitHubStatsService:
    def __init__(self, github_token=None):
        self.github_token = github_token
        self.headers = {'Authorization': f'token {github_token}'} if github_token else {}
        
        # Map of country names to their ISO codes and population API names
        self.country_mapping = {
            'Ireland': {'code': 'IE', 'population_name': 'ireland'},
            'United Kingdom': {'code': 'GB', 'population_name': 'united kingdom'},
            'France': {'code': 'FR', 'population_name': 'france'}
        }
    
    def get_population(self, country_name: str) -> int:
        """Get country population from World Bank API"""
        try:
            country = self.country_mapping[country_name]['population_name']
            response = requests.get(f'https://restcountries.com/v3.1/name/{country}')
            response.raise_for_status()
            return response.json()[0]['population']
        except Exception as e:
            logger.error(f"Error fetching population for {country_name}: {e}")
            return 0
    
    def get_todays_commits(self, country_code: str) -> int:
        """Get today's commit count for a country using GitHub API"""
        try:
            # Calculate today's date in ISO format
            today = datetime.utcnow().date().isoformat()
            
            # GitHub search query for commits from today in the specified country
            query = f'committer-date:{today} location:{country_code}'
            
            response = requests.get(
                'https://api.github.com/search/commits',
                headers={
                    **self.headers,
                    'Accept': 'application/vnd.github.cloak-preview'
                },
                params={'q': query, 'per_page': 1}
            )
            response.raise_for_status()
            
            return response.json()['total_count']
            
        except Exception as e:
            logger.error(f"Error fetching commits for {country_code}: {e}")
            return 0
    
    def get_country_stats(self) -> list:
        """Get commit stats for all tracked countries"""
        stats = []
        current_time = datetime.utcnow()
        
        for country_name, info in self.country_mapping.items():
            population = self.get_population(country_name)
            commits = self.get_todays_commits(info['code'])
            
            # Calculate commits per capita (per million people to make it more readable)
            commits_per_capita = (commits / population) * 1_000_000 if population > 0 else 0
            
            stats.append({
                'country_code': info['code'],
                'country_name': country_name,
                'population': population,
                'commit_count': commits,
                'commits_per_capita': round(commits_per_capita, 2),
                'timestamp': current_time.isoformat()
            })
        
        return stats
