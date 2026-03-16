from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule


async def create_schedule(db: AsyncSession, **kwargs) -> Schedule:
    schedule = Schedule(**kwargs)
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def get_schedule(db: AsyncSession, schedule_id: str) -> Schedule | None:
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    return result.scalar_one_or_none()


async def list_schedules(db: AsyncSession, active_only: bool = False) -> list[Schedule]:
    stmt = select(Schedule).order_by(Schedule.name)
    if active_only:
        stmt = stmt.where(Schedule.is_active == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_schedule(db: AsyncSession, schedule_id: str, **kwargs) -> Schedule | None:
    schedule = await get_schedule(db, schedule_id)
    if not schedule:
        return None
    for key, val in kwargs.items():
        if val is not None:
            setattr(schedule, key, val)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def delete_schedule(db: AsyncSession, schedule_id: str) -> bool:
    schedule = await get_schedule(db, schedule_id)
    if not schedule:
        return False
    await db.delete(schedule)
    await db.commit()
    return True
