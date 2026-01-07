import aiohttp
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
import logging
from bs4 import BeautifulSoup
from core.config import CONFIG

logger = logging.getLogger(__name__)

async def get_rss_data(url: str, raise_on_error: bool = False) -> Optional[Dict[str, Any]]:
    """
    获取RSS源数据
    """
    try:
        async with aiohttp.ClientSession() as session:
            # 如果配置了代理，使用代理
            content = None
            if CONFIG.general.http_proxy:
                logging.info(f"Using proxy: {CONFIG.general.http_proxy} for URL: {url}")
                async with session.get(
                    url, 
                    timeout=aiohttp.ClientTimeout(total=30),
                    proxy=CONFIG.general.http_proxy
                ) as response:
                    if response.status != 200:
                        error_msg = f"获取RSS失败: HTTP {response.status}"
                        logger.error(error_msg)
                        if raise_on_error:
                            raise RuntimeError(error_msg)
                        return None
                    
                    content = await response.text()
            else:
                async with session.get(
                    url, 
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_msg = f"获取RSS失败: HTTP {response.status}"
                        logger.error(error_msg)
                        if raise_on_error:
                            raise RuntimeError(error_msg)
                        return None
                    
                    content = await response.text()
                    
            # 尝试解析XML
            if content:
                try:
                    root = ET.fromstring(content)
                    return _parse_rss_xml(root)
                except ET.ParseError as e:
                    error_msg = f"RSS解析失败: {e}"
                    logger.error(error_msg)
                    if raise_on_error:
                        raise RuntimeError(error_msg)
                    return None
            else:
                return None
    except Exception as e:
        error_msg = f"获取RSS异常: {e}"
        logger.error(error_msg)
        if raise_on_error:
            raise RuntimeError(error_msg)
        return None

def _parse_rss_xml(root: ET.Element) -> Dict[str, Any]:
    """
    解析RSS XML数据
    """
    rss_data = {
        "title": None,
        "description": None,
        "link": None,
        "items": []
    }
    
    # 查找channel元素
    channel = root.find(".//channel")
    if channel is None:
        # 尝试查找feed元素（Atom格式）
        if root.tag.endswith("feed"):
            return _parse_atom_xml(root)
        return rss_data
    
    # 获取频道信息
    title_elem = channel.find("title")
    if title_elem is not None:
        rss_data["title"] = title_elem.text
    
    desc_elem = channel.find("description")
    if desc_elem is not None:
        rss_data["description"] = desc_elem.text
    
    link_elem = channel.find("link")
    if link_elem is not None:
        rss_data["link"] = link_elem.text
    
    # 获取条目
    items = channel.findall("item")
    for item in items:
        item_data = {}
        
        title_elem = item.find("title")
        if title_elem is not None:
            item_data["title"] = title_elem.text
        
        link_elem = item.find("link")
        if link_elem is not None:
            item_data["link"] = link_elem.text
        
        desc_elem = item.find("description")
        if desc_elem is not None:
            item_data["description"] = desc_elem.text
        
        pub_date_elem = item.find("pubDate")
        if pub_date_elem is not None:
            item_data["pub_date"] = pub_date_elem.text
        
        # 查找enclosure或magnet链接
        enclosure_elem = item.find("enclosure")
        if enclosure_elem is not None:
            item_data["enclosure"] = enclosure_elem.get("url")
        
        # 查找magnet链接（通常在description中）
        if "description" in item_data and item_data["description"]:
            soup = BeautifulSoup(item_data["description"], 'html.parser')
            links = soup.find_all("a")
            for link in links:
                try:
                    # 尝试获取 href 属性
                    href = None
                    if hasattr(link, 'get'):
                        href = link.get("href")  # type: ignore
                    if href and isinstance(href, str) and href.startswith("magnet:"):
                        item_data["magnet"] = href
                        break
                except:
                    continue
        
        rss_data["items"].append(item_data)
    
    return rss_data

def _parse_atom_xml(root: ET.Element) -> Dict[str, Any]:
    """
    解析Atom XML数据
    """
    rss_data = {
        "title": None,
        "description": None,
        "link": None,
        "items": []
    }
    
    # 获取命名空间
    ns = {"atom": root.tag.split("}")[0][1:]} if "}" in root.tag else {}
    
    # 获取feed信息
    title_elem = root.find("atom:title", ns) if ns else root.find("title")
    if title_elem is not None:
        rss_data["title"] = title_elem.text
    
    subtitle_elem = root.find("atom:subtitle", ns) if ns else root.find("subtitle")
    if subtitle_elem is not None:
        rss_data["description"] = subtitle_elem.text
    
    link_elem = root.find("atom:link", ns) if ns else root.find("link")
    if link_elem is not None:
        rss_data["link"] = link_elem.get("href")
    
    # 获取条目
    entries = root.findall("atom:entry", ns) if ns else root.findall("entry")
    for entry in entries:
        item_data = {}
        
        title_elem = entry.find("atom:title", ns) if ns else entry.find("title")
        if title_elem is not None:
            item_data["title"] = title_elem.text
        
        link_elem = entry.find("atom:link", ns) if ns else entry.find("link")
        if link_elem is not None:
            item_data["link"] = link_elem.get("href")
        
        content_elem = entry.find("atom:content", ns) if ns else entry.find("content")
        if content_elem is not None:
            item_data["description"] = content_elem.text
        
        updated_elem = entry.find("atom:updated", ns) if ns else entry.find("updated")
        if updated_elem is not None:
            item_data["pub_date"] = updated_elem.text
        
        rss_data["items"].append(item_data)
    
    return rss_data

async def get_rss_title(url: str, data=None) -> Optional[str]:
    """
    获取RSS源的标题
    """
    if data is None:
        data = await get_rss_data(url)
    
    if data and "title" in data:
        title = data["title"]
        if title:
            # 清理标题，移除多余的空白字符
            title = title.strip()
            # 移除常见的RSS标题后缀
            for suffix in [" - RSS", " RSS", " Feed", " feed"]:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
    
    return None

async def get_item_titles(url: str, data=None) -> Optional[List[str]]:
    """
    获取RSS源的所有条目标题
    """
    if data is None:
        data = await get_rss_data(url)
    
    if data:
        titles = []
        for item in data.get("items", []):
            if "title" in item:
                titles.append(item["title"])
        return titles

    return None

async def get_first_item(url: str, data=None) -> Optional[Dict[str, Any]]:
    """
    获取RSS源的第一个条目
    """
    if data is None:
        data = await get_rss_data(url)
    
    if data and data.get("items"):
        items = data.get("items", [])
        if items:
            return items[0]
    
    return None
