from models.models import Source

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from typing import List, Optional

async def get_all_sources(db: AsyncSession, start: int, limit: int) -> List[Source]:
    """获取所有来源"""
    result = await db.execute(
        select(Source).offset(start).limit(limit)
    )
    sources = result.scalars().all()
    return list(sources)

async def get_source_by_id(db: AsyncSession, source_id: int) -> Optional[Source]:
    """根据ID获取来源"""
    source = await db.get(Source, source_id)
    return source if source else None
