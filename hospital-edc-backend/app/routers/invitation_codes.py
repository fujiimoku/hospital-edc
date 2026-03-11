from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import secrets
from app.database import get_db
from app.models.center import InvitationCode, Center
from app.models.user import User
from app.schemas.invitation import InvitationCodeCreate, InvitationCodeOut
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/invitation-codes", tags=["邀请码管理"])


@router.get("/", response_model=dict)
def list_invitation_codes(
    skip: int = 0,
    limit: int = 50,
    center_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取邀请码列表"""
    query = db.query(InvitationCode)

    # 分中心管理员只能看自己中心的邀请码
    if current_user.role == "center_admin":
        query = query.filter(InvitationCode.center_id == current_user.center_id)
    elif center_id:
        query = query.filter(InvitationCode.center_id == center_id)

    if is_active is not None:
        query = query.filter(InvitationCode.is_active == is_active)

    total = query.count()
    items = query.order_by(InvitationCode.created_at.desc()).offset(skip).limit(limit).all()

    return {"total": total, "items": items}


@router.post("/", response_model=InvitationCodeOut)
def create_invitation_code(
    data: InvitationCodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建邀请码"""
    # 分中心管理员只能为自己的中心创建邀请码
    if current_user.role == "center_admin":
        if data.center_id != current_user.center_id:
            raise HTTPException(403, "只能为自己的中心创建邀请码")

    # 验证中心是否存在
    center = db.query(Center).filter(Center.id == data.center_id).first()
    if not center:
        raise HTTPException(404, "中心不存在")

    # 生成唯一邀请码
    code = secrets.token_urlsafe(16)

    # 设置过期时间
    expires_at = None
    if data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_days)

    invitation = InvitationCode(
        code=code,
        center_id=data.center_id,
        role=data.role,
        max_uses=data.max_uses or 1,
        expires_at=expires_at,
        created_by=current_user.id,
    )

    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


@router.delete("/{code_id}")
def deactivate_invitation_code(
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """停用邀请码"""
    code = db.query(InvitationCode).filter(InvitationCode.id == code_id).first()
    if not code:
        raise HTTPException(404, "邀请码不存在")

    # 分中心管理员只能停用自己中心的邀请码
    if current_user.role == "center_admin" and code.center_id != current_user.center_id:
        raise HTTPException(403, "无权操作该邀请码")

    code.is_active = False
    db.commit()
    return {"message": "邀请码已停用"}


@router.get("/validate/{code}")
def validate_invitation_code(
    code: str,
    db: Session = Depends(get_db),
):
    """验证邀请码（公开接口，用于注册页面）"""
    code_record = db.query(InvitationCode).filter(
        InvitationCode.code == code,
        InvitationCode.is_active == True
    ).first()

    if not code_record:
        return {"valid": False, "message": "邀请码无效"}

    if code_record.expires_at and code_record.expires_at < datetime.utcnow():
        return {"valid": False, "message": "邀请码已过期"}

    if code_record.used_count >= code_record.max_uses:
        return {"valid": False, "message": "邀请码已达到最大使用次数"}

    # 获取中心信息
    center = db.query(Center).filter(Center.id == code_record.center_id).first()

    return {
        "valid": True,
        "center_name": center.center_name if center else None,
        "role": code_record.role,
    }
