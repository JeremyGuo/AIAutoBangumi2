import aiohttp
import json
import re
from typing import Tuple, List, Dict
from core.config import CONFIG
import logging


async def call_llm_api(messages: List[Dict[str, str]]) -> str:
    """
    调用 OpenAI 风格的 LLM API
    
    Args:
        messages: 消息列表，格式为 [{"role": "user/assistant/system", "content": "内容"}]
    
    Returns:
        AI 的回复内容
    """
    if not CONFIG.llm.enable:
        return ""
    
    try:
        headers = {
            "Authorization": f"Bearer {CONFIG.llm.token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": CONFIG.llm.name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(CONFIG.llm.url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    print(f"LLM API 调用失败: {response.status}")
                    return ""
    except Exception as e:
        print(f"LLM API 调用异常: {e}")
        return ""


async def get_cleaned_title(title: str) -> str:
    """
    通过搜索和AI清洗标题，去除发布组织名称等冗余信息
    
    Args:
        title: 原始标题
    
    Returns:
        清洗后的干净标题
    """
    try:
        messages = [
            {
                "role": "user",
                "content": f"""从下面的标题中，清洗掉除了标题之外的所有内容，只保留一种语言，不要保留季度等信息，只要标题。将返回的内容写入<title></title>中：{title}"""
            }
        ]
        
        # 步骤3: 调用AI获取清洗结果
        result = await call_llm_api(messages)
        # cleaned_title = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
        cleaned_title = re.search(r'<title>(.*?)</title>', result, re.DOTALL)

        if cleaned_title:
            return cleaned_title.group(1).strip()
        else:
            # AI调用失败时的备用方案
            return (await basic_title_cleanup(title)).strip()
            
    except Exception as e:
        print(f"标题清洗失败: {e}")
        return await basic_title_cleanup(title)


async def basic_title_cleanup(title: str) -> str:
    """
    基础的标题清理，作为AI清理失败时的备用方案
    
    Args:
        title: 原始标题
    
    Returns:
        基础清理后的标题
    """
    # 移除常见的发布组织标识
    patterns_to_remove = [
        r'\[.*?Mikan.*?\]',          # [Mikan Project]
        r'\[.*?ANi.*?\]',            # [ANi]
        r'\[.*?Nyaa.*?\]',           # [Nyaa]
        r'\[.*?DMHY.*?\]',           # [DMHY]
        r'\[.*?字幕组.*?\]',          # [字幕组]
        r'\[.*?SubGroup.*?\]',       # [SubGroup]
        r'Mikan\s*Project\s*-?\s*',  # Mikan Project -
        r'ANi\s*-?\s*',              # ANi -
        r'Nyaa\s*-?\s*',             # Nyaa -
        r'\[\d+p\]',                 # [1080p], [720p]
        r'\[HEVC\]',                 # [HEVC]
        r'\[H\.?264\]',              # [H.264], [H264]
        r'\[H\.?265\]',              # [H.265], [H265]
        r'\[.*?简体.*?\]',            # [简体中文]
        r'\[.*?繁体.*?\]',            # [繁体中文]
        r'\[.*?中文.*?\]',            # [中文字幕]
        r'\[.*?字幕.*?\]',            # [字幕]
        r'\[.*?SUB.*?\]',            # [SUB]
        r'\[.*?DUB.*?\]',            # [DUB]
        r'- \d+$',                   # - 01 (集数)
        r'\s+\d+$',                  # 空格加集数
    ]
    
    cleaned = title
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # 清理多余的空格和符号
    cleaned = re.sub(r'\s*-\s*$', '', cleaned)  # 移除末尾的 -
    cleaned = re.sub(r'^\s*-\s*', '', cleaned)  # 移除开头的 -
    cleaned = re.sub(r'\s+', ' ', cleaned)      # 合并多个空格
    cleaned = cleaned.strip()
    
    # 如果清理后为空，返回原标题
    return cleaned if cleaned else title

async def get_regex_from_titles(title: str) -> str:
    """
    根据文件标题列表生成提取剧集编号的正则表达式
    
    Args:
        title: 单个标题或用 | 分隔的多个标题
    
    Returns:
        用于提取剧集编号的正则表达式
    """
    try:
        # 如果启用了LLM，优先使用AI生成
        if CONFIG.llm.enable:
            ai_regex = await _get_regex_with_ai(title)
            if ai_regex:
                logging.info(f"AI生成的正则表达式: {ai_regex}")
                return ai_regex
        
        # 备用方案：使用规则生成
        return await _get_regex_with_rules(title)
        
    except Exception as e:
        print(f"正则表达式生成失败: {e}")
        return await _get_regex_with_rules(title)

async def _get_regex_with_ai(title: str) -> str:
    """
    使用AI生成正则表达式
    """
    try:
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的正则表达式专家。你的任务是分析动漫文件名，生成能够提取剧集编号的正则表达式。"
            },
            {
                "role": "user",
                "content": f"""分析下面这个动漫标题，为其生成一个用于提取集数的正则表达式。标题可能包含多个，使用|分割。

<title>{title}</title>

请提供一个正则表达式，用于从类似格式的标题中提取剧集号码。
正则表达式应该:
1. 使用括号 () 来捕获集数
2. 正确匹配标题中表示集数的部分（如E01, 第01集, EP.01等）
3. 只捕获数字部分
4. 尽可能精确，避免误匹配
5. 测试你的正则表达式能否从第一个标题中正确提取集数

请在<regex>标签中返回正则表达式。
例如: <regex>E(\\d+)</regex> 或 <regex>第(\\d+)集</regex>

如果无法确定，返回 <regex>null</regex>。

请确保你的正则表达式能够从提供的标题中正确提取集数。"""
            }
        ]
        
        result = await call_llm_api(messages)
        if result and result.strip():
            # 提取<regex>标签中的内容
            match = re.search(r'<regex>(.*?)</regex>', result, re.DOTALL)
            regex = None
            if match:
                regex = match.group(1).strip()
            
            if not regex:
                print(f"AI未返回正则表达式 {result}")
                return ""

            # 验证正则表达式有效性
            try:
                re.compile(regex)
                return regex
            except re.error:
                print(f"AI生成的正则表达式无效: {regex}")
                return ""
        
        return ""
        
    except Exception as e:
        print(f"AI生成正则表达式失败: {e}")
        return ""

