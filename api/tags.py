"""Tags/Labels API for organizing sources."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from models.session import get_db
from models.models import User, Source
from core.user import get_current_user, get_current_admin_user

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class TagCreate(BaseModel):
    """创建标签的请求模型"""
    name: str
    color: str = "#3b82f6"  # 默认蓝色


class SourceTagUpdate(BaseModel):
    """更新源标签的请求模型"""
    tags: List[str]


@router.get("/")
async def list_all_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    列出所有使用过的标签
    
    从所有源的标签字段中提取唯一的标签列表
    """
    try:
        # 获取所有源（目前标签信息存储在title或可以添加新字段）
        # 这里我们假设在源模型中添加了tags字段
        # 由于当前模型没有tags字段，我们可以使用一个简单的实现
        
        # 返回预定义的标签列表（可以后续扩展为从数据库读取）
        predefined_tags = [
            {"name": "动画", "color": "#ef4444", "count": 0},
            {"name": "电影", "color": "#f59e0b", "count": 0},
            {"name": "连载中", "color": "#10b981", "count": 0},
            {"name": "已完结", "color": "#6366f1", "count": 0},
            {"name": "高优先级", "color": "#ec4899", "count": 0},
            {"name": "待补", "color": "#8b5cf6", "count": 0}
        ]
        
        # 统计每种媒体类型的数量
        tv_count = await db.execute(
            select(func.count(Source.id)).where(Source.media_type == "tv")
        )
        movie_count = await db.execute(
            select(func.count(Source.id)).where(Source.media_type == "movie")
        )
        
        # 更新预定义标签的计数（这是一个简化版本）
        for tag in predefined_tags:
            if tag["name"] == "动画":
                tag["count"] = tv_count.scalar_one()
            elif tag["name"] == "电影":
                tag["count"] = movie_count.scalar_one()
        
        return {
            "tags": predefined_tags
        }
    except Exception as e:
        logger.error(f"Error listing tags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标签列表失败: {str(e)}"
        )


@router.post("/create")
async def create_tag(
    tag_data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    创建新标签
    
    这是一个占位符实现，实际应该有专门的标签表
    """
    try:
        # TODO: 实现标签持久化存储
        # 目前返回成功消息
        return {
            "status": "success",
            "message": f"标签 '{tag_data.name}' 创建成功",
            "tag": {
                "name": tag_data.name,
                "color": tag_data.color
            }
        }
    except Exception as e:
        logger.error(f"Error creating tag: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建标签失败: {str(e)}"
        )


@router.post("/{source_id}/assign")
async def assign_tags_to_source(
    source_id: int,
    tag_update: SourceTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    为源分配标签
    
    这是一个占位符实现，需要在Source模型中添加tags字段
    """
    try:
        # 检查源是否存在
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="源不存在"
            )
        
        # TODO: 实际保存标签到数据库
        # source.tags = tag_update.tags
        # await db.commit()
        
        return {
            "status": "success",
            "message": f"已为源 '{source.title}' 分配标签",
            "tags": tag_update.tags
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning tags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分配标签失败: {str(e)}"
        )


@router.get("/sources/{tag_name}")
async def get_sources_by_tag(
    tag_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    根据标签获取源列表
    
    这是一个简化版本，基于媒体类型过滤
    """
    try:
        # 简化版本：根据标签名映射到媒体类型
        media_type_map = {
            "动画": "tv",
            "电影": "movie"
        }
        
        media_type = media_type_map.get(tag_name)
        
        if media_type:
            result = await db.execute(
                select(Source).where(Source.media_type == media_type)
            )
        else:
            # 如果不是预定义标签，返回所有源
            result = await db.execute(select(Source))
        
        sources = result.scalars().all()
        
        return {
            "tag": tag_name,
            "count": len(sources),
            "sources": [
                {
                    "id": source.id,
                    "title": source.title,
                    "type": source.type,
                    "media_type": source.media_type,
                    "created_at": source.created_at.isoformat()
                }
                for source in sources
            ]
        }
    except Exception as e:
        logger.error(f"Error getting sources by tag: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标签源列表失败: {str(e)}"
        )
