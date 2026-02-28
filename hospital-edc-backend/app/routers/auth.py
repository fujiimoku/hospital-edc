from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
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