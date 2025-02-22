from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import decimal

class Base(DeclarativeBase):
    pass


class Devices(Base):
    __tablename__ = 'devices'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    uuid: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[str] = mapped_column(Text)

    metrics: Mapped[List['Metrics']] = relationship('Metrics', back_populates='devices')


class MetricTypes(Base):
    __tablename__ = 'metric_types'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    type: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[str] = mapped_column(Text)

    metrics: Mapped[List['Metrics']] = relationship('Metrics', back_populates='metric_types')


class Visits(Base):
    __tablename__ = 'visits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True)
    count: Mapped[int] = mapped_column(Integer)
    last_visit: Mapped[datetime.datetime] = mapped_column(DateTime)


class Metrics(Base):
    __tablename__ = 'metrics'

    device: Mapped[int] = mapped_column(ForeignKey('devices.id'))
    type: Mapped[int] = mapped_column(ForeignKey('metric_types.id'))
    value: Mapped[decimal.Decimal] = mapped_column(Numeric)
    created_at: Mapped[str] = mapped_column(Text)
    id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)

    devices: Mapped['Devices'] = relationship('Devices', back_populates='metrics')
    metric_types: Mapped['MetricTypes'] = relationship('MetricTypes', back_populates='metrics')
