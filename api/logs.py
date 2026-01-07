from __future__ import annotations

from collections import deque
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from core.user import get_current_admin_user
from core.logging_config import LOG_FILE
from models.models import User

router = APIRouter()

MAX_LIMIT = 2000
DEFAULT_LIMIT = 200
DEFAULT_PAGE = 1


def _parse_log_line(line: str) -> dict:
    line = line.rstrip("\n")
    parts = line.split(" | ", 3)
    if len(parts) == 4:
        timestamp, level, logger, message = parts
        return {
            "timestamp": timestamp,
            "level": level,
            "logger": logger,
            "message": message,
            "raw": line,
        }
    return {"raw": line}


@router.get("/recent")
async def get_recent_logs(
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    level: Optional[str] = None,
    keyword: Optional[str] = None,
    logger: Optional[str] = None,
    user: User = Depends(get_current_admin_user),
):
    """获取最近日志"""
    if not LOG_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "日志文件不存在"},
        )

    max_buffer = max(2000, page_size * (page + 1))
    lines: deque[str] = deque(maxlen=max_buffer)
    try:
        with LOG_FILE.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                lines.append(line)
    except OSError as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"读取日志失败: {exc}"},
        )

    level_filter = level.upper() if level else None
    keyword_filter = keyword.lower() if keyword else None
    logger_filter = logger.lower() if logger else None

    items = []
    offset = (page - 1) * page_size
    matched = 0
    has_more = False
    for line in reversed(lines):
        entry = _parse_log_line(line)
        raw = entry.get("raw", "")

        if level_filter and entry.get("level", "").upper() != level_filter:
            continue
        if keyword_filter and keyword_filter not in raw.lower():
            continue
        if logger_filter and logger_filter not in entry.get("logger", "").lower():
            continue

        if matched < offset:
            matched += 1
            continue

        if len(items) < page_size:
            items.append(entry)
            matched += 1
            continue

        has_more = True
        break

    return {
        "status": "success",
        "total": len(items),
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "log_file": str(LOG_FILE),
    }
