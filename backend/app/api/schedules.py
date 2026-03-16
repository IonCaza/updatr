from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from app.services.scheduler_service import (
    create_schedule,
    get_schedule,
    list_schedules,
    update_schedule,
    delete_schedule,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/schedules", tags=["schedules"], dependencies=[Depends(get_current_user)])


def _to_response(s) -> ScheduleResponse:
    return ScheduleResponse(
        id=s.id,
        name=s.name,
        cron_expression=s.cron_expression,
        host_ids=s.host_ids,
        tags_filter=s.tags_filter,
        patch_categories=s.patch_categories or [],
        reboot_policy=s.reboot_policy,
        is_active=s.is_active,
        last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        next_run_at=None,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


@router.get("", response_model=list[ScheduleResponse])
async def list_all_schedules(db: AsyncSession = Depends(get_db)):
    items = await list_schedules(db)
    return [_to_response(s) for s in items]


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_new_schedule(body: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    sched = await create_schedule(
        db,
        name=body.name,
        cron_expression=body.cron_expression,
        host_ids=body.host_ids,
        tags_filter=body.tags_filter,
        patch_categories=body.patch_categories,
        reboot_policy=body.reboot_policy,
    )
    return _to_response(sched)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_single_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    sched = await get_schedule(db, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _to_response(sched)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_existing_schedule(
    schedule_id: str, body: ScheduleUpdate, db: AsyncSession = Depends(get_db)
):
    updates = body.model_dump(exclude_unset=True)
    sched = await update_schedule(db, schedule_id, **updates)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _to_response(sched)


@router.delete("/{schedule_id}", status_code=204)
async def delete_existing_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_schedule(db, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
