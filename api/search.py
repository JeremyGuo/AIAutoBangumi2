"""Enhanced search and filter API."""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func

from models.session import get_db
from models.models import User, Source, Torrent, File
from core.user import get_current_user

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/sources")
async def search_sources(
    q: Optional[str] = Query(None, description="搜索关键词"),
    type: Optional[str] = Query(None, description="源类型：rss或magnet"),
    media_type: Optional[str] = Query(None, description="媒体类型：tv或movie"),
    outdated: Optional[bool] = Query(None, description="是否过期"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    搜索和过滤源
    
    支持按关键词、类型、媒体类型等条件搜索
    """
    try:
        # 构建查询条件
        conditions = []
        
        # 关键词搜索（标题或URL）
        if q:
            conditions.append(
                or_(
                    Source.title.ilike(f"%{q}%"),
                    Source.url.ilike(f"%{q}%")
                )
            )
        
        # 源类型过滤
        if type:
            conditions.append(Source.type == type)
        
        # 媒体类型过滤
        if media_type:
            conditions.append(Source.media_type == media_type)
        
        # 过期状态过滤
        if outdated is not None:
            conditions.append(Source.outdated == outdated)
        
        # 构建查询
        query = select(Source)
        if conditions:
            query = query.where(and_(*conditions))
        
        # 获取总数
        count_query = select(func.count(Source.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # 分页查询
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        sources = result.scalars().all()
        
        # 格式化结果
        sources_data = []
        for source in sources:
            sources_data.append({
                "id": source.id,
                "type": source.type,
                "url": source.url,
                "title": source.title,
                "media_type": source.media_type,
                "season": source.season,
                "tmdb_id": source.tmdb_id,
                "use_ai_episode": source.use_ai_episode,
                "episode_regex": source.episode_regex,
                "episode_offset": source.episode_offset,
                "outdated": source.outdated,
                "created_at": source.created_at.isoformat(),
                "last_check": source.last_check.isoformat() if source.last_check else None
            })
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "results": sources_data
        }
    
    except Exception as e:
        logger.error(f"Error searching sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索源失败: {str(e)}"
        )


@router.get("/torrents")
async def search_torrents(
    q: Optional[str] = Query(None, description="搜索关键词"),
    status: Optional[str] = Query(None, description="种子状态"),
    source_id: Optional[int] = Query(None, description="源ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    搜索和过滤种子
    
    支持按关键词、状态、源等条件搜索
    """
    try:
        # 构建查询条件
        conditions = []
        
        # 关键词搜索（标题或hash）
        if q:
            conditions.append(
                or_(
                    Torrent.title.ilike(f"%{q}%"),
                    Torrent.hash.ilike(f"%{q}%")
                )
            )
        
        # 状态过滤
        if status:
            conditions.append(Torrent.status == status)
        
        # 源过滤
        if source_id:
            conditions.append(Torrent.source_id == source_id)
        
        # 构建查询
        query = select(Torrent)
        if conditions:
            query = query.where(and_(*conditions))
        
        # 获取总数
        count_query = select(func.count(Torrent.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # 按创建时间降序排序
        query = query.order_by(Torrent.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        torrents = result.scalars().all()
        
        # 格式化结果
        torrents_data = []
        for torrent in torrents:
            torrents_data.append({
                "id": torrent.id,
                "hash": torrent.hash,
                "title": torrent.title,
                "status": torrent.status,
                "download_progress": torrent.download_progress,
                "source_id": torrent.source_id,
                "created_at": torrent.created_at.isoformat(),
                "started_at": torrent.started_at.isoformat() if torrent.started_at else None,
                "completed_at": torrent.completed_at.isoformat() if torrent.completed_at else None,
                "error_message": torrent.error_message
            })
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "results": torrents_data
        }
    
    except Exception as e:
        logger.error(f"Error searching torrents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索种子失败: {str(e)}"
        )


@router.get("/files")
async def search_files(
    q: Optional[str] = Query(None, description="搜索关键词"),
    file_type: Optional[str] = Query(None, description="文件类型"),
    hardlink_status: Optional[str] = Query(None, description="硬链接状态"),
    torrent_id: Optional[int] = Query(None, description="种子ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    搜索和过滤文件
    
    支持按关键词、文件类型、硬链接状态等条件搜索
    """
    try:
        # 构建查询条件
        conditions = []
        
        # 关键词搜索（文件名）
        if q:
            conditions.append(File.name.ilike(f"%{q}%"))
        
        # 文件类型过滤
        if file_type:
            conditions.append(File.file_type == file_type)
        
        # 硬链接状态过滤
        if hardlink_status:
            conditions.append(File.hardlink_status == hardlink_status)
        
        # 种子过滤
        if torrent_id:
            conditions.append(File.torrent_id == torrent_id)
        
        # 构建查询
        query = select(File)
        if conditions:
            query = query.where(and_(*conditions))
        
        # 获取总数
        count_query = select(func.count(File.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # 按创建时间降序排序
        query = query.order_by(File.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        files = result.scalars().all()
        
        # 格式化结果
        files_data = []
        for file in files:
            files_data.append({
                "id": file.id,
                "name": file.name,
                "path": file.path,
                "size": file.size,
                "file_type": file.file_type,
                "torrent_id": file.torrent_id,
                "extracted_episode": file.extracted_episode,
                "final_episode": file.final_episode,
                "hardlink_path": file.hardlink_path,
                "hardlink_status": file.hardlink_status,
                "hardlink_error": file.hardlink_error,
                "created_at": file.created_at.isoformat()
            })
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "results": files_data
        }
    
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索文件失败: {str(e)}"
        )


@router.get("/global")
async def global_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    全局搜索
    
    同时搜索源、种子和文件
    """
    try:
        # 搜索源
        sources_result = await db.execute(
            select(Source).where(
                or_(
                    Source.title.ilike(f"%{q}%"),
                    Source.url.ilike(f"%{q}%")
                )
            ).limit(5)
        )
        sources = sources_result.scalars().all()
        
        # 搜索种子
        torrents_result = await db.execute(
            select(Torrent).where(
                or_(
                    Torrent.title.ilike(f"%{q}%"),
                    Torrent.hash.ilike(f"%{q}%")
                )
            ).limit(5)
        )
        torrents = torrents_result.scalars().all()
        
        # 搜索文件
        files_result = await db.execute(
            select(File).where(
                File.name.ilike(f"%{q}%")
            ).limit(5)
        )
        files = files_result.scalars().all()
        
        return {
            "query": q,
            "sources": [
                {
                    "id": s.id,
                    "title": s.title,
                    "type": s.type,
                    "media_type": s.media_type
                }
                for s in sources
            ],
            "torrents": [
                {
                    "id": t.id,
                    "title": t.title,
                    "hash": t.hash,
                    "status": t.status
                }
                for t in torrents
            ],
            "files": [
                {
                    "id": f.id,
                    "name": f.name,
                    "file_type": f.file_type,
                    "hardlink_status": f.hardlink_status
                }
                for f in files
            ]
        }
    
    except Exception as e:
        logger.error(f"Error in global search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"全局搜索失败: {str(e)}"
        )
