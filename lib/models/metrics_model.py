from datetime import datetime
from typing import Optional
from sqlalchemy import Float, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .generated_models import Base

class Metrics(Base):
    __tablename__ = 'Metrics'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_available_gb: Mapped[float] = mapped_column(Float, nullable=False)
    memory_total_gb: Mapped[float] = mapped_column(Float, nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
