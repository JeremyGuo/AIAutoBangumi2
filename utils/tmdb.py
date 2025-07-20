from schemas.source import AnalyzeSourceResponse
from utils.rss import get_rss_title, get_rss_data
from core.config import load_config
import logging
import aiohttp
import asyncio
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

async def search_tmdb(title: str) -> List[Dict]:
    """
    使用TMDB API搜索影视作品
    """
    try:
        config = load_config()
        
        if not config.tmdb_api.enabled or not config.tmdb_api.api_key:
            logger.warning("TMDB API未启用或API Key未配置")
            return []
        
        # TMDB API搜索端点
        search_url = "https://api.themoviedb.org/3/search/multi"
        
        # 请求头，包含认证信息
        headers = {
            'Authorization': f'Bearer {config.tmdb_api.api_key}',
            'accept': 'application/json'
        }
        
        # 查询参数
        params = {
            'query': title,
            'language': 'zh-CN',  # 中文结果
            'include_adult': 'true',  # 包含成人内容
        }
        
        # 设置代理
        proxy = None
        if config.general.http_proxy:
            proxy = config.general.http_proxy
        
        # 发起HTTP请求
        async with aiohttp.ClientSession() as session:
            async with session.get(
                search_url, 
                headers=headers, 
                params=params,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results', [])
                    
                    # 处理结果，转换为我们需要的格式
                    processed_results = []
                    for item in results:
                        processed_item = {
                            'id': str(item.get('id')),  # 确保ID为字符串
                            'title': item.get('title') or item.get('name'),
                            'original_title': item.get('original_title') or item.get('original_name'),
                            'type': 'movie' if item.get('media_type') == 'movie' else 'tv',
                            'overview': item.get('overview'),
                            'first_air_date': item.get('first_air_date'),
                            'release_date': item.get('release_date'),
                            'poster_path': item.get('poster_path'),
                            'vote_average': item.get('vote_average'),
                            'popularity': item.get('popularity')
                        }
                        processed_results.append(processed_item)
                    
                    logger.info(f"TMDB搜索 '{title}' 返回 {len(processed_results)} 个结果")
                    return processed_results
                else:
                    logger.error(f"TMDB API请求失败: {response.status}")
                    return []
                    
    except asyncio.TimeoutError:
        logger.error("TMDB API请求超时")
        return []
    except Exception as e:
        logger.error(f"TMDB API请求发生错误: {e}")
        return []

async def get_tmdb_tv_details(tv_id: int) -> Optional[Dict]:
    """
    获取TMDB TV剧的详细信息，包括季度和剧集信息
    """
    try:
        config = load_config()
        
        if not config.tmdb_api.enabled or not config.tmdb_api.api_key:
            logger.warning("TMDB API未启用或API Key未配置")
            return None
        
        # TMDB API TV详情端点
        tv_url = f"https://api.themoviedb.org/3/tv/{tv_id}"
        
        # 请求头，包含认证信息
        headers = {
            'Authorization': f'Bearer {config.tmdb_api.api_key}',
            'accept': 'application/json'
        }
        
        # 查询参数
        params = {
            'language': 'zh-CN',  # 中文结果
        }
        
        # 设置代理
        proxy = None
        if config.general.http_proxy:
            proxy = config.general.http_proxy
        
        # 发起HTTP请求
        async with aiohttp.ClientSession() as session:
            async with session.get(
                tv_url, 
                headers=headers, 
                params=params,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # 处理季度信息
                    seasons = []
                    for season in data.get('seasons', []):
                        if season.get('season_number', 0) > 0:  # 排除特别篇（season 0）
                            seasons.append({
                                'season_number': season.get('season_number'),
                                'name': season.get('name'),
                                'episode_count': season.get('episode_count'),
                                'air_date': season.get('air_date'),
                                'overview': season.get('overview')
                            })
                    
                    return {
                        'id': data.get('id'),
                        'name': data.get('name'),
                        'original_name': data.get('original_name'),
                        'overview': data.get('overview'),
                        'number_of_seasons': data.get('number_of_seasons'),
                        'number_of_episodes': data.get('number_of_episodes'),
                        'seasons': seasons,
                        'first_air_date': data.get('first_air_date'),
                        'last_air_date': data.get('last_air_date'),
                        'status': data.get('status')
                    }
                else:
                    logger.error(f"TMDB TV详情API请求失败: {response.status}")
                    return None
                    
    except asyncio.TimeoutError:
        logger.error("TMDB TV详情API请求超时")
        return None
    except Exception as e:
        logger.error(f"TMDB TV详情API请求发生错误: {e}")
        return None

async def analyze_source(url: str, source_type: str) -> AnalyzeSourceResponse:
    """
    分析来源URL，返回标题和TMDB匹配结果
    """
    # 验证输入参数
    if not url or not source_type:
        return AnalyzeSourceResponse(error="URL或类型不能为空")

    cleaned_title = None
    
    try:
        if source_type == "rss":
            # 获取RSS数据和标题
            rss_data = await get_rss_data(url)
            if rss_data is None:
                return AnalyzeSourceResponse(error="无法获取RSS数据，请检查URL是否正确")
            dirty_title = await get_rss_title(url, rss_data)
            if not dirty_title:
                return AnalyzeSourceResponse(error="无法从RSS源获取标题")
            from utils.ai import get_cleaned_title
            cleaned_title = await get_cleaned_title(dirty_title)
            if not cleaned_title:
                return AnalyzeSourceResponse(error=f"无法清理标题 {dirty_title}")
            logging.info(f"清理后的标题: {cleaned_title}")
        elif source_type == "magnet":
            # 对于磁力链接，可以尝试从链接中提取标题
            # 这里可以添加磁力链接标题提取逻辑
            from utils.magnet import extract_title_from_torrent
            dirty_title = await extract_title_from_torrent(url)
            if not dirty_title:
                return AnalyzeSourceResponse(error="无法从磁力链接提取标题")
            from utils.ai import get_cleaned_title
            cleaned_title = await get_cleaned_title(dirty_title)
            if not cleaned_title:
                return AnalyzeSourceResponse(error=f"无法清理标题 {dirty_title}")
        else:
            return AnalyzeSourceResponse(error=f"不支持的源类型: {source_type}")
        
        # 用Cleaned标题查询TMDB
        tmdb_results = []
        if cleaned_title:
            tmdb_results = await search_tmdb(cleaned_title)
        
        return AnalyzeSourceResponse(
            title=cleaned_title,
            tmdb_results=tmdb_results
        )
        
    except Exception as e:
        logger.error(f"分析源时发生错误: {e}")
        return AnalyzeSourceResponse(error=f"分析源时发生错误: {str(e)}")