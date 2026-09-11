"""站内通知：写 notifications 表。调用方负责 commit。"""
from sqlalchemy.orm import Session

from app.models.notification import Notification


def notify_user(db: Session, user_id: int | None, type_: str, content: str,
                center_id: int | None = None) -> None:
    if not user_id:
        return
    db.add(Notification(user_id=user_id, center_id=center_id, type=type_, content=content))
