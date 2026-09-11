"""审计留痕服务：写 audit_logs，字段级 diff。"""
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_change(db: Session, user, table_name: str, record_id: int,
               changes: dict, action: str = "update") -> None:
    """记录字段级前后值。changes = {field: (old, new)}。

    调用方负责 commit（与业务写操作同事务）。
    """
    if user is None:
        return
    for field, (old, new) in changes.items():
        db.add(AuditLog(
            table_name=table_name,
            record_id=record_id,
            field_name=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            action=action,
            user_id=user.id,
            center_id=getattr(user, "center_id", None),
        ))


def log_action(db: Session, user, table_name: str, record_id: int,
               action: str, detail: str = "") -> None:
    """记录一次动作（状态流转/导出/登录等），detail 放入 new_value。"""
    if user is None:
        return
    db.add(AuditLog(
        table_name=table_name,
        record_id=record_id,
        field_name="-",
        new_value=detail,
        action=action,
        user_id=user.id,
        center_id=getattr(user, "center_id", None),
    ))


def diff_model(obj, data: dict) -> dict:
    """对将要 setattr 的字段做 diff：{field: (old, new)}。"""
    changes = {}
    for key, new in data.items():
        old = getattr(obj, key, None)
        if old != new:
            changes[key] = (old, new)
    return changes