async def _get_regex_with_rules(title: str) -> str:
    """
    使用规则生成正则表达式
    """
    # 分析标题列表
    titles = title.split('|') if '|' in title else [title]
    
    # 常见的剧集编号模式
    patterns = [
        r'- (\d+)',           # - 01, - 1
        r'第(\d+)集',          # 第01集, 第1集
        r'第(\d+)话',          # 第01话, 第1话
        r'\[(\d+)\]',         # [01], [1]
        r'EP(\d+)',           # EP01, EP1
        r'Episode (\d+)',     # Episode 01, Episode 1
        r' (\d+)$',           # 空格+数字结尾
        r'_(\d+)',            # _01, _1
        r'\.(\d+)\.',         # .01., .1.
        r'S\d+E(\d+)',        # S01E01, S1E1
    ]
    
    # 测试每个模式
    for pattern in patterns:
        matches = 0
        test_results = []
        for title_text in titles[:5]:  # 只检查前5个标题
            match = re.search(pattern, title_text, re.IGNORECASE)
            if match:
                matches += 1
                try:
                    episode_num = match.group(1)
                    test_results.append(f"从 '{title_text}' 提取到: {episode_num}")
                except:
                    pass
        
        # 如果超过一半的标题匹配这个模式，使用它
        if matches >= max(1, len(titles[:5]) // 2):
            if test_results:
                logging.info(f"规则生成的正则表达式: {pattern}")
                logging.info("测试结果: " + "; ".join(test_results[:3]))  # 只显示前3个结果
            return pattern
    
    # 如果没有找到匹配的模式，尝试找到数字
    # 查找独立的数字（被非数字字符包围）
    for title_text in titles[:3]:  # 检查前3个标题
        # 查找可能的剧集编号
        numbers = re.findall(r'(?:^|[^\d])(\d{1,3})(?:[^\d]|$)', title_text)
        if numbers:
            # 找到数字，尝试构建正则表达式
            # 查找数字前后的字符
            for num in numbers:
                # 如果数字看起来像剧集编号（1-999之间）
                if 1 <= int(num) <= 999:
                    # 找到这个数字在标题中的位置
                    match = re.search(rf'([^\d]?)({re.escape(num)})([^\d]?)', title_text)
                    if match:
                        before, number, after = match.groups()
                        # 构建正则表达式
                        before_pattern = re.escape(before) if before else ''
                        after_pattern = re.escape(after) if after else ''
                        pattern = f'{before_pattern}(\\d+){after_pattern}'
                        return pattern
    
    # 默认模式：查找独立的数字
    return r'(\d+)'

# 保留原函数名作为别名，以兼容API调用
async def get_regex_from_title(title: str) -> str:
    """别名函数，与get_regex_from_titles功能相同"""
    return await get_regex_from_titles(title)

async def is_file_important(filename: str) -> Tuple[bool, bool, bool]:
    """
    使用AI判断文件是否重要
    返回: (是否重要, 是否主要剧集, 是否视频文件)
    """
    try:
        # 如果LLM未启用，使用备用规则判断
        if not CONFIG.llm.enable:
            return await _fallback_file_importance_check(filename)
        
        filename_lower = filename.lower()
        
        # 首先检查文件扩展名确定文件类型
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
        subtitle_extensions = ['.srt', '.ass', '.ssa', '.vtt', '.sub']
        
        is_video = any(filename_lower.endswith(ext) for ext in video_extensions)
        is_subtitle = any(filename_lower.endswith(ext) for ext in subtitle_extensions)
        
        if not (is_video or is_subtitle):
            return False, False, False
        
        # 使用AI分析文件重要性
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的动漫文件分析助手。你需要分析文件名并判断：
1. 这个文件是否重要（值得下载和保存）
2. 这个文件是否是主要剧集（正片，非特别篇/OVA/预告等）
3. 这个文件是否是视频文件

请根据文件名的内容进行分析。"""
            },
            {
                "role": "user",
                "content": f"""请分析这个文件名并做出判断：

文件名: {filename}

请分析以下方面：
1. 是否是重要文件（不是样片sample、预告trailer、菜单menu、片头ncop、片尾nced等）
2. 是否是主要剧集（不是特别篇sp/special、OVA、OAD、电影movie、PV等）
3. 文件类型（已知是{'视频' if is_video else '字幕'}文件）

注意：
- 电影文件虽然重要，但不算主要剧集
- 特别篇/OVA/OAD 等虽然重要，但不算主要剧集
- 样片、预告片、片头片尾等都不重要

请严格按照以下JSON格式返回结果，不要包含任何其他内容：
{{
    "is_important": true/false,
    "is_main_episode": true/false,
    "is_video": true/false,
    "reason": "简短的判断理由"
}}"""
            }
        ]
        
        result = await call_llm_api(messages)
        
        if result:
            try:
                # 尝试解析JSON回复
                # 提取JSON部分
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                    
                    is_important = analysis.get('is_important', False)
                    is_main_episode = analysis.get('is_main_episode', False)
                    reason = analysis.get('reason', '')
                    
                    logging.info(f"AI文件分析 - {filename}: 重要={is_important}, 主剧集={is_main_episode}, 理由={reason}")
                    
                    return is_important, is_main_episode, is_video
                    
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"AI回复解析失败: {e}, 回复内容: {result}")
        
        # AI分析失败时的备用方案
        logging.warning(f"AI分析文件失败，使用备用规则: {filename}")
        return await _fallback_file_importance_check(filename)
        
    except Exception as e:
        logging.error(f"文件重要性AI分析异常: {e}")
        return await _fallback_file_importance_check(filename)

async def _fallback_file_importance_check(filename: str) -> Tuple[bool, bool, bool]:
    """
    备用的文件重要性检查规则
    """
    filename_lower = filename.lower()
    
    # 视频文件扩展名
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    # 字幕文件扩展名
    subtitle_extensions = ['.srt', '.ass', '.ssa', '.vtt', '.sub']
    
    # 检查是否是视频或字幕文件
    is_video = any(filename_lower.endswith(ext) for ext in video_extensions)
    is_subtitle = any(filename_lower.endswith(ext) for ext in subtitle_extensions)
    
    if not (is_video or is_subtitle):
        return False, False, False
    
    # 跳过样片、预告片等
    skip_keywords = ['sample', 'preview', 'trailer', 'ncop', 'nced', 'menu']
    if any(keyword in filename_lower for keyword in skip_keywords):
        return False, False, is_video
    
    # 判断是否是特别篇
    special_keywords = ['sp', 'special', 'ova', 'oad', 'movie', 'pv']
    is_special = any(keyword in filename_lower for keyword in special_keywords)
    
    # 判断是否是主要剧集（非特别篇）
    is_main_episode = not is_special
    
    return True, is_main_episode, is_video

async def get_episode_from_filename(filename: str) -> int:
    """
    使用AI从文件名中提取剧集编号
    """
    try:
        # 如果LLM未启用，使用备用规则判断
        if not CONFIG.llm.enable:
            return await _fallback_episode_extraction(filename)
        
        # 使用AI分析文件名提取剧集编号
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的动漫文件名分析助手。你需要从文件名中准确提取剧集编号。

规则：
1. 找到文件名中表示剧集编号的数字
2. 忽略年份、分辨率、画质等无关数字
3. 返回0表示无法确定剧集编号
4. 剧集编号通常在1-999范围内"""
            },
            {
                "role": "user",
                "content": f"""请从这个文件名中提取剧集编号：

文件名: {filename}

请分析文件名中的各个数字，识别哪个是剧集编号。

常见格式包括：
- 第01集、第1话
- E01、EP01、Episode 01
- S01E01（提取E后的数字）
- [01]、(01)
- 末尾的独立数字（如 - 01）

请严格按照以下JSON格式返回结果，不要包含任何其他内容：
{{
    "episode_number": 数字或0,
    "confidence": "high/medium/low",
    "reason": "简短的提取理由"
}}

如果无法确定剧集编号，episode_number返回0。"""
            }
        ]
        
        result = await call_llm_api(messages)
        
        if result:
            try:
                # 尝试解析JSON回复
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                    
                    episode_number = analysis.get('episode_number', 0)
                    confidence = analysis.get('confidence', 'low')
                    reason = analysis.get('reason', '')
                    
                    # 验证剧集编号合理性
                    if isinstance(episode_number, int) and 1 <= episode_number <= 999:
                        logging.info(f"AI剧集提取 - {filename}: 集数={episode_number}, 置信度={confidence}, 理由={reason}")
                        return episode_number
                    elif episode_number == 0:
                        logging.info(f"AI剧集提取 - {filename}: 无法确定剧集编号, 理由={reason}")
                        return 0
                    else:
                        logging.warning(f"AI返回无效剧集编号: {episode_number}, 使用备用方案")
                        
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"AI回复解析失败: {e}, 回复内容: {result}")
        
        # AI分析失败时的备用方案
        logging.warning(f"AI剧集提取失败，使用备用规则: {filename}")
        return await _fallback_episode_extraction(filename)
        
    except Exception as e:
        logging.error(f"剧集编号AI提取异常: {e}")
        return await _fallback_episode_extraction(filename)

