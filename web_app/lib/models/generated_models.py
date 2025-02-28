from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import decimal

class Base(DeclarativeBase):
    pass


class Aggregators(Base):
    __tablename__ = 'aggregators'

    aggregator_id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    aggregator_uuid: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)

    devices: Mapped[List['Devices']] = relationship('Devices', back_populates='aggregator')


class Visits(Base):
    __tablename__ = 'visits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True)
    count: Mapped[int] = mapped_column(Integer)
    last_visit: Mapped[datetime.datetime] = mapped_column(DateTime)


class Devices(Base):
    __tablename__ = 'devices'

    device_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_uuid: Mapped[str] = mapped_column(Text, unique=True)
    device_name: Mapped[str] = mapped_column(Text)
    aggregator_id: Mapped[int] = mapped_column(ForeignKey('aggregators.aggregator_id'))
    created_at: Mapped[str] = mapped_column(Text)

    aggregator: Mapped['Aggregators'] = relationship('Aggregators', back_populates='devices')
    metric_snapshots: Mapped[List['MetricSnapshots']] = relationship('MetricSnapshots', back_populates='device')
    metric_types: Mapped[List['MetricTypes']] = relationship('MetricTypes', back_populates='device')


class MetricSnapshots(Base):
    __tablename__ = 'metric_snapshots'

    metric_snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    device_id: Mapped[int] = mapped_column(ForeignKey('devices.device_id'))
    client_timestamp_utc: Mapped[str] = mapped_column(Text)
    client_timezone_minutes: Mapped[int] = mapped_column(Integer)
    server_timestamp_utc: Mapped[str] = mapped_column(Text)
    server_timezone_minutes: Mapped[int] = mapped_column(Integer)

    device: Mapped['Devices'] = relationship('Devices', back_populates='metric_snapshots')
    metric_values: Mapped[List['MetricValues']] = relationship('MetricValues', back_populates='metric_snapshot')


class MetricTypes(Base):
    __tablename__ = 'metric_types'

    metric_type_id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    device_id: Mapped[int] = mapped_column(ForeignKey('devices.device_id'))
    metric_type_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)

    device: Mapped['Devices'] = relationship('Devices', back_populates='metric_types')
    metric_values: Mapped[List['MetricValues']] = relationship('MetricValues', back_populates='metric_type')


class MetricValues(Base):
    __tablename__ = 'metric_values'

    metric_snapshot_id: Mapped[int] = mapped_column(ForeignKey('metric_snapshots.metric_snapshot_id'), primary_key=True)
    metric_type_id: Mapped[int] = mapped_column(ForeignKey('metric_types.metric_type_id'), primary_key=True)
    value: Mapped[decimal.Decimal] = mapped_column(Numeric)

    metric_snapshot: Mapped['MetricSnapshots'] = relationship('MetricSnapshots', back_populates='metric_values')
    metric_type: Mapped['MetricTypes'] = relationship('MetricTypes', back_populates='metric_values')
