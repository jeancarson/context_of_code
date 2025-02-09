from typing import Optional

from sqlalchemy import Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = 'Person'

    Name: Mapped[Optional[str]] = mapped_column(Text)
    DOB: Mapped[Optional[str]] = mapped_column(Text)
    ROWID: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)

