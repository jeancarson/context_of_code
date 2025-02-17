from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .generated_models import Base

class Visit(Base):
    """Model for tracking page visits by IP address"""
    __tablename__ = 'visits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=False)  # IPv6 addresses can be up to 45 chars
    count: Mapped[int] = mapped_column(Integer, default=1)
    last_visit: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Visit(ip={self.ip_address}, count={self.count})>"
