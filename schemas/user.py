from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class BaseUser(BaseModel):
    """
    基础用户模型，包含公共字段
    """
    username: str

class UserCreate(BaseUser):
    """
    用户创建模型，包含密码字段
    """
    password: str
    is_active: bool
    is_admin: bool