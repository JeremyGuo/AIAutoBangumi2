from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from core.user import authenticate_user, create_access_token, get_user_count, get_user_by_username, create_user
from models.session import get_db
import logging

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger("api.auth")

# 登录表单处理（网页表单提交）
@router.post("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """处理登录表单"""
    logging.info(f"用户尝试登录: {username} {password}")
    user = await authenticate_user(db, username, password)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "用户名或密码错误"}
        )
    
    # 创建访问令牌（使用用户ID）
    access_token = create_access_token(user.id)
    
    # 创建带有Token的重定向响应
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=60 * 60 * 24 * 365 * 100,
        path="/"
    )
    return response

from schemas.user import UserCreate
# 注册表单处理
@router.post("/register", response_class=HTMLResponse)
async def register_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """处理注册表单"""
    try:
        # 检查是否是第一个用户
        user_count = await get_user_count(db)
        is_first_user = user_count == 0
        # 第一个用户默认是管理员并且active
        # 后续用户默认不是管理员且inactive
        
        # 检查用户名是否已存在
        existing_user = await get_user_by_username(db, username)
        if existing_user:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "用户名已存在"}
            )
        
        # 创建新用户
        user_create = UserCreate(username=username,
                                 password=password,
                                 is_active=is_first_user,
                                 is_admin=is_first_user)
        user = await create_user(db, user_create)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"detail": "用户注册成功"}
        )
        
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "注册失败，请稍后再试"}
        )

# 添加登出路由
@router.get("/logout")
async def logout():
    """用户登出"""
    response = RedirectResponse(url="/api/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", path="/")
    return response
