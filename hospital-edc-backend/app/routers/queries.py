from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.query import Query
from app.models.visit import Visit
from app.models.patient import Patient
from app.schemas.query import QueryCreate, QueryAnswer, QueryOut
from app.dependencies import (
    get_current_user, get_accessible_center_ids,
    require_qc, require_researcher,
)
from app.services.audit import log_action
from app.services.notify import notify_user

router = APIRouter(prefix="/api/queries", tags=["数据质疑 Query"])


def _get_accessible_visit(db: Session, visit_id: int, current_user) -> Visit:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and (patient is None or patient.center_id not in accessible):
        raise HTTPException(403, "无权访问该访视")
    return visit


@router.get("/", response_model=List[QueryOut])
def list_queries(
    visit_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """按访视/状态列出 query，按中心隔离。"""
    query = db.query(Query).join(Visit).join(Patient)
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None:
        query = query.filter(Patient.center_id.in_(accessible))
    if visit_id:
        query = query.filter(Query.visit_id == visit_id)
    if status:
        query = query.filter(Query.status == status)
    return query.order_by(Query.created_at.desc()).all()


@router.post("/", response_model=QueryOut, status_code=201)
def create_query(
    data: QueryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_qc),
):
    """质控员创建 query（submitted 状态的访视）。"""
    visit = _get_accessible_visit(db, data.visit_id, current_user)
    if visit.status == "draft":
        raise HTTPException(400, "草稿状态的访视无需质控质疑，请先提交")
    q = Query(
        visit_id=data.visit_id,
        field_name=data.field_name,
        content=data.content,
        raised_by=current_user.id,
        status="open",
    )
    db.add(q)
    db.flush()
    log_action(db, current_user, "queries", q.id, "create",
               f"visit={data.visit_id} field={data.field_name}: {data.content[:100]}")
    # 给该访视的创建研究者发站内通知
    notify_user(db, visit.created_by, "query_raised",
                f"访视 #{data.visit_id} 的字段 {data.field_name} 被质控质疑：{data.content[:80]}")
    db.commit()
    db.refresh(q)
    return q


@router.patch("/{query_id}/answer", response_model=QueryOut)
def answer_query(
    query_id: int,
    data: QueryAnswer,
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    """研究者回答 query（open → answered）。"""
    q = db.query(Query).filter(Query.id == query_id).first()
    if not q:
        raise HTTPException(404, "疑问不存在")
    _get_accessible_visit(db, q.visit_id, current_user)
    if q.status not in ("open", "answered"):
        raise HTTPException(400, "该疑问已关闭")
    q.answer = data.answer
    q.answered_by = current_user.id
    q.status = "answered"
    log_action(db, current_user, "queries", q.id, "answer", data.answer[:200])
    db.commit()
    db.refresh(q)
    return q


@router.patch("/{query_id}/close", response_model=QueryOut)
def close_query(
    query_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_qc),
):
    """质控员关闭 query（answered → closed）。"""
    q = db.query(Query).filter(Query.id == query_id).first()
    if not q:
        raise HTTPException(404, "疑问不存在")
    _get_accessible_visit(db, q.visit_id, current_user)
    if q.status != "answered":
        raise HTTPException(400, "研究者尚未回答，无法关闭")
    q.status = "closed"
    log_action(db, current_user, "queries", q.id, "close", "")
    db.commit()
    db.refresh(q)
    return q
