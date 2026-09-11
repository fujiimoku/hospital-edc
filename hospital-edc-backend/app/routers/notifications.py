from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.notification import Notification
from app.models.user import User
from app.services.reminder import scan_followup_windows

router = APIRouter(prefix="/api/notifications", tags=["站内通知"])


@router.get("/")
def list_notifications(
    unread_only: bool = Query(False, description="true=只看未读"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的通知列表（仅本人）。"""
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    items = q.order_by(Notification.id.desc()).limit(limit).all()
    unread = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).count()
    return {
        "unread": unread,
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "content": n.content,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in items
        ],
    }


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """顶栏铃铛未读数。"""
    cnt = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).count()
    return {"unread": cnt}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记单条已读（仅本人）。"""
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n or n.user_id != current_user.id:
        raise HTTPException(404, "通知不存在")
    n.is_read = True
    db.commit()
    return {"message": "已标记为已读", "id": notification_id}


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全部标记已读。"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "已全部标记为已读"}


@router.post("/scan-followups")
def trigger_followup_scan(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """手动触发随访窗口扫描（正式部署可配定时任务调用 scan_followup_windows）。"""
    created = scan_followup_windows(db)
    return {"message": "扫描完成", "created": created}
