from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.session import get_db
from models.models import User, Torrent, Source

from core.user import get_current_user, get_current_admin_user
from core.sources import get_all_sources

from schemas.source import SourceBase, AnalyzeSourceResponse, AnalyzeSourceRequest

import logging

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger("api.source")

@router.get("/", response_class=JSONResponse)
async def list_sources(
    request: Request,
    start: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """源列表页面"""
    sources = await get_all_sources(db, start, limit)
    
    # 获取总数
    result = await db.execute(select(func.count(Source.id)))
    total = result.scalar_one()
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "total": total,
            "start": start,
            "limit": limit,
            "sources": [
                {
                    "id": source.id,
                    "url": source.url,
                    "type": source.type,
                    "title": source.title,
                    "media_type": source.media_type,
                    "season": source.season,
                    "episode_offset": source.episode_offset,
                    "episode_regex": source.episode_regex,
                    "use_ai_episode": source.use_ai_episode,
                    "check_interval": source.check_interval,
                    "created_at": source.created_at.isoformat(),
                    "last_check": source.last_check.isoformat() if source.last_check else None,
                    "outdated": source.outdated,
                    "tmdb_id": source.tmdb_id
                }
                for source in sources
            ]
        }
    )

@router.get("/{source_id}", response_class=JSONResponse)
async def get_source_detail(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取源的详细信息"""
    from core.sources import get_source_by_id
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="源不存在"
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "id": source.id,
            "url": source.url,
            "type": source.type,
            "title": source.title,
            "media_type": source.media_type,
            "season": source.season,
            "episode_offset": source.episode_offset,
            "episode_regex": source.episode_regex,
            "use_ai_episode": source.use_ai_episode,
            "check_interval": source.check_interval,
            "created_at": source.created_at.isoformat(),
            "last_check": source.last_check.isoformat() if source.last_check else None,
            "outdated": source.outdated,
            "tmdb_id": source.tmdb_id
        }
    )

@router.post("/create")
async def create_source(
    request: Request,
    source_in: SourceBase,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user)
):
    """创建新的来源"""
    logging.info(f"创建新的来源: {source_in}")
    new_source = Source(**source_in.model_dump())
    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)
    logger.info(f"已创建来源 ID:{new_source.id}")
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"status": "success"}
    )

@router.post("/analyze", response_model=AnalyzeSourceResponse)
async def analyze_source(
    request: AnalyzeSourceRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """分析来源URL，返回标题和TMDB匹配结果"""
    from utils.tmdb import analyze_source
    logging.info(f"分析来源: {request.url} 类型: {request.type}")
    result = await analyze_source(
        url=str(request.url),
        source_type=request.type
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法分析来源URL"
        )
    return result

@router.get("/tmdb/{tmdb_id}")
async def get_tmdb_tv_details(
    tmdb_id: int,
    current_user: User = Depends(get_current_user)
):
    """获取TMDB TV剧的详细信息，包括季度和剧集信息"""
    from utils.tmdb import get_tmdb_tv_details
    logging.info(f"获取TMDB TV详情: {tmdb_id}")
    result = await get_tmdb_tv_details(tmdb_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无法获取TMDB详情"
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result
    )

@router.delete("/{source_id}")
@router.post("/{source_id}/delete")  # Add POST method endpoint to match frontend
async def delete_source(
    source_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除来源"""
    from core.sources import get_source_by_id
    db_obj = await get_source_by_id(db, source_id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="来源不存在"
        )
    await db.delete(db_obj)
    await db.commit()
    logger.info(f"已删除来源 ID:{source_id}")
    return {"status": "success", "message": "来源已删除"}

@router.post("/{source_id}/reset-check", response_model=dict)
async def reset_source_check_time(
    source_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user)
):
    """重置来源的最后检查时间，强制下次检查RSS"""
    from core.sources import get_source_by_id
    db_obj = await get_source_by_id(db, source_id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="来源不存在"
        )
    
    # 更新为很早的时间，确保下次检查会处理所有内容
    from datetime import datetime, timezone
    past_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db_obj.last_check = past_time
    await db.commit()
    await db.refresh(db_obj)  # 刷新对象以获取最新数据
    
    logger.info(f"已重置来源 ID:{source_id} 的检查时间")
    return {"status": "success", "message": "已重置来源的检查时间"}

@router.post("/generate-regex", response_model=dict)
async def generate_episode_regex(
    request: Request,
    url: str = Form(...),
    source_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user)
):
    """从RSS源的第一个条目生成集数正则表达式 / 从种子文件列表中的文件名生成正则表达式"""
    try:
        # 获取RSS源的第一个条目标题
        if source_type == "rss":
            from utils.rss import get_first_item
            item = await get_first_item(url)
            if not item:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"status": "error", "message": "无法获取RSS源数据"}
                )
            first_item_title = item["title"]
            full_title_list = first_item_title
        else: # Get torrent file list and generate regex from file names
            from utils.magnet import get_file_list
            items = await get_file_list(url)
            titles = []
            for item in items:
                if "name" in item:
                    titles.append(item["name"])
            if not titles:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"status": "error", "message": "无法获取种子文件列表"}
                )
            first_item_title = titles[0]  # 使用第一个文件名作为示例
            full_title_list = '|'.join(titles)
        
        # 使用第一个条目的标题生成正则表达式
        from utils.ai import get_regex_from_titles
        import re
        
        logging.info(f"生成正则表达式，标题: {full_title_list}")
        regex_pattern = await get_regex_from_titles(full_title_list)
        logging.info(f"生成的正则表达式: {regex_pattern}")
        
        if not regex_pattern:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"status": "error", "message": "无法生成正则表达式"}
            )
        
        # 用正则表达式测试第一个标题，提取集数作为示例
        sample_result = None
        try:
            match = re.search(regex_pattern, first_item_title)
            if match:
                sample_result = match.group(1)  # 提取第一个捕获组
        except Exception as e:
            logging.warning(f"正则表达式测试失败: {e}")
        
        return {
            "status": "success", 
            "regex": regex_pattern, 
            "sample_title": first_item_title,
            "sample_result": sample_result
        }
        
    except Exception as e:
        logger.error(f"生成正则表达式失败: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"生成失败: {str(e)}"}
        )