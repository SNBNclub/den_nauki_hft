from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, ARRAY, BigInteger, ForeignKey, Numeric, JSON, Date, Text
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs

from instance import SQL_URL_RC

engine = create_async_engine(url=SQL_URL_RC, echo=True)
async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id = Column(BigInteger, primary_key=True, index=True, nullable=False)
    name = Column(String, default='')
    username = Column(String, nullable=True)
    is_superuser = Column(Boolean, default=False)


class Raffle(Base):
    __tablename__ = "raffle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(Date, default=datetime.now)
    finished_at = Column(Date, nullable=True)
    winner_id = Column(BigInteger, nullable=True)
    winner_number = Column(Integer, nullable=True)


class RaffleEntry(Base):
    __tablename__ = "raffle_entry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raffle_id = Column(Integer, ForeignKey("raffle.id"))
    user_id = Column(BigInteger, ForeignKey("user.id"))
    number = Column(Integer, nullable=False)
    entry_time = Column(Date, default=datetime.now)


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)