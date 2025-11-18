"""Backup and export API for configuration and data."""
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.session import get_db
from models.models import User, Source, Torrent
from core.user import get_current_admin_user
from core.config import CONFIG

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/export/sources")
async def export_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Response:
    """
    导出所有源配置为JSON文件
    """
    try:
        # 获取所有源
        result = await db.execute(select(Source))
        sources = result.scalars().all()
        
        # 转换为字典
        sources_data = []
        for source in sources:
            sources_data.append({
                "type": source.type,
                "url": source.url,
                "media_type": source.media_type,
                "title": source.title,
                "tmdb_id": source.tmdb_id,
                "season": source.season,
                "use_ai_episode": source.use_ai_episode,
                "episode_regex": source.episode_regex,
                "episode_offset": source.episode_offset,
                "check_interval": source.check_interval,
                "created_at": source.created_at.isoformat()
            })
        
        # 创建导出数据
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "total_sources": len(sources_data),
            "sources": sources_data
        }
        
        # 生成文件名
        filename = f"aiautobangumi_sources_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 返回JSON文件
        return Response(
            content=json.dumps(export_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"Error exporting sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出源配置失败: {str(e)}"
        )


@router.post("/import/sources")
async def import_sources(
    import_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    从JSON数据导入源配置
    """
    try:
        if "sources" not in import_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="导入数据格式错误：缺少sources字段"
            )
        
        sources_data = import_data["sources"]
        success_count = 0
        failed_count = 0
        errors = []
        
        for source_data in sources_data:
            try:
                # 检查是否已存在相同URL的源
                existing = await db.execute(
                    select(Source).where(Source.url == source_data["url"])
                )
                if existing.scalar_one_or_none():
                    errors.append(f"源 '{source_data['title']}' 已存在，跳过")
                    failed_count += 1
                    continue
                
                # 创建新源
                new_source = Source(
                    type=source_data["type"],
                    url=source_data["url"],
                    media_type=source_data["media_type"],
                    title=source_data["title"],
                    tmdb_id=source_data.get("tmdb_id"),
                    season=source_data.get("season"),
                    use_ai_episode=source_data.get("use_ai_episode", False),
                    episode_regex=source_data.get("episode_regex"),
                    episode_offset=source_data.get("episode_offset", 0),
                    check_interval=source_data.get("check_interval", 3600)
                )
                
                db.add(new_source)
                success_count += 1
            
            except Exception as e:
                errors.append(f"导入源 '{source_data.get('title', 'Unknown')}' 失败: {str(e)}")
                failed_count += 1
                logger.error(f"Error importing source: {e}")
        
        await db.commit()
        
        return {
            "status": "completed",
            "total": len(sources_data),
            "success": success_count,
            "failed": failed_count,
            "errors": errors[:10]  # 只返回前10个错误
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error importing sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入源配置失败: {str(e)}"
        )


@router.get("/export/statistics")
async def export_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Response:
    """
    导出系统统计数据
    """
    try:
        # 获取统计数据
        from api.statistics import get_statistics_overview
        stats = await get_statistics_overview(db=db, current_user=current_user)
        
        # 添加导出信息
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "statistics": stats
        }
        
        # 生成文件名
        filename = f"aiautobangumi_stats_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 返回JSON文件
        return Response(
            content=json.dumps(export_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"Error exporting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出统计数据失败: {str(e)}"
        )


@router.get("/config")
async def get_config_info(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    获取当前配置信息（敏感信息已脱敏）
    """
    try:
        config_info = {
            "general": {
                "address": CONFIG.general.address,
                "listen": CONFIG.general.listen,
                "system_lang": CONFIG.general.system_lang,
                "http_proxy": CONFIG.general.http_proxy or "未设置"
            },
            "download": {
                "qbittorrent_url": CONFIG.download.qbittorrent_url,
                "qbittorrent_port": CONFIG.download.qbittorrent_port,
                "qbittorrent_username": CONFIG.download.qbittorrent_username,
                "download_dir": CONFIG.download.download_dir
                # 密码已隐藏
            },
            "hardlink": {
                "enable": CONFIG.hardlink.enable,
                "output_base": CONFIG.hardlink.output_base
            },
            "llm": {
                "enable": CONFIG.llm.enable,
                "url": CONFIG.llm.url,
                "name": CONFIG.llm.name
                # token已隐藏
            },
            "tmdb_api": {
                "enabled": CONFIG.tmdb_api.enabled
                # api_key已隐藏
            }
        }
        
        return config_info
    
    except Exception as e:
        logger.error(f"Error getting config info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置信息失败: {str(e)}"
        )
