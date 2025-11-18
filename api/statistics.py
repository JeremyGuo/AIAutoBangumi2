"""Statistics and monitoring API endpoints."""
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from models.session import get_db
from models.models import User, Source, Torrent, File
from core.user import get_current_user

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/overview")
async def get_statistics_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取系统统计概览
    
    Returns:
        包含各种统计数据的字典
    """
    try:
        # 统计源的数量
        sources_count = await db.execute(select(func.count(Source.id)))
        total_sources = sources_count.scalar_one()
        
        # 统计RSS和磁力链接源的数量
        rss_sources_count = await db.execute(
            select(func.count(Source.id)).where(Source.type == "rss")
        )
        total_rss_sources = rss_sources_count.scalar_one()
        
        magnet_sources_count = await db.execute(
            select(func.count(Source.id)).where(Source.type == "magnet")
        )
        total_magnet_sources = magnet_sources_count.scalar_one()
        
        # 统计种子数量
        torrents_count = await db.execute(select(func.count(Torrent.id)))
        total_torrents = torrents_count.scalar_one()
        
        # 统计各状态的种子数量
        downloading_count = await db.execute(
            select(func.count(Torrent.id)).where(Torrent.status == "downloading")
        )
        downloading_torrents = downloading_count.scalar_one()
        
        completed_count = await db.execute(
            select(func.count(Torrent.id)).where(Torrent.status == "completed")
        )
        completed_torrents = completed_count.scalar_one()
        
        failed_count = await db.execute(
            select(func.count(Torrent.id)).where(Torrent.status == "failed")
        )
        failed_torrents = failed_count.scalar_one()
        
        pending_count = await db.execute(
            select(func.count(Torrent.id)).where(Torrent.status == "pending")
        )
        pending_torrents = pending_count.scalar_one()
        
        # 统计文件数量
        files_count = await db.execute(select(func.count(File.id)))
        total_files = files_count.scalar_one()
        
        # 统计硬链接成功和失败的文件数量
        hardlink_success_count = await db.execute(
            select(func.count(File.id)).where(File.hardlink_status == "completed")
        )
        hardlink_success = hardlink_success_count.scalar_one()
        
        hardlink_failed_count = await db.execute(
            select(func.count(File.id)).where(File.hardlink_status == "failed")
        )
        hardlink_failed = hardlink_failed_count.scalar_one()
        
        # 统计总文件大小
        total_size_result = await db.execute(select(func.sum(File.size)))
        total_size = total_size_result.scalar_one() or 0
        
        # 最近24小时的下载统计
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_torrents_count = await db.execute(
            select(func.count(Torrent.id)).where(Torrent.created_at >= yesterday)
        )
        recent_torrents = recent_torrents_count.scalar_one()
        
        recent_completed_count = await db.execute(
            select(func.count(Torrent.id)).where(
                and_(
                    Torrent.status == "completed",
                    Torrent.completed_at >= yesterday
                )
            )
        )
        recent_completed = recent_completed_count.scalar_one()
        
        return {
            "sources": {
                "total": total_sources,
                "rss": total_rss_sources,
                "magnet": total_magnet_sources
            },
            "torrents": {
                "total": total_torrents,
                "downloading": downloading_torrents,
                "completed": completed_torrents,
                "failed": failed_torrents,
                "pending": pending_torrents
            },
            "files": {
                "total": total_files,
                "hardlink_success": hardlink_success,
                "hardlink_failed": hardlink_failed,
                "total_size": total_size,
                "total_size_gb": round(total_size / (1024**3), 2)
            },
            "recent_24h": {
                "new_torrents": recent_torrents,
                "completed_torrents": recent_completed
            }
        }
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计数据失败: {str(e)}"
        )


@router.get("/download-history")
async def get_download_history(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取下载历史统计（按天）
    
    Args:
        days: 统计最近几天的数据，默认7天
    """
    try:
        if days > 90:
            days = 90  # 限制最多90天
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 获取每天的种子创建数量
        result = await db.execute(
            select(
                func.date(Torrent.created_at).label('date'),
                func.count(Torrent.id).label('count')
            )
            .where(Torrent.created_at >= start_date)
            .group_by(func.date(Torrent.created_at))
            .order_by(func.date(Torrent.created_at))
        )
        
        daily_stats = []
        for row in result:
            daily_stats.append({
                "date": row.date.isoformat() if row.date else None,
                "count": row.count
            })
        
        return {
            "period_days": days,
            "daily_stats": daily_stats
        }
    except Exception as e:
        logger.error(f"Error getting download history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取下载历史失败: {str(e)}"
        )


@router.get("/top-sources")
async def get_top_sources(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取下载最多的源
    
    Args:
        limit: 返回前N个源，默认10
    """
    try:
        if limit > 50:
            limit = 50  # 限制最多50个
        
        # 获取每个源的种子数量
        result = await db.execute(
            select(
                Source.id,
                Source.title,
                Source.type,
                Source.media_type,
                func.count(Torrent.id).label('torrent_count')
            )
            .join(Torrent, Source.id == Torrent.source_id)
            .group_by(Source.id, Source.title, Source.type, Source.media_type)
            .order_by(func.count(Torrent.id).desc())
            .limit(limit)
        )
        
        top_sources = []
        for row in result:
            top_sources.append({
                "source_id": row.id,
                "title": row.title,
                "type": row.type,
                "media_type": row.media_type,
                "torrent_count": row.torrent_count
            })
        
        return {
            "top_sources": top_sources
        }
    except Exception as e:
        logger.error(f"Error getting top sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热门源失败: {str(e)}"
        )


@router.get("/storage")
async def get_storage_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取存储空间统计
    """
    try:
        # 按文件类型统计大小
        result = await db.execute(
            select(
                File.file_type,
                func.count(File.id).label('count'),
                func.sum(File.size).label('total_size')
            )
            .group_by(File.file_type)
        )
        
        storage_by_type = []
        total_size = 0
        
        for row in result:
            size = row.total_size or 0
            total_size += size
            storage_by_type.append({
                "file_type": row.file_type or "unknown",
                "count": row.count,
                "size": size,
                "size_gb": round(size / (1024**3), 2)
            })
        
        return {
            "total_size": total_size,
            "total_size_gb": round(total_size / (1024**3), 2),
            "by_type": storage_by_type
        }
    except Exception as e:
        logger.error(f"Error getting storage statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取存储统计失败: {str(e)}"
        )
