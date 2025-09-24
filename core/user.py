from datetime import datetime, timedelta
from typing import Optional, Union, Any, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.config import CONFIG
from sqlalchemy.ext.asyncio import AsyncSession
from models.session import get_db
from models.models import User
from schemas.user import UserCreate
from fastapi import FastAPI, Depends, Request
import logging

# 配置密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 配置 JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 配置 OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)

from pydantic import BaseModel
from typing import Optional, Union
from datetime import datetime

class TokenPayload(BaseModel):
    """用于解析JWT令牌的payload数据"""
    sub: Optional[str] = None
    exp: Optional[float] = None

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌，始终使用用户ID（转换为字符串）作为subject
    
    Args:
        subject: 用户ID
        expires_delta: 过期时间增量
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # 确保subject始终是字符串
    to_encode = {"exp": expire.timestamp(), "sub": str(user_id)}
    encoded_jwt = jwt.encode(to_encode, CONFIG.general.secret_key, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(token, CONFIG.general.secret_key, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        # 检查是否过期
        if datetime.fromtimestamp(token_data.exp) < datetime.now():
            return None
        return token_data
    except (JWTError, Exception) as e:
        logging.error(f"JWT验证失败: {str(e)}")
        return None

def get_token_from_request(request: Request) -> Optional[str]:
    """
    从请求中获取JWT令牌，支持从Authorization头部或Cookie中获取
    """
    # 尝试从Authorization头部获取
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    # 尝试从Cookie中获取
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        return token.split(" ")[1]
    elif token:
        return token
    return None

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """
    获取当前用户，使用JWT令牌验证用户身份
    """
    token = get_token_from_request(request)
    # logging.info(f"获取当前用户: {token}")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = await verify_token(token)
    if not token_data or not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = str(token_data.sub)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return user

async def get_current_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前管理员用户，确保用户是管理员
    """
    user = await get_current_user(request, db)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="操作需要管理员权限"
        )
    return user

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """
    验证用户凭据，返回用户对象或None
    """
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

from sqlalchemy import select, func

async def get_user_count(db: AsyncSession) -> int:
    """
    获取用户总数
    """
    result = await db.execute(select(func.count(User.id)))
    return result.scalar_one() if result else 0

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    根据用户名获取用户对象
    """
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    return user

async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    """
    创建新用户
    """
    hashed_password = get_password_hash(user_create.password)
    user = User(
        username=user_create.username,
        hashed_password=hashed_password,
        is_active=user_create.is_active,
        is_admin=user_create.is_admin
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user