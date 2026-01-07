from schemas.source import AnalyzeSourceResponse
from utils.rss import get_rss_title, get_rss_data
from core.config import load_config
import logging
import aiohttp
import asyncio
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def _language_from_system(system_lang: str) -> str:
    system_lang = system_lang.lower()
    if system_lang.startswith("cn") or system_lang.startswith("zh"):
        return "zh-CN"
    if system_lang.startswith("ja") or system_lang.startswith("jp"):
        return "ja-JP"
    if system_lang.startswith("en"):
        return "en-US"
    return "en-US"

def _extract_display_title(item: Dict) -> str:
    return item.get('title') or item.get('name') or ""

async def search_tmdb(title: str, raise_on_error: bool = False) -> List[Dict]:
    """
    使用TMDB API搜索影视作品
    """
    try:
        config = load_config()
        
        if not config.tmdb_api.enabled or not config.tmdb_api.api_key:
            message = "TMDB未启用或API Key未配置"
            logger.warning(message)
            if raise_on_error:
                raise RuntimeError(message)
            return []
        
        search_url = "https://api.themoviedb.org/3/search/multi"
        headers = {
            'Authorization': f'Bearer {config.tmdb_api.api_key}',
            'accept': 'application/json'
        }
        proxy = config.general.http_proxy if config.general.http_proxy else None

        async def fetch_results(language: str | None) -> List[Dict]:
            params = {
                'query': title,
                'include_adult': 'true',
            }
            if language:
                params['language'] = language
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
                        return data.get('results', [])
                    message = f"TMDB请求失败: HTTP {response.status}"
                    logger.error(message)
                    if raise_on_error:
                        raise RuntimeError(message)
                    return []

        system_lang = (getattr(config.general, "system_lang", "") or "")
        preferred_lang = _language_from_system(system_lang)
        languages = [preferred_lang, "en-US", None]
        by_lang: dict[str | None, dict[tuple[str, str], Dict]] = {}
        for lang in languages:
            results = await fetch_results(lang)
            if not results:
                continue
            lang_map: dict[tuple[str, str], Dict] = {}
            for item in results:
                media_type = item.get('media_type') or "tv"
                key = (str(item.get('id')), str(media_type))
                lang_map[key] = item
            by_lang[lang] = lang_map

        merged: dict[tuple[str, str], Dict] = {}
        for lang_map in by_lang.values():
            for key, item in lang_map.items():
                merged[key] = item

        processed_results = []
        for key, item in merged.items():
            display_title = ""
            for lang in languages:
                lang_map = by_lang.get(lang)
                if not lang_map:
                    continue
                candidate = lang_map.get(key)
                if candidate:
                    display_title = _extract_display_title(candidate)
                    if display_title:
                        break
            if not display_title:
                display_title = _extract_display_title(item)
            processed_item = {
                'id': str(item.get('id')),
                'title': item.get('title') or item.get('name'),
                'original_title': item.get('original_title') or item.get('original_name'),
                'display_title': display_title,
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
                    
    except asyncio.TimeoutError:
        message = "TMDB请求超时"
        logger.error(message)
        if raise_on_error:
            raise RuntimeError(message)
        return []
    except Exception as e:
        message = f"TMDB请求发生错误: {e}"
        logger.error(message)
        if raise_on_error:
            raise RuntimeError(message)
        return []

async def get_tmdb_tv_details(tv_id: int, raise_on_error: bool = False) -> Optional[Dict]:
    """
    获取TMDB TV剧的详细信息，包括季度和剧集信息
    """
    try:
        config = load_config()
        
        if not config.tmdb_api.enabled or not config.tmdb_api.api_key:
            message = "TMDB未启用或API Key未配置"
            logger.warning(message)
            if raise_on_error:
                raise RuntimeError(message)
            return None
        
        # TMDB API TV详情端点
        tv_url = f"https://api.themoviedb.org/3/tv/{tv_id}"
        
        # 请求头，包含认证信息
        headers = {
            'Authorization': f'Bearer {config.tmdb_api.api_key}',
            'accept': 'application/json'
        }
        
        system_lang = (getattr(config.general, "system_lang", "") or "")
        params = {
            'language': _language_from_system(system_lang),
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
                    message = f"TMDB详情请求失败: HTTP {response.status}"
                    logger.error(message)
                    if raise_on_error:
                        raise RuntimeError(message)
                    return None
                    
    except asyncio.TimeoutError:
        message = "TMDB详情请求超时"
        logger.error(message)
        if raise_on_error:
            raise RuntimeError(message)
        return None
    except Exception as e:
        message = f"TMDB详情请求发生错误: {e}"
        logger.error(message)
        if raise_on_error:
            raise RuntimeError(message)
        return None

async def analyze_source(url: str, source_type: str) -> AnalyzeSourceResponse:
    """
    分析来源URL，返回标题和TMDB匹配结果
    """
    # 验证输入参数
    if not url or not source_type:
        return AnalyzeSourceResponse(error="URL或类型不能为空")

    cleaned_title = None
    warning = None
    attempted_titles: list[str] = []
    
    try:
        if source_type == "rss":
            # 获取RSS数据和标题
            rss_data = await get_rss_data(url, raise_on_error=True)
            dirty_title = await get_rss_title(url, rss_data)
            if not dirty_title:
                return AnalyzeSourceResponse(error="无法从RSS源获取标题")
            attempted_titles.append(dirty_title)
            from utils.ai import get_cleaned_title
            cleaned_title = await get_cleaned_title(dirty_title)
            if not cleaned_title:
                return AnalyzeSourceResponse(error=f"无法清理标题 {dirty_title}")
            if cleaned_title not in attempted_titles:
                attempted_titles.append(cleaned_title)
            logging.info(f"清理后的标题: {cleaned_title}")
        elif source_type == "magnet":
            # 对于磁力链接，可以尝试从链接中提取标题
            # 这里可以添加磁力链接标题提取逻辑
            from utils.magnet import extract_title_from_torrent
            dirty_title = await extract_title_from_torrent(url, raise_on_error=True)
            attempted_titles.append(dirty_title)
            from utils.ai import get_cleaned_title
            cleaned_title = await get_cleaned_title(dirty_title)
            if not cleaned_title:
                return AnalyzeSourceResponse(error=f"无法清理标题 {dirty_title}")
            if cleaned_title not in attempted_titles:
                attempted_titles.append(cleaned_title)
        else:
            return AnalyzeSourceResponse(error=f"不支持的源类型: {source_type}")
        
        # 用Cleaned标题查询TMDB
        tmdb_results = []
        if cleaned_title:
            try:
                tmdb_results = await search_tmdb(cleaned_title, raise_on_error=True)
            except RuntimeError as e:
                warning = str(e)
        
        return AnalyzeSourceResponse(
            title=cleaned_title,
            tmdb_results=tmdb_results,
            warning=warning,
            attempted_titles=attempted_titles
        )
        
    except Exception as e:
        logger.error(f"分析源时发生错误: {e}")
        raise RuntimeError(f"分析源时发生错误: {str(e)}")
