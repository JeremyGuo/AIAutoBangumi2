#!/usr/bin/python3
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import logging

from api.auth import router as auth_router
from api.source import router as source_router
from api.torrent import router as torrent_router
from api.user import router as user_router
from api.cache import router as cache_router
from api.statistics import router as statistics_router
from api.tags import router as tags_router
from api.batch import router as batch_router
from api.backup import router as backup_router
from api.search import router as search_router
from api.notifications import router as notifications_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from utils.dht import dht_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...")
    # 初始化数据库
    from models.session import init_db
    await init_db()
    
    # 启动定时任务调度器
    from core.scheduler import scheduler
    await scheduler.start()

    # 启动DHT服务
    dht_service.start()
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")
    # 停止定时任务调度器
    await scheduler.stop()

    # 停止DHT服务
    dht_service.stop()

# Create FastAPI app
app = FastAPI(
    title="AIAutoBangumi2",
    description="AI Auto Bangumi Management System - 智能动漫自动下载与管理系统",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add middleware
from core.middleware import (
    RequestLoggingMiddleware,
    ErrorHandlingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
# Rate limiting: 100 requests per minute per IP (can be adjusted)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

# Include API routers
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(source_router, prefix="/api/source", tags=["源管理"])
app.include_router(torrent_router, prefix="/api/torrent", tags=["种子管理"])
app.include_router(user_router, prefix="/api/user", tags=["用户管理"])
app.include_router(cache_router, prefix="/api/cache", tags=["缓存管理"])
app.include_router(statistics_router, prefix="/api/statistics", tags=["统计分析"])
app.include_router(tags_router, prefix="/api/tags", tags=["标签管理"])
app.include_router(batch_router, prefix="/api/batch", tags=["批量操作"])
app.include_router(backup_router, prefix="/api/backup", tags=["备份导出"])
app.include_router(search_router, prefix="/api/search", tags=["搜索过滤"])
app.include_router(notifications_router, prefix="/api/notifications", tags=["通知服务"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates with custom delimiters to avoid conflict with Vue.js
from jinja2 import Environment, FileSystemLoader
jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    variable_start_string='{%',
    variable_end_string='%}',
    block_start_string='{%%',
    block_end_string='%%}',
    comment_start_string='{#',
    comment_end_string='#}'
)
templates = Jinja2Templates(env=jinja_env)

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "AIAutoBangumi2"
    }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login.html", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register.html", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the register page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/new_source.html", response_class=HTMLResponse)
async def new_source_page(request: Request):
    """Serve the new source page"""
    return templates.TemplateResponse("new_source.html", {"request": request})

@app.get("/source.html", response_class=HTMLResponse)
async def source_detail_page(request: Request):
    """Serve the source detail page"""
    return templates.TemplateResponse("source.html", {"request": request})

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    """Catch-all route for SPA routing - serves main page for non-API routes"""
    # If the path starts with 'api', it should have been handled by API routers
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # For all other paths, serve the main page (SPA routing)
    return templates.TemplateResponse("index.html", {"request": request})

from core.config import CONFIG

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=CONFIG.general.address,
        port=CONFIG.general.listen,
        reload=True,
        log_level="info"
    )


