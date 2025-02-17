from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CountryCommits(Base):
    __tablename__ = 'country_commits'
    
    id = Column(Integer, primary_key=True)
    country_code = Column(String(2), nullable=False)  # ISO 2-letter code
    country_name = Column(String(100), nullable=False)
    population = Column(Integer, nullable=False)
    commit_count = Column(Integer, nullable=False)
    commits_per_capita = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    def to_dict(self):
        return {
            'country_code': self.country_code,
            'country_name': self.country_name,
            'population': self.population,
            'commit_count': self.commit_count,
            'commits_per_capita': self.commits_per_capita,
            'timestamp': self.timestamp.isoformat()
        }
