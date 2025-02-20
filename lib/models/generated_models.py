from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Float, DateTime, Integer
import uuid
from datetime import datetime

Base = declarative_base()

class Base(DeclarativeBase):
    pass


class Metrics(Base):
    __tablename__ = 'Metrics'

    timestamp: Mapped[datetime] = mapped_column(DateTime)
    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    memory_available_gb: Mapped[float] = mapped_column(Float)
    memory_total_gb: Mapped[float] = mapped_column(Float)
    device_id: Mapped[str] = mapped_column(String(100))
    id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
    cpu_temp: Mapped[Optional[float]] = mapped_column(Float)



class ExchangeRates(Base):
    __tablename__ = 'exchange_rates'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rate = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
