from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..models.generated_models import Base

class CapitalTemperature(Base):
    __tablename__ = 'capital_temperatures'
    
    id = Column(String(36), primary_key=True)
    country_code = Column(String(2), ForeignKey('countries.code'), nullable=False)
    temperature = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Use string reference to avoid circular imports
    country = relationship("Country", 
                         back_populates="temperatures",
                         primaryjoin="CapitalTemperature.country_code == Country.code")
    
    def __repr__(self):
        return f"<CapitalTemperature(country_code='{self.country_code}', temperature={self.temperature}, timestamp='{self.timestamp}')>"
