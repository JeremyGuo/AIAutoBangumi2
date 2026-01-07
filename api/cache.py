from fastapi import APIRouter, Depends, HTTPException, status

from models.models import User
from core.user import get_current_admin_user
from utils.magnet import get_cache_info, clear_torrent_cache

router = APIRouter()

@router.get("/cache/info")
async def get_torrent_cache_info(
    user: User = Depends(get_current_admin_user)
):
    """获取种子缓存信息（仅管理员）"""
    try:
        cache_info = get_cache_info()
        return {
            "status": "success",
            "data": cache_info
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取缓存信息失败: {str(e)}"
        )

@router.delete("/cache/clear")
async def clear_cache(
    user: User = Depends(get_current_admin_user)
):
    """清空种子缓存（仅管理员）"""
    try:
        clear_torrent_cache()
        return {
            "status": "success",
            "message": "种子缓存已清空"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空缓存失败: {str(e)}"
        )
