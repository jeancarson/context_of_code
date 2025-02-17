from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from ..models.generated_models import Base

class Country(Base):
    __tablename__ = 'countries'
    
    code = Column(String(2), primary_key=True)
    name = Column(String(100), nullable=False)
    capital = Column(String(100), nullable=False)
    
    # Use string references to avoid circular imports
    commits = relationship("CountryCommits", 
                         back_populates="country",
                         primaryjoin="Country.code == CountryCommits.country_code")
    temperatures = relationship("CapitalTemperature",
                              back_populates="country",
                              primaryjoin="Country.code == CapitalTemperature.country_code")
    
    def __repr__(self):
        return f"<Country(code='{self.code}', name='{self.name}', capital='{self.capital}')>"
