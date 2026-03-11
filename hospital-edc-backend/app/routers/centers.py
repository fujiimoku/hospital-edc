from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models.center import Center
from app.models.user import User
from app.schemas.center import CenterCreate, CenterUpdate, CenterOut
from app.dependencies import get_current_user, require_main_admin

router = APIRouter(prefix="/api/centers", tags=["中心管理"])


@router.get("/", response_model=dict)
def list_centers(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = Query(None, description="按中心编号或名称搜索"),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取中心列表"""
    query = db.query(Center)

    if search:
        query = query.filter(
            Center.center_code.contains(search) | Center.center_name.contains(search)
        )

    if is_active is not None:
        query = query.filter(Center.is_active == is_active)

    total = query.count()
    items = query.order_by(Center.id).offset(skip).limit(limit).all()

    return {"total": total, "items": items}


@router.post("/", response_model=CenterOut)
def create_center(
    data: CenterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_admin),
):
    """创建新中心（仅总管理员）"""
    # 检查中心编号是否已存在
    if db.query(Center).filter(Center.center_code == data.center_code).first():
        raise HTTPException(400, "中心编号已存在")

    center = Center(**data.model_dump())
    db.add(center)
    db.commit()
    db.refresh(center)
    return center


@router.get("/{center_id}", response_model=CenterOut)
def get_center(
    center_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取中心详情"""
    center = db.query(Center).filter(Center.id == center_id).first()
    if not center:
        raise HTTPException(404, "中心不存在")
    return center


@router.put("/{center_id}", response_model=CenterOut)
def update_center(
    center_id: int,
    data: CenterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_admin),
):
    """更新中心信息（仅总管理员）"""
    center = db.query(Center).filter(Center.id == center_id).first()
    if not center:
        raise HTTPException(404, "中心不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(center, key, value)

    db.commit()
    db.refresh(center)
    return center


@router.delete("/{center_id}")
def deactivate_center(
    center_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_admin),
):
    """停用中心（仅总管理员）"""
    center = db.query(Center).filter(Center.id == center_id).first()
    if not center:
        raise HTTPException(404, "中心不存在")

    center.is_active = False
    db.commit()
    return {"message": "中心已停用"}
