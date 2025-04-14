from sqlalchemy import select, desc, distinct, and_, update, func
from datetime import datetime

from database.models import User, Raffle, RaffleEntry, async_session
from errors.errors import *
from handlers.errors import db_error_handler


@db_error_handler
async def get_user(tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        if user:
            return user
        else:
            return None


@db_error_handler
async def create_user(tg_id: int, name: str = '', username: str = None):
    async with async_session() as session:
        user = await get_user(tg_id)
        data = {}
        if not user:
            data['id'] = tg_id
            data['name'] = name
            data['username'] = username
            user_data = User(**data)
            session.add(user_data)
            await session.commit()
        else:
            raise Error409


@db_error_handler
async def update_user(tg_id: int, data: dict):
    async with async_session() as session:
        user = await get_user(tg_id)
        if not user:
            raise Error404
        else:
            for key, value in data.items():
                setattr(user, key, value)
            session.add(user)
            await session.commit()


@db_error_handler
async def get_all_users():
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()


@db_error_handler
async def get_admin_ids():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.is_superuser == True))
        admins = result.scalars().all()
        return [admin.id for admin in admins]


@db_error_handler
async def set_admin(tg_id: int):
    async with async_session() as session:
        user = await get_user(tg_id)
        if not user:
            raise Error404
        else:
            user.is_superuser = True
            session.add(user)
            await session.commit()


@db_error_handler
async def create_raffle():
    async with async_session() as session:
        active_raffle = await session.scalar(select(Raffle).where(Raffle.is_active == True))
        if active_raffle:
            raise Error409

        raffle = Raffle()
        session.add(raffle)
        await session.commit()
        await session.refresh(raffle)
        return raffle.id

@db_error_handler
async def get_active_raffle():
    async with async_session() as session:
        raffle = await session.scalar(select(Raffle).where(Raffle.is_active == True))
        return raffle


@db_error_handler
async def end_raffle(raffle_id: int):
    async with async_session() as session:
        raffle = await session.get(Raffle, raffle_id)
        if not raffle:
            raise Error404

        query = select(
            RaffleEntry.number,
            func.count(RaffleEntry.number).label('count')
        ).where(
            RaffleEntry.raffle_id == raffle_id
        ).group_by(
            RaffleEntry.number
        ).having(
            func.count(RaffleEntry.number) == 1
        ).order_by(
            RaffleEntry.number
        )

        result = await session.execute(query)
        unique_numbers = result.all()

        if not unique_numbers:
            raffle.is_active = False
            raffle.finished_at = datetime.now()
            session.add(raffle)
            await session.commit()
            return None, None

        min_unique_number = unique_numbers[0][0]

        winner_entry = await session.scalar(
            select(RaffleEntry).where(
                and_(
                    RaffleEntry.raffle_id == raffle_id,
                    RaffleEntry.number == min_unique_number
                )
            )
        )

        raffle.is_active = False
        raffle.finished_at = datetime.now()
        raffle.winner_id = winner_entry.user_id
        raffle.winner_number = min_unique_number

        session.add(raffle)
        await session.commit()
        await session.refresh(raffle)
        await session.refresh(winner_entry)

        return winner_entry.user_id, min_unique_number


@db_error_handler
async def add_raffle_entry(user_id: int, number: int):
    async with async_session() as session:
        raffle = await get_active_raffle()
        if not raffle:
            raise Error404

        existing_entry = await session.scalar(
            select(RaffleEntry).where(
                and_(
                    RaffleEntry.raffle_id == raffle.id,
                    RaffleEntry.user_id == user_id
                )
            )
        )

        if existing_entry:
            existing_entry.number = number
            existing_entry.entry_time = datetime.now()
            session.add(existing_entry)
        else:

            entry = RaffleEntry(
                raffle_id=raffle.id,
                user_id=user_id,
                number=number
            )
            session.add(entry)

        await session.commit()
        return raffle.id


@db_error_handler
async def get_raffle_participants(raffle_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(RaffleEntry.user_id).where(RaffleEntry.raffle_id == raffle_id).distinct()
        )
        return [row[0] for row in result.all()]


@db_error_handler
async def get_user_entries(raffle_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(RaffleEntry).where(RaffleEntry.raffle_id == raffle_id)
        )
        entries = result.scalars().all()
        return entries