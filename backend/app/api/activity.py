from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.activity_service import get_activity_feed
from app.api.deps import get_current_user

router = APIRouter(prefix="/activity", tags=["activity"], dependencies=[Depends(get_current_user)])


@router.get("")
async def activity_feed(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await get_activity_feed(db, limit=limit)
