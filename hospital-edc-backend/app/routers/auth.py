from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.center import InvitationCode
from app.schemas.user import UserCreate, UserOut
from app.dependencies import (
    verify_password, hash_password,
    create_access_token, get_current_user, require_admin,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "center_id": user.center_id,
        },
    }


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/register", response_model=UserOut)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),   # 只有管理员可以创建账号
):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role or "researcher",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password")
def change_password(
    old_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.hashed_password = hash_password(new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.post("/register-with-code", response_model=UserOut)
def register_with_invitation_code(
    username: str,
    password: str,
    full_name: str,
    invitation_code: str,
    db: Session = Depends(get_db),
):
    """使用邀请码注册账号"""
    # 验证邀请码
    code_record = db.query(InvitationCode).filter(
        InvitationCode.code == invitation_code,
        InvitationCode.is_active == True
    ).first()

    if not code_record:
        raise HTTPException(status_code=400, detail="邀请码无效")

    # 检查邀请码是否过期
    if code_record.expires_at and code_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="邀请码已过期")

    # 检查使用次数
    if code_record.used_count >= code_record.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已达到最大使用次数")

    # 检查用户名是否已存在
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户
    user = User(
        username=username,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=code_record.role,
        center_id=code_record.center_id,
    )
    db.add(user)

    # 更新邀请码使用次数
    code_record.used_count += 1

    db.commit()
    db.refresh(user)
    return user