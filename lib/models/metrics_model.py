from datetime import datetime
from typing import Optional
from sqlalchemy import Float, String, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .generated_models import Base

class Metrics(Base):
    """Model for system metrics"""
    __tablename__ = 'metrics'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_available_gb: Mapped[float] = mapped_column(Float, nullable=False)
    memory_total_gb: Mapped[float] = mapped_column(Float, nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
