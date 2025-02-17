import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime
from lib.models.generated_models import Base

class CapitalTemperature(Base):
    __tablename__ = 'capital_temperatures'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    country_code = Column(String, nullable=False)
    temperature = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'country_code': self.country_code,
            'temperature': self.temperature,
            'timestamp': self.timestamp.isoformat()
        }

    def __repr__(self):
        return f"<CapitalTemperature(country_code='{self.country_code}', temperature={self.temperature}, timestamp='{self.timestamp}')>"
