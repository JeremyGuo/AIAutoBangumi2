from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from core.user import get_current_user, get_user_count
from models.session import get_db
from models.models import User

router = APIRouter()

@router.get("/me")
async def get_current_user_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户的信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active
    }

@router.get("/count")
async def get_user_count_info(db: AsyncSession = Depends(get_db)):
    """获取用户数量信息，用于判断是否是第一个用户"""
    user_count = await get_user_count(db)
    return {
        "count": user_count,
        "is_first_user": user_count == 0
    }