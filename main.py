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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")
    # 停止定时任务调度器
    await scheduler.stop()

# Create FastAPI app
app = FastAPI(
    title="AIAutoBangumi2",
    description="AI Auto Bangumi Management System",
    version="2.0.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(source_router, prefix="/api/source")
app.include_router(torrent_router, prefix="/api/torrent")
app.include_router(user_router, prefix="/api/user")
app.include_router(cache_router, prefix="/api/cache")

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


