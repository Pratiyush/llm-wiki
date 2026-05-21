"""Authentication routes — login, register, current user."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from llmwiki import REPO_ROOT
from llmwiki.web.database import get_db
from llmwiki.web.models import User

load_dotenv(REPO_ROOT / ".env")


def _resolve_secret_key() -> str:
    """Resolve JWT secret key: env var > persisted file > auto-generate."""
    env_key = os.environ.get("JWT_SECRET_KEY")
    if env_key:
        return env_key

    secret_file = REPO_ROOT / ".jwt_secret"
    if secret_file.is_file():
        return secret_file.read_text(encoding="utf-8").strip()

    generated = secrets.token_hex(32)
    secret_file.write_text(generated, encoding="utf-8")
    print(
        f"  warning: no JWT_SECRET_KEY set — auto-generated a random key "
        f"({secret_file}). Set JWT_SECRET_KEY in .env for persistent deployments.",
    )
    return generated


SECRET_KEY = _resolve_secret_key()
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _create_token(user: User) -> str:
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency: extract current user from JWT token."""
    exc = HTTPException(status_code=401, detail="未登录或登录已过期")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise exc
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise exc
    return user


def require_leader(user: User = Depends(get_current_user)) -> User:
    """Dependency: require leader or admin role."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要部门长或管理员权限")
    return user


@router.post("/login")
async def login(body: dict, db: Session = Depends(get_db)):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="请输入用户名和密码")

    user = db.query(User).filter(User.username == username).first()
    if not user or not _verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = _create_token(user)
    return {
        "token": token,
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "department": user.department,
            "role": user.role,
        },
    }


@router.post("/register")
async def register(body: dict, db: Session = Depends(get_db)):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    full_name = body.get("full_name", "")
    department = body.get("department", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少4个字符")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # First user becomes admin
    is_first = db.query(User).count() == 0
    role = "admin" if is_first else "staff"

    user = User(
        username=username,
        hashed_password=_hash_password(password),
        full_name=full_name,
        department=department,
        role=role,
    )
    db.add(user)
    db.commit()

    token = _create_token(user)
    return {
        "token": token,
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "department": user.department,
            "role": user.role,
        },
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "username": user.username,
        "full_name": user.full_name,
        "department": user.department,
        "role": user.role,
    }


@router.post("/change-password")
async def change_password(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")
    if not _verify_password(old_pw, user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(new_pw) < 4:
        raise HTTPException(status_code=400, detail="新密码至少4个字符")
    user.hashed_password = _hash_password(new_pw)
    db.commit()
    return {"status": "ok"}


@router.get("/users")
async def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin: list all users."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看用户列表")
    users = db.query(User).order_by(User.id).all()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "department": u.department,
                "role": u.role,
                "is_active": u.is_active,
            }
            for u in users
        ]
    }


@router.post("/users/{user_id}/role")
async def update_role(user_id: int, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin: change a user's role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改角色")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_role = body.get("role", "staff")
    if new_role not in ("admin", "leader", "staff"):
        raise HTTPException(status_code=400, detail="无效角色")
    target.role = new_role
    db.commit()
    return {"status": "ok"}
