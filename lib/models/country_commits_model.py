from sqlalchemy import Column, String, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from ..models.generated_models import Base
from sqlalchemy import func
from sqlalchemy import and_

class CountryCommits(Base):
    __tablename__ = 'country_commits'

    id = Column(String(36), primary_key=True)
    country_code = Column(String(2), ForeignKey('countries.code'), nullable=False)
    country_name = Column(String(100), nullable=False)
    population = Column(Integer, nullable=False)
    commit_count = Column(Integer, nullable=False)
    commits_per_capita = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)

    # Use string reference to avoid circular imports
    country = relationship("Country", 
                         back_populates="commits",
                         primaryjoin="CountryCommits.country_code == Country.code")

    def to_dict(self):
        return {
            'country_code': self.country_code,
            'country_name': self.country_name,
            'population': self.population,
            'commit_count': self.commit_count,
            'commits_per_capita': self.commits_per_capita,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def get_latest_stats_with_temperature(cls, db):
        """Get latest stats for each country with temperature data"""
        from ..models.temperature_model import CapitalTemperature  # Import here to avoid circular imports
        import logging
        logger = logging.getLogger(__name__)
        
        # Get latest commits for each country
        commits_subq = (
            db.query(cls.country_code, 
                    func.max(cls.timestamp).label('max_commit_time'))
            .group_by(cls.country_code)
            .subquery()
        )
        
        # Get latest temperatures for each country
        temp_subq = (
            db.query(CapitalTemperature.country_code,
                    func.max(CapitalTemperature.timestamp).label('max_temp_time'))
            .group_by(CapitalTemperature.country_code)
            .subquery()
        )
        
        # Join commits with latest temperatures
        results = (
            db.query(cls, CapitalTemperature)
            .join(
                commits_subq,
                and_(
                    cls.country_code == commits_subq.c.country_code,
                    cls.timestamp == commits_subq.c.max_commit_time
                )
            )
            .outerjoin(  # Use outer join in case some countries don't have temperature data
                temp_subq,
                cls.country_code == temp_subq.c.country_code
            )
            .outerjoin(
                CapitalTemperature,
                and_(
                    CapitalTemperature.country_code == temp_subq.c.country_code,
                    CapitalTemperature.timestamp == temp_subq.c.max_temp_time
                )
            )
            .all()
        )
        
        return results
