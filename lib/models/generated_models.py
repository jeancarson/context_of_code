from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
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


class Currencies(Base):
    __tablename__ = 'currencies'

    currency_code: Mapped[str] = mapped_column(Text, unique=True)
    currency_name: Mapped[str] = mapped_column(Text)
    id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)

    countries: Mapped[List['Countries']] = relationship('Countries', back_populates='currency')
    exchange_rates: Mapped[List['ExchangeRates']] = relationship('ExchangeRates', foreign_keys='[ExchangeRates.from_currency]', back_populates='currencies')
    exchange_rates_: Mapped[List['ExchangeRates']] = relationship('ExchangeRates', foreign_keys='[ExchangeRates.to_currency]', back_populates='currencies_')


class Visits(Base):
    __tablename__ = 'visits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True)
    count: Mapped[int] = mapped_column(Integer)
    last_visit: Mapped[datetime.datetime] = mapped_column(DateTime)


class Countries(Base):
    __tablename__ = 'countries'

    country_name: Mapped[str] = mapped_column(Text)
    capital_city: Mapped[str] = mapped_column(Text)
    currency_id: Mapped[int] = mapped_column(ForeignKey('currencies.id'))
    id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)

    currency: Mapped['Currencies'] = relationship('Currencies', back_populates='countries')
    capital_temperatures: Mapped[List['CapitalTemperatures']] = relationship('CapitalTemperatures', back_populates='country')


class ExchangeRates(Base):
    __tablename__ = 'exchange_rates'
    __table_args__ = (
        Index('idx_currency_timestamp', 'from_currency', 'to_currency', 'timestamp'),
        Index('idx_from_currency', 'from_currency'),
        Index('idx_to_currency', 'to_currency')
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    from_currency: Mapped[int] = mapped_column(ForeignKey('currencies.id'))
    to_currency: Mapped[int] = mapped_column(ForeignKey('currencies.id'))
    rate: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)

    currencies: Mapped['Currencies'] = relationship('Currencies', foreign_keys=[from_currency], back_populates='exchange_rates')
    currencies_: Mapped['Currencies'] = relationship('Currencies', foreign_keys=[to_currency], back_populates='exchange_rates_')


class CapitalTemperatures(Base):
    __tablename__ = 'capital_temperatures'
    __table_args__ = (
        Index('idx_country_id', 'country_id'),
        Index('idx_country_timestamp', 'country_id', 'timestamp')
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey('countries.id'))
    temperature: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)

    country: Mapped['Countries'] = relationship('Countries', back_populates='capital_temperatures')
