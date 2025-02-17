from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import datetime

class Base(DeclarativeBase):
    pass


class Metrics(Base):
    __tablename__ = 'Metrics'

    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)
    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    memory_available_gb: Mapped[float] = mapped_column(Float)
    memory_total_gb: Mapped[float] = mapped_column(Float)
    device_id: Mapped[str] = mapped_column(String(100))
    id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
    cpu_temp: Mapped[Optional[float]] = mapped_column(Float)


class Person(Base):
    __tablename__ = 'Person'

    Name: Mapped[Optional[str]] = mapped_column(Text)
    DOB: Mapped[Optional[str]] = mapped_column(Text)
    ROWID: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