async def _fallback_episode_extraction(filename: str) -> int:
    """
    备用的剧集编号提取规则
    """
    try:
        # 常见的剧集编号模式
        patterns = [
            r'第(\d+)[话集話]',          # 第1话, 第01集
            r'[Ee]p?\.?(\d+)',          # E01, ep.1, E1
            r'[第](\d+)[话集話期]',       # 第1话
            r'(\d+)[话集話期]',          # 1话, 01集
            r'[\[\(](\d+)[\]\)]',       # [01], (1)
            r'Episode (\d+)',           # Episode 01
            r'EP(\d+)',                 # EP01
            r'S\d+E(\d+)',             # S01E01
            r'- (\d+)',                # - 01
            r'(\d{2,3})(?!x\d)',       # 两到三位数字，但不是分辨率
        ]
        
        filename_clean = filename.replace('_', ' ').replace('.', ' ')
        
        for pattern in patterns:
            match = re.search(pattern, filename_clean, re.IGNORECASE)
            if match:
                episode_num = int(match.group(1))
                # 过滤掉明显不是剧集编号的数字（比如年份、分辨率等）
                if 1 <= episode_num <= 999:
                    return episode_num
        
        return 0
    except Exception as e:
        logging.error(f"备用剧集提取失败 {filename}: {e}")
        return 0
