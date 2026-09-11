from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/audit-logs", tags=["审计日志"])


@router.get("/")
def list_audit_logs(
    table_name: Optional[str] = Query(None, description="按表名过滤，如 patients/visits/exports"),
    action: Optional[str] = Query(None, description="按操作过滤，如 create/update/export/login"),
    record_id: Optional[int] = Query(None, description="按记录 ID 过滤"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """审计日志查询（GCP 可溯源性需求 11.2）。仅管理员可见。"""
    q = db.query(AuditLog)
    if table_name:
        q = q.filter(AuditLog.table_name == table_name)
    if action:
        q = q.filter(AuditLog.action == action)
    if record_id is not None:
        q = q.filter(AuditLog.record_id == record_id)
    total = q.count()
    items = (
        q.order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "table_name": a.table_name,
                "record_id": a.record_id,
                "field_name": a.field_name,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "action": a.action,
                "user_id": a.user_id,
                "center_id": a.center_id,
                "created_at": a.created_at,
            }
            for a in items
        ],
    }
